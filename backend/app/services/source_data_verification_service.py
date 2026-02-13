"""Source Data Verification Service (SDV).

Manages source data verification operations: SDV task tracking, finding
documentation, site-level SDV progress, review records, and SDV metrics.

Usage:
    from app.services.source_data_verification_service import (
        get_source_data_verification_service,
    )

    svc = get_source_data_verification_service()
    tasks = svc.list_sdv_tasks()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.source_data_verification import (
    FindingSeverity,
    FindingStatus,
    ReviewOutcome,
    SDVFinding,
    SDVFindingCreate,
    SDVFindingUpdate,
    SDVPriority,
    SDVReviewRecord,
    SDVReviewRecordCreate,
    SDVReviewRecordUpdate,
    SDVSiteProgress,
    SDVSiteProgressCreate,
    SDVSiteProgressUpdate,
    SDVTask,
    SDVTaskCreate,
    SDVTaskStatus,
    SDVTaskUpdate,
    SourceDataVerificationMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SourceDataVerificationService:
    """In-memory Source Data Verification engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._sdv_tasks: dict[str, SDVTask] = {}
        self._sdv_findings: dict[str, SDVFinding] = {}
        self._sdv_site_progress: dict[str, SDVSiteProgress] = {}
        self._sdv_review_records: dict[str, SDVReviewRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic source data verification data."""
        now = datetime.now(timezone.utc)

        # --- 12 SDV Tasks ---
        tasks_data = [
            {
                "id": "SDVT-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "subject_id": "SUBJ-E001",
                "visit_name": "Screening",
                "crf_name": "Demographics",
                "task_status": SDVTaskStatus.COMPLETED,
                "priority": SDVPriority.HIGH,
                "assigned_to": "CRA Sarah Johnson",
                "due_date": now - timedelta(days=60),
                "completed_date": now - timedelta(days=62),
                "fields_verified": 15,
                "fields_total": 15,
                "discrepancies_found": 0,
                "notes": "All demographic fields verified against source. No discrepancies.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "SDVT-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "subject_id": "SUBJ-E001",
                "visit_name": "Week 4",
                "crf_name": "Vital Signs",
                "task_status": SDVTaskStatus.COMPLETED,
                "priority": SDVPriority.MEDIUM,
                "assigned_to": "CRA Sarah Johnson",
                "due_date": now - timedelta(days=45),
                "completed_date": now - timedelta(days=47),
                "fields_verified": 12,
                "fields_total": 12,
                "discrepancies_found": 1,
                "notes": "Minor discrepancy in systolic BP recording. Query issued.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SDVT-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "subject_id": "SUBJ-E003",
                "visit_name": "Baseline",
                "crf_name": "Medical History",
                "task_status": SDVTaskStatus.IN_PROGRESS,
                "priority": SDVPriority.HIGH,
                "assigned_to": "CRA Michael Chen",
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "fields_verified": 8,
                "fields_total": 22,
                "discrepancies_found": 2,
                "notes": "In progress. Two findings documented for concomitant medication entries.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SDVT-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "subject_id": "SUBJ-E002",
                "visit_name": "Week 8",
                "crf_name": "Adverse Events",
                "task_status": SDVTaskStatus.PENDING,
                "priority": SDVPriority.CRITICAL,
                "assigned_to": "CRA Michael Chen",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "fields_verified": 0,
                "fields_total": 18,
                "discrepancies_found": 0,
                "notes": "Pending AE verification. High priority due to SAE report.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SDVT-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "subject_id": "SUBJ-D001",
                "visit_name": "Baseline",
                "crf_name": "Efficacy Assessments",
                "task_status": SDVTaskStatus.COMPLETED,
                "priority": SDVPriority.HIGH,
                "assigned_to": "CRA Lisa Park",
                "due_date": now - timedelta(days=50),
                "completed_date": now - timedelta(days=52),
                "fields_verified": 20,
                "fields_total": 20,
                "discrepancies_found": 0,
                "notes": "All efficacy endpoints verified. Data matches source records.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "SDVT-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "subject_id": "SUBJ-D002",
                "visit_name": "Week 4",
                "crf_name": "Lab Results",
                "task_status": SDVTaskStatus.IN_PROGRESS,
                "priority": SDVPriority.MEDIUM,
                "assigned_to": "CRA Lisa Park",
                "due_date": now + timedelta(days=5),
                "completed_date": None,
                "fields_verified": 10,
                "fields_total": 25,
                "discrepancies_found": 3,
                "notes": "Three lab value discrepancies identified. Queries pending site response.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "SDVT-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "subject_id": "SUBJ-D003",
                "visit_name": "Screening",
                "crf_name": "Informed Consent",
                "task_status": SDVTaskStatus.ON_HOLD,
                "priority": SDVPriority.CRITICAL,
                "assigned_to": "CRA David Kim",
                "due_date": now + timedelta(days=3),
                "completed_date": None,
                "fields_verified": 5,
                "fields_total": 10,
                "discrepancies_found": 1,
                "notes": "On hold pending IRB clarification on consent version discrepancy.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "SDVT-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "subject_id": "SUBJ-D003",
                "visit_name": "Week 8",
                "crf_name": "Concomitant Medications",
                "task_status": SDVTaskStatus.OVERDUE,
                "priority": SDVPriority.LOW,
                "assigned_to": "CRA David Kim",
                "due_date": now - timedelta(days=5),
                "completed_date": None,
                "fields_verified": 0,
                "fields_total": 14,
                "discrepancies_found": 0,
                "notes": "Overdue. CRA reassignment under review.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "SDVT-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "subject_id": "SUBJ-L001",
                "visit_name": "Baseline",
                "crf_name": "Tumor Assessment",
                "task_status": SDVTaskStatus.COMPLETED,
                "priority": SDVPriority.CRITICAL,
                "assigned_to": "CRA Rachel Adams",
                "due_date": now - timedelta(days=40),
                "completed_date": now - timedelta(days=42),
                "fields_verified": 30,
                "fields_total": 30,
                "discrepancies_found": 0,
                "notes": "Complete tumor assessment verification. All measurements confirmed.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SDVT-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "subject_id": "SUBJ-L002",
                "visit_name": "Week 6",
                "crf_name": "Immunogenicity",
                "task_status": SDVTaskStatus.IN_PROGRESS,
                "priority": SDVPriority.HIGH,
                "assigned_to": "CRA Rachel Adams",
                "due_date": now + timedelta(days=10),
                "completed_date": None,
                "fields_verified": 6,
                "fields_total": 16,
                "discrepancies_found": 1,
                "notes": "Immunogenicity sample collection time discrepancy noted.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SDVT-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "subject_id": "SUBJ-L003",
                "visit_name": "Screening",
                "crf_name": "Eligibility Criteria",
                "task_status": SDVTaskStatus.CANCELLED,
                "priority": SDVPriority.ROUTINE,
                "assigned_to": "CRA Tom Bradley",
                "due_date": now - timedelta(days=15),
                "completed_date": None,
                "fields_verified": 3,
                "fields_total": 20,
                "discrepancies_found": 0,
                "notes": "Cancelled due to subject withdrawal from study.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "SDVT-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "subject_id": "SUBJ-L001",
                "visit_name": "Week 12",
                "crf_name": "Study Drug Accountability",
                "task_status": SDVTaskStatus.PENDING,
                "priority": SDVPriority.MEDIUM,
                "assigned_to": "CRA Tom Bradley",
                "due_date": now + timedelta(days=21),
                "completed_date": None,
                "fields_verified": 0,
                "fields_total": 10,
                "discrepancies_found": 0,
                "notes": "Pending drug accountability verification for Week 12 visit.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for t in tasks_data:
            self._sdv_tasks[t["id"]] = SDVTask(**t)

        # --- 12 SDV Findings ---
        findings_data = [
            {
                "id": "SDVF-001",
                "trial_id": EYLEA_TRIAL,
                "task_id": "SDVT-002",
                "site_id": "SITE-NY-001",
                "subject_id": "SUBJ-E001",
                "field_name": "systolic_bp",
                "finding_severity": FindingSeverity.MINOR,
                "finding_status": FindingStatus.RESOLVED,
                "source_value": "138",
                "crf_value": "148",
                "description": "Systolic blood pressure transcription error. Source reads 138 mmHg but CRF entered as 148 mmHg.",
                "corrective_action": "CRF value corrected to 138 mmHg per source document.",
                "identified_by": "CRA Sarah Johnson",
                "resolved_by": "Site Coordinator Amy Lin",
                "resolved_date": now - timedelta(days=44),
                "notes": "Simple transcription error. No impact on safety assessment.",
                "created_at": now - timedelta(days=47),
            },
            {
                "id": "SDVF-002",
                "trial_id": EYLEA_TRIAL,
                "task_id": "SDVT-003",
                "site_id": "SITE-LA-001",
                "subject_id": "SUBJ-E003",
                "field_name": "concomitant_med_start_date",
                "finding_severity": FindingSeverity.MAJOR,
                "finding_status": FindingStatus.OPEN,
                "source_value": "2025-08-15",
                "crf_value": "2025-09-15",
                "description": "Concomitant medication start date discrepancy. One month difference between source and CRF.",
                "corrective_action": None,
                "identified_by": "CRA Michael Chen",
                "resolved_by": None,
                "resolved_date": None,
                "notes": "Query issued to site. Awaiting PI clarification.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "SDVF-003",
                "trial_id": EYLEA_TRIAL,
                "task_id": "SDVT-003",
                "site_id": "SITE-LA-001",
                "subject_id": "SUBJ-E003",
                "field_name": "concomitant_med_dose",
                "finding_severity": FindingSeverity.MINOR,
                "finding_status": FindingStatus.IN_REVIEW,
                "source_value": "10mg",
                "crf_value": "100mg",
                "description": "Medication dose entry appears to have extra zero. Source shows 10mg, CRF shows 100mg.",
                "corrective_action": None,
                "identified_by": "CRA Michael Chen",
                "resolved_by": None,
                "resolved_date": None,
                "notes": "Potential tenfold dosing error. Escalated for medical review.",
                "created_at": now - timedelta(days=27),
            },
            {
                "id": "SDVF-004",
                "trial_id": EYLEA_TRIAL,
                "task_id": "SDVT-004",
                "site_id": "SITE-LA-001",
                "subject_id": "SUBJ-E002",
                "field_name": "ae_onset_date",
                "finding_severity": FindingSeverity.CRITICAL,
                "finding_status": FindingStatus.ESCALATED,
                "source_value": "2025-10-01",
                "crf_value": "2025-11-01",
                "description": "Adverse event onset date discrepancy for SAE. Could affect causality assessment.",
                "corrective_action": None,
                "identified_by": "CRA Michael Chen",
                "resolved_by": None,
                "resolved_date": None,
                "notes": "Escalated to medical monitor. SAE timeline under review.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "SDVF-005",
                "trial_id": DUPIXENT_TRIAL,
                "task_id": "SDVT-006",
                "site_id": "SITE-CHI-001",
                "subject_id": "SUBJ-D002",
                "field_name": "hemoglobin",
                "finding_severity": FindingSeverity.MINOR,
                "finding_status": FindingStatus.RESOLVED,
                "source_value": "13.2",
                "crf_value": "13.8",
                "description": "Hemoglobin value discrepancy. Lab report shows 13.2 g/dL, CRF entered 13.8 g/dL.",
                "corrective_action": "CRF corrected to match lab report value of 13.2 g/dL.",
                "identified_by": "CRA Lisa Park",
                "resolved_by": "Data Manager Tom Lee",
                "resolved_date": now - timedelta(days=15),
                "notes": "Transcription error corrected. No clinical significance.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SDVF-006",
                "trial_id": DUPIXENT_TRIAL,
                "task_id": "SDVT-006",
                "site_id": "SITE-CHI-001",
                "subject_id": "SUBJ-D002",
                "field_name": "creatinine",
                "finding_severity": FindingSeverity.MAJOR,
                "finding_status": FindingStatus.OPEN,
                "source_value": "1.8",
                "crf_value": "0.8",
                "description": "Creatinine value significantly different. Source shows 1.8 mg/dL (elevated), CRF shows 0.8 mg/dL (normal).",
                "corrective_action": None,
                "identified_by": "CRA Lisa Park",
                "resolved_by": None,
                "resolved_date": None,
                "notes": "Clinically significant discrepancy. May affect eligibility assessment.",
                "created_at": now - timedelta(days=33),
            },
            {
                "id": "SDVF-007",
                "trial_id": DUPIXENT_TRIAL,
                "task_id": "SDVT-006",
                "site_id": "SITE-CHI-001",
                "subject_id": "SUBJ-D002",
                "field_name": "alt_sgpt",
                "finding_severity": FindingSeverity.OBSERVATION,
                "finding_status": FindingStatus.CLOSED,
                "source_value": "42",
                "crf_value": "42",
                "description": "ALT value matches but units not specified in CRF. Source clearly states U/L.",
                "corrective_action": "Units field populated with U/L to match source document.",
                "identified_by": "CRA Lisa Park",
                "resolved_by": "Site Coordinator Kim Wu",
                "resolved_date": now - timedelta(days=20),
                "notes": "Documentation improvement. Values were correct.",
                "created_at": now - timedelta(days=32),
            },
            {
                "id": "SDVF-008",
                "trial_id": DUPIXENT_TRIAL,
                "task_id": "SDVT-007",
                "site_id": "SITE-BOS-001",
                "subject_id": "SUBJ-D003",
                "field_name": "consent_version",
                "finding_severity": FindingSeverity.CRITICAL,
                "finding_status": FindingStatus.OPEN,
                "source_value": "v3.1",
                "crf_value": "v2.0",
                "description": "Informed consent version mismatch. Subject signed v3.1 but CRF references v2.0.",
                "corrective_action": None,
                "identified_by": "CRA David Kim",
                "resolved_by": None,
                "resolved_date": None,
                "notes": "Critical regulatory finding. IRB notification may be required.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "SDVF-009",
                "trial_id": LIBTAYO_TRIAL,
                "task_id": "SDVT-010",
                "site_id": "SITE-HOU-001",
                "subject_id": "SUBJ-L002",
                "field_name": "sample_collection_time",
                "finding_severity": FindingSeverity.MAJOR,
                "finding_status": FindingStatus.IN_REVIEW,
                "source_value": "08:30",
                "crf_value": "14:30",
                "description": "Immunogenicity sample collection time discrepancy. 6-hour difference may invalidate PK data.",
                "corrective_action": None,
                "identified_by": "CRA Rachel Adams",
                "resolved_by": None,
                "resolved_date": None,
                "notes": "Under review by PK scientist. May require protocol deviation report.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SDVF-010",
                "trial_id": LIBTAYO_TRIAL,
                "task_id": "SDVT-009",
                "site_id": "SITE-HOU-001",
                "subject_id": "SUBJ-L001",
                "field_name": "tumor_measurement_longest_diameter",
                "finding_severity": FindingSeverity.INFORMATIONAL,
                "finding_status": FindingStatus.CLOSED,
                "source_value": "2.3cm",
                "crf_value": "2.3cm",
                "description": "Tumor measurement verified and matches. Documented for completeness of SDV trail.",
                "corrective_action": None,
                "identified_by": "CRA Rachel Adams",
                "resolved_by": "CRA Rachel Adams",
                "resolved_date": now - timedelta(days=42),
                "notes": "Verification complete. No discrepancy.",
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "SDVF-011",
                "trial_id": LIBTAYO_TRIAL,
                "task_id": "SDVT-010",
                "site_id": "SITE-HOU-001",
                "subject_id": "SUBJ-L002",
                "field_name": "body_weight",
                "finding_severity": FindingSeverity.MINOR,
                "finding_status": FindingStatus.WONT_FIX,
                "source_value": "72.5",
                "crf_value": "72.0",
                "description": "Body weight rounding difference. Source shows 72.5 kg, CRF rounded to 72.0 kg.",
                "corrective_action": None,
                "identified_by": "CRA Rachel Adams",
                "resolved_by": "Data Manager Janet Price",
                "resolved_date": now - timedelta(days=25),
                "notes": "Within acceptable rounding tolerance per protocol. Won't fix.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "SDVF-012",
                "trial_id": LIBTAYO_TRIAL,
                "task_id": "SDVT-012",
                "site_id": "SITE-SEA-001",
                "subject_id": "SUBJ-L001",
                "field_name": "drug_return_count",
                "finding_severity": FindingSeverity.MAJOR,
                "finding_status": FindingStatus.OPEN,
                "source_value": "8",
                "crf_value": "6",
                "description": "Drug accountability discrepancy. Pharmacy log shows 8 units returned but CRF records 6.",
                "corrective_action": None,
                "identified_by": "CRA Tom Bradley",
                "resolved_by": None,
                "resolved_date": None,
                "notes": "Two unaccounted drug units. Compliance investigation initiated.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for f in findings_data:
            self._sdv_findings[f["id"]] = SDVFinding(**f)

        # --- 12 SDV Site Progress Records ---
        site_progress_data = [
            {
                "id": "SDVP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "site_name": "New York University Medical Center",
                "total_subjects": 25,
                "subjects_verified": 20,
                "total_crfs": 150,
                "crfs_verified": 125,
                "total_fields": 2250,
                "fields_verified": 1900,
                "sdv_completion_pct": 84.4,
                "open_findings": 2,
                "last_sdv_date": now - timedelta(days=5),
                "next_scheduled_date": now + timedelta(days=14),
                "assigned_cra": "CRA Sarah Johnson",
                "notes": "On track. Strong site performance with low discrepancy rate.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "SDVP-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "site_name": "UCLA Medical Center",
                "total_subjects": 18,
                "subjects_verified": 10,
                "total_crfs": 108,
                "crfs_verified": 55,
                "total_fields": 1620,
                "fields_verified": 780,
                "sdv_completion_pct": 48.1,
                "open_findings": 5,
                "last_sdv_date": now - timedelta(days=10),
                "next_scheduled_date": now + timedelta(days=7),
                "assigned_cra": "CRA Michael Chen",
                "notes": "Below target. Additional monitoring visits scheduled.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "SDVP-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-SF-001",
                "site_name": "UCSF Medical Center",
                "total_subjects": 12,
                "subjects_verified": 12,
                "total_crfs": 72,
                "crfs_verified": 72,
                "total_fields": 1080,
                "fields_verified": 1080,
                "sdv_completion_pct": 100.0,
                "open_findings": 0,
                "last_sdv_date": now - timedelta(days=3),
                "next_scheduled_date": now + timedelta(days=30),
                "assigned_cra": "CRA Sarah Johnson",
                "notes": "Fully verified. Exemplary site with zero open findings.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "SDVP-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-DAL-001",
                "site_name": "UT Southwestern Medical Center",
                "total_subjects": 8,
                "subjects_verified": 4,
                "total_crfs": 48,
                "crfs_verified": 20,
                "total_fields": 720,
                "fields_verified": 280,
                "sdv_completion_pct": 38.9,
                "open_findings": 3,
                "last_sdv_date": now - timedelta(days=20),
                "next_scheduled_date": now + timedelta(days=5),
                "assigned_cra": "CRA Michael Chen",
                "notes": "New site with limited enrollment. Ramping up SDV activities.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SDVP-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "site_name": "Northwestern Memorial Hospital",
                "total_subjects": 30,
                "subjects_verified": 24,
                "total_crfs": 180,
                "crfs_verified": 145,
                "total_fields": 2700,
                "fields_verified": 2200,
                "sdv_completion_pct": 81.5,
                "open_findings": 4,
                "last_sdv_date": now - timedelta(days=7),
                "next_scheduled_date": now + timedelta(days=14),
                "assigned_cra": "CRA Lisa Park",
                "notes": "High-enrolling site. SDV on schedule despite volume.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "SDVP-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "site_name": "Massachusetts General Hospital",
                "total_subjects": 15,
                "subjects_verified": 8,
                "total_crfs": 90,
                "crfs_verified": 42,
                "total_fields": 1350,
                "fields_verified": 600,
                "sdv_completion_pct": 44.4,
                "open_findings": 6,
                "last_sdv_date": now - timedelta(days=15),
                "next_scheduled_date": now + timedelta(days=3),
                "assigned_cra": "CRA David Kim",
                "notes": "Falling behind target. Consent version issue contributing to delays.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SDVP-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-PHI-001",
                "site_name": "Penn Medicine",
                "total_subjects": 22,
                "subjects_verified": 19,
                "total_crfs": 132,
                "crfs_verified": 115,
                "total_fields": 1980,
                "fields_verified": 1750,
                "sdv_completion_pct": 88.4,
                "open_findings": 1,
                "last_sdv_date": now - timedelta(days=4),
                "next_scheduled_date": now + timedelta(days=21),
                "assigned_cra": "CRA Lisa Park",
                "notes": "Excellent performance. Minimal findings and rapid resolution.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "SDVP-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-ATL-001",
                "site_name": "Emory University Hospital",
                "total_subjects": 10,
                "subjects_verified": 6,
                "total_crfs": 60,
                "crfs_verified": 30,
                "total_fields": 900,
                "fields_verified": 420,
                "sdv_completion_pct": 46.7,
                "open_findings": 2,
                "last_sdv_date": now - timedelta(days=12),
                "next_scheduled_date": now + timedelta(days=10),
                "assigned_cra": "CRA David Kim",
                "notes": "Moderate progress. Site training on data entry completed last week.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "SDVP-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "site_name": "MD Anderson Cancer Center",
                "total_subjects": 35,
                "subjects_verified": 30,
                "total_crfs": 210,
                "crfs_verified": 185,
                "total_fields": 3150,
                "fields_verified": 2800,
                "sdv_completion_pct": 88.9,
                "open_findings": 3,
                "last_sdv_date": now - timedelta(days=2),
                "next_scheduled_date": now + timedelta(days=14),
                "assigned_cra": "CRA Rachel Adams",
                "notes": "Top-performing oncology site. Experienced staff and low error rate.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SDVP-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "site_name": "Fred Hutchinson Cancer Center",
                "total_subjects": 20,
                "subjects_verified": 12,
                "total_crfs": 120,
                "crfs_verified": 65,
                "total_fields": 1800,
                "fields_verified": 950,
                "sdv_completion_pct": 52.8,
                "open_findings": 4,
                "last_sdv_date": now - timedelta(days=8),
                "next_scheduled_date": now + timedelta(days=7),
                "assigned_cra": "CRA Tom Bradley",
                "notes": "Moderate progress. Subject withdrawal impacting SDV completion metrics.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "SDVP-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-MIA-001",
                "site_name": "Sylvester Comprehensive Cancer Center",
                "total_subjects": 14,
                "subjects_verified": 14,
                "total_crfs": 84,
                "crfs_verified": 84,
                "total_fields": 1260,
                "fields_verified": 1260,
                "sdv_completion_pct": 100.0,
                "open_findings": 0,
                "last_sdv_date": now - timedelta(days=1),
                "next_scheduled_date": now + timedelta(days=28),
                "assigned_cra": "CRA Rachel Adams",
                "notes": "100% SDV complete. All findings resolved. Model site.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SDVP-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-DEN-001",
                "site_name": "University of Colorado Hospital",
                "total_subjects": 6,
                "subjects_verified": 2,
                "total_crfs": 36,
                "crfs_verified": 10,
                "total_fields": 540,
                "fields_verified": 140,
                "sdv_completion_pct": 25.9,
                "open_findings": 1,
                "last_sdv_date": now - timedelta(days=25),
                "next_scheduled_date": now + timedelta(days=2),
                "assigned_cra": "CRA Tom Bradley",
                "notes": "Recently activated site. SDV just beginning. First monitoring visit upcoming.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for sp in site_progress_data:
            self._sdv_site_progress[sp["id"]] = SDVSiteProgress(**sp)

        # --- 12 SDV Review Records ---
        review_data = [
            {
                "id": "SDVR-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "review_date": now - timedelta(days=60),
                "reviewer_name": "CRA Sarah Johnson",
                "review_type": "Routine Monitoring Visit",
                "subjects_reviewed": 8,
                "crfs_reviewed": 48,
                "findings_generated": 1,
                "review_outcome": ReviewOutcome.PASS,
                "duration_hours": 6.5,
                "follow_up_required": False,
                "follow_up_due_date": None,
                "notes": "Routine visit completed successfully. One minor finding documented.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SDVR-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "review_date": now - timedelta(days=30),
                "reviewer_name": "CRA Michael Chen",
                "review_type": "Interim Monitoring Visit",
                "subjects_reviewed": 5,
                "crfs_reviewed": 30,
                "findings_generated": 4,
                "review_outcome": ReviewOutcome.CONDITIONAL_PASS,
                "duration_hours": 8.0,
                "follow_up_required": True,
                "follow_up_due_date": now + timedelta(days=14),
                "notes": "Conditional pass. Four findings require resolution before next visit.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SDVR-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-SF-001",
                "review_date": now - timedelta(days=20),
                "reviewer_name": "CRA Sarah Johnson",
                "review_type": "Close-out Visit",
                "subjects_reviewed": 12,
                "crfs_reviewed": 72,
                "findings_generated": 0,
                "review_outcome": ReviewOutcome.PASS,
                "duration_hours": 10.0,
                "follow_up_required": False,
                "follow_up_due_date": None,
                "notes": "Site close-out complete. All SDV 100%. No open queries.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "SDVR-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-DAL-001",
                "review_date": now - timedelta(days=15),
                "reviewer_name": "CRA Michael Chen",
                "review_type": "Site Initiation Visit",
                "subjects_reviewed": 0,
                "crfs_reviewed": 0,
                "findings_generated": 0,
                "review_outcome": ReviewOutcome.NOT_APPLICABLE,
                "duration_hours": 4.0,
                "follow_up_required": True,
                "follow_up_due_date": now + timedelta(days=30),
                "notes": "SIV completed. Site trained on SDV procedures. First subjects expected within 2 weeks.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "SDVR-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "review_date": now - timedelta(days=25),
                "reviewer_name": "CRA Lisa Park",
                "review_type": "Routine Monitoring Visit",
                "subjects_reviewed": 10,
                "crfs_reviewed": 60,
                "findings_generated": 3,
                "review_outcome": ReviewOutcome.PASS,
                "duration_hours": 7.5,
                "follow_up_required": False,
                "follow_up_due_date": None,
                "notes": "Routine visit. Three minor findings documented. Site performance satisfactory.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "SDVR-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "review_date": now - timedelta(days=18),
                "reviewer_name": "CRA David Kim",
                "review_type": "For-Cause Monitoring Visit",
                "subjects_reviewed": 4,
                "crfs_reviewed": 24,
                "findings_generated": 6,
                "review_outcome": ReviewOutcome.FAIL,
                "duration_hours": 9.0,
                "follow_up_required": True,
                "follow_up_due_date": now + timedelta(days=7),
                "notes": "For-cause visit due to consent discrepancy. Six findings including critical consent issue.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "SDVR-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-PHI-001",
                "review_date": now - timedelta(days=10),
                "reviewer_name": "CRA Lisa Park",
                "review_type": "Routine Monitoring Visit",
                "subjects_reviewed": 7,
                "crfs_reviewed": 42,
                "findings_generated": 1,
                "review_outcome": ReviewOutcome.PASS,
                "duration_hours": 5.5,
                "follow_up_required": False,
                "follow_up_due_date": None,
                "notes": "Excellent site. One informational finding only. Data quality high.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SDVR-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-ATL-001",
                "review_date": now - timedelta(days=8),
                "reviewer_name": "CRA David Kim",
                "review_type": "Interim Monitoring Visit",
                "subjects_reviewed": 3,
                "crfs_reviewed": 18,
                "findings_generated": 2,
                "review_outcome": ReviewOutcome.CONDITIONAL_PASS,
                "duration_hours": 6.0,
                "follow_up_required": True,
                "follow_up_due_date": now + timedelta(days=21),
                "notes": "Two findings related to data entry training gaps. Retraining scheduled.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "SDVR-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "review_date": now - timedelta(days=12),
                "reviewer_name": "CRA Rachel Adams",
                "review_type": "Routine Monitoring Visit",
                "subjects_reviewed": 12,
                "crfs_reviewed": 72,
                "findings_generated": 2,
                "review_outcome": ReviewOutcome.PASS,
                "duration_hours": 8.5,
                "follow_up_required": False,
                "follow_up_due_date": None,
                "notes": "Strong oncology site. Two minor findings documented and being addressed.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "SDVR-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "review_date": now - timedelta(days=5),
                "reviewer_name": "CRA Tom Bradley",
                "review_type": "Interim Monitoring Visit",
                "subjects_reviewed": 6,
                "crfs_reviewed": 36,
                "findings_generated": 3,
                "review_outcome": ReviewOutcome.CONDITIONAL_PASS,
                "duration_hours": 7.0,
                "follow_up_required": True,
                "follow_up_due_date": now + timedelta(days=14),
                "notes": "Three findings including drug accountability issue. Follow-up required.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "SDVR-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-MIA-001",
                "review_date": now - timedelta(days=3),
                "reviewer_name": "CRA Rachel Adams",
                "review_type": "Close-out Visit",
                "subjects_reviewed": 14,
                "crfs_reviewed": 84,
                "findings_generated": 0,
                "review_outcome": ReviewOutcome.PASS,
                "duration_hours": 11.0,
                "follow_up_required": False,
                "follow_up_due_date": None,
                "notes": "Close-out complete. 100% SDV. Zero open findings. Exemplary site.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "SDVR-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-DEN-001",
                "review_date": now - timedelta(days=1),
                "reviewer_name": "CRA Tom Bradley",
                "review_type": "Site Initiation Visit",
                "subjects_reviewed": 0,
                "crfs_reviewed": 0,
                "findings_generated": 0,
                "review_outcome": ReviewOutcome.DEFERRED,
                "duration_hours": 3.5,
                "follow_up_required": True,
                "follow_up_due_date": now + timedelta(days=45),
                "notes": "SIV for new site. Training completed. SDV deferred until first subjects enrolled.",
                "created_at": now - timedelta(days=1),
            },
        ]

        for r in review_data:
            self._sdv_review_records[r["id"]] = SDVReviewRecord(**r)

    # ------------------------------------------------------------------
    # SDV Tasks
    # ------------------------------------------------------------------

    def list_sdv_tasks(
        self,
        *,
        trial_id: str | None = None,
        task_status: SDVTaskStatus | None = None,
        priority: SDVPriority | None = None,
        site_id: str | None = None,
    ) -> list[SDVTask]:
        """List SDV tasks with optional filters."""
        with self._lock:
            result = list(self._sdv_tasks.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if task_status is not None:
            result = [t for t in result if t.task_status == task_status]
        if priority is not None:
            result = [t for t in result if t.priority == priority]
        if site_id is not None:
            result = [t for t in result if t.site_id == site_id]

        return sorted(result, key=lambda t: t.due_date, reverse=True)

    def get_sdv_task(self, task_id: str) -> SDVTask | None:
        """Get a single SDV task by ID."""
        with self._lock:
            return self._sdv_tasks.get(task_id)

    def create_sdv_task(self, payload: SDVTaskCreate) -> SDVTask:
        """Create a new SDV task."""
        now = datetime.now(timezone.utc)
        task_id = f"SDVT-{uuid4().hex[:8].upper()}"
        task = SDVTask(
            id=task_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            visit_name=payload.visit_name,
            crf_name=payload.crf_name,
            task_status=SDVTaskStatus.PENDING,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            completed_date=None,
            fields_verified=0,
            fields_total=payload.fields_total,
            discrepancies_found=0,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._sdv_tasks[task_id] = task
        logger.info("Created SDV task %s for trial %s", task_id, payload.trial_id)
        return task

    def update_sdv_task(
        self, task_id: str, payload: SDVTaskUpdate
    ) -> SDVTask | None:
        """Update an existing SDV task."""
        with self._lock:
            existing = self._sdv_tasks.get(task_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SDVTask(**data)
            self._sdv_tasks[task_id] = updated
        return updated

    def delete_sdv_task(self, task_id: str) -> bool:
        """Delete an SDV task. Returns True if deleted."""
        with self._lock:
            if task_id in self._sdv_tasks:
                del self._sdv_tasks[task_id]
                return True
            return False

    # ------------------------------------------------------------------
    # SDV Findings
    # ------------------------------------------------------------------

    def list_sdv_findings(
        self,
        *,
        trial_id: str | None = None,
        finding_severity: FindingSeverity | None = None,
        finding_status: FindingStatus | None = None,
        task_id: str | None = None,
    ) -> list[SDVFinding]:
        """List SDV findings with optional filters."""
        with self._lock:
            result = list(self._sdv_findings.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if finding_severity is not None:
            result = [f for f in result if f.finding_severity == finding_severity]
        if finding_status is not None:
            result = [f for f in result if f.finding_status == finding_status]
        if task_id is not None:
            result = [f for f in result if f.task_id == task_id]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_sdv_finding(self, finding_id: str) -> SDVFinding | None:
        """Get a single SDV finding by ID."""
        with self._lock:
            return self._sdv_findings.get(finding_id)

    def create_sdv_finding(self, payload: SDVFindingCreate) -> SDVFinding:
        """Create a new SDV finding."""
        now = datetime.now(timezone.utc)
        finding_id = f"SDVF-{uuid4().hex[:8].upper()}"
        finding = SDVFinding(
            id=finding_id,
            trial_id=payload.trial_id,
            task_id=payload.task_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            field_name=payload.field_name,
            finding_severity=payload.finding_severity,
            finding_status=FindingStatus.OPEN,
            source_value=payload.source_value,
            crf_value=payload.crf_value,
            description=payload.description,
            corrective_action=None,
            identified_by=payload.identified_by,
            resolved_by=None,
            resolved_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._sdv_findings[finding_id] = finding
        logger.info("Created SDV finding %s for task %s", finding_id, payload.task_id)
        return finding

    def update_sdv_finding(
        self, finding_id: str, payload: SDVFindingUpdate
    ) -> SDVFinding | None:
        """Update an existing SDV finding."""
        with self._lock:
            existing = self._sdv_findings.get(finding_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SDVFinding(**data)
            self._sdv_findings[finding_id] = updated
        return updated

    def delete_sdv_finding(self, finding_id: str) -> bool:
        """Delete an SDV finding. Returns True if deleted."""
        with self._lock:
            if finding_id in self._sdv_findings:
                del self._sdv_findings[finding_id]
                return True
            return False

    # ------------------------------------------------------------------
    # SDV Site Progress
    # ------------------------------------------------------------------

    def list_sdv_site_progress(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
    ) -> list[SDVSiteProgress]:
        """List SDV site progress records with optional filters."""
        with self._lock:
            result = list(self._sdv_site_progress.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if site_id is not None:
            result = [s for s in result if s.site_id == site_id]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_sdv_site_progress(self, progress_id: str) -> SDVSiteProgress | None:
        """Get a single SDV site progress record by ID."""
        with self._lock:
            return self._sdv_site_progress.get(progress_id)

    def create_sdv_site_progress(self, payload: SDVSiteProgressCreate) -> SDVSiteProgress:
        """Create a new SDV site progress record."""
        now = datetime.now(timezone.utc)
        progress_id = f"SDVP-{uuid4().hex[:8].upper()}"
        record = SDVSiteProgress(
            id=progress_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            total_subjects=payload.total_subjects,
            subjects_verified=0,
            total_crfs=payload.total_crfs,
            crfs_verified=0,
            total_fields=payload.total_fields,
            fields_verified=0,
            sdv_completion_pct=0.0,
            open_findings=0,
            last_sdv_date=None,
            next_scheduled_date=None,
            assigned_cra=payload.assigned_cra,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._sdv_site_progress[progress_id] = record
        logger.info("Created SDV site progress %s for site %s", progress_id, payload.site_id)
        return record

    def update_sdv_site_progress(
        self, progress_id: str, payload: SDVSiteProgressUpdate
    ) -> SDVSiteProgress | None:
        """Update an existing SDV site progress record."""
        with self._lock:
            existing = self._sdv_site_progress.get(progress_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SDVSiteProgress(**data)
            self._sdv_site_progress[progress_id] = updated
        return updated

    def delete_sdv_site_progress(self, progress_id: str) -> bool:
        """Delete an SDV site progress record. Returns True if deleted."""
        with self._lock:
            if progress_id in self._sdv_site_progress:
                del self._sdv_site_progress[progress_id]
                return True
            return False

    # ------------------------------------------------------------------
    # SDV Review Records
    # ------------------------------------------------------------------

    def list_sdv_review_records(
        self,
        *,
        trial_id: str | None = None,
        review_outcome: ReviewOutcome | None = None,
        site_id: str | None = None,
    ) -> list[SDVReviewRecord]:
        """List SDV review records with optional filters."""
        with self._lock:
            result = list(self._sdv_review_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if review_outcome is not None:
            result = [r for r in result if r.review_outcome == review_outcome]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.review_date, reverse=True)

    def get_sdv_review_record(self, review_id: str) -> SDVReviewRecord | None:
        """Get a single SDV review record by ID."""
        with self._lock:
            return self._sdv_review_records.get(review_id)

    def create_sdv_review_record(self, payload: SDVReviewRecordCreate) -> SDVReviewRecord:
        """Create a new SDV review record."""
        now = datetime.now(timezone.utc)
        review_id = f"SDVR-{uuid4().hex[:8].upper()}"
        record = SDVReviewRecord(
            id=review_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            review_date=now,
            reviewer_name=payload.reviewer_name,
            review_type=payload.review_type,
            subjects_reviewed=payload.subjects_reviewed,
            crfs_reviewed=payload.crfs_reviewed,
            findings_generated=0,
            review_outcome=ReviewOutcome.PASS,
            duration_hours=payload.duration_hours,
            follow_up_required=False,
            follow_up_due_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._sdv_review_records[review_id] = record
        logger.info("Created SDV review record %s for site %s", review_id, payload.site_id)
        return record

    def update_sdv_review_record(
        self, review_id: str, payload: SDVReviewRecordUpdate
    ) -> SDVReviewRecord | None:
        """Update an existing SDV review record."""
        with self._lock:
            existing = self._sdv_review_records.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SDVReviewRecord(**data)
            self._sdv_review_records[review_id] = updated
        return updated

    def delete_sdv_review_record(self, review_id: str) -> bool:
        """Delete an SDV review record. Returns True if deleted."""
        with self._lock:
            if review_id in self._sdv_review_records:
                del self._sdv_review_records[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> SourceDataVerificationMetrics:
        """Compute aggregated source data verification metrics."""
        with self._lock:
            tasks = list(self._sdv_tasks.values())
            findings = list(self._sdv_findings.values())
            site_progress = list(self._sdv_site_progress.values())
            reviews = list(self._sdv_review_records.values())

        # Filter by trial if specified
        if trial_id is not None:
            tasks = [t for t in tasks if t.trial_id == trial_id]
            findings = [f for f in findings if f.trial_id == trial_id]
            site_progress = [s for s in site_progress if s.trial_id == trial_id]
            reviews = [r for r in reviews if r.trial_id == trial_id]

        # Tasks by status
        tasks_by_status: dict[str, int] = {}
        for t in tasks:
            key = t.task_status.value
            tasks_by_status[key] = tasks_by_status.get(key, 0) + 1

        # Tasks by priority
        tasks_by_priority: dict[str, int] = {}
        for t in tasks:
            key = t.priority.value
            tasks_by_priority[key] = tasks_by_priority.get(key, 0) + 1

        # Task completion rate
        completed_count = sum(
            1 for t in tasks if t.task_status == SDVTaskStatus.COMPLETED
        )
        task_completion_rate = round(
            (completed_count / max(1, len(tasks))) * 100, 1
        )

        # Findings by severity
        findings_by_severity: dict[str, int] = {}
        for f in findings:
            key = f.finding_severity.value
            findings_by_severity[key] = findings_by_severity.get(key, 0) + 1

        # Findings by status
        findings_by_status: dict[str, int] = {}
        for f in findings:
            key = f.finding_status.value
            findings_by_status[key] = findings_by_status.get(key, 0) + 1

        # Open finding rate
        open_count = sum(
            1 for f in findings if f.finding_status == FindingStatus.OPEN
        )
        open_finding_rate = round(
            (open_count / max(1, len(findings))) * 100, 1
        )

        # Average SDV completion percentage
        avg_sdv_completion_pct = round(
            sum(s.sdv_completion_pct for s in site_progress) / max(1, len(site_progress)),
            1,
        )

        # Reviews by outcome
        reviews_by_outcome: dict[str, int] = {}
        for r in reviews:
            key = r.review_outcome.value
            reviews_by_outcome[key] = reviews_by_outcome.get(key, 0) + 1

        return SourceDataVerificationMetrics(
            total_tasks=len(tasks),
            tasks_by_status=tasks_by_status,
            tasks_by_priority=tasks_by_priority,
            task_completion_rate=task_completion_rate,
            total_findings=len(findings),
            findings_by_severity=findings_by_severity,
            findings_by_status=findings_by_status,
            open_finding_rate=open_finding_rate,
            total_sites_tracked=len(site_progress),
            avg_sdv_completion_pct=avg_sdv_completion_pct,
            total_reviews=len(reviews),
            reviews_by_outcome=reviews_by_outcome,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SourceDataVerificationService | None = None
_instance_lock = threading.Lock()


def get_source_data_verification_service() -> SourceDataVerificationService:
    """Return the singleton SourceDataVerificationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SourceDataVerificationService()
    return _instance


def reset_source_data_verification_service() -> SourceDataVerificationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SourceDataVerificationService()
    return _instance
