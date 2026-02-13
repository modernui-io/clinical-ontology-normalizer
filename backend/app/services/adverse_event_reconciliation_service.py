"""Adverse Event Reconciliation (AER-REC) Service.

Manages adverse event reconciliation operations: reconciliation tasks,
discrepancy records, line-item comparisons, reconciliation sign-offs,
and aggregated metrics across clinical trials.

Usage:
    from app.services.adverse_event_reconciliation_service import (
        get_adverse_event_reconciliation_service,
    )

    svc = get_adverse_event_reconciliation_service()
    tasks = svc.list_reconciliation_tasks()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.adverse_event_reconciliation import (
    AdverseEventReconciliationMetrics,
    ComparisonOutcome,
    DiscrepancyRecord,
    DiscrepancyRecordCreate,
    DiscrepancyRecordUpdate,
    DiscrepancySeverity,
    DiscrepancyType,
    LineItemComparison,
    LineItemComparisonCreate,
    LineItemComparisonUpdate,
    ReconciliationSignOff,
    ReconciliationSignOffCreate,
    ReconciliationSignOffUpdate,
    ReconciliationStatus,
    ReconciliationTask,
    ReconciliationTaskCreate,
    ReconciliationTaskUpdate,
    SignOffStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class AdverseEventReconciliationService:
    """In-memory Adverse Event Reconciliation engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._reconciliation_tasks: dict[str, ReconciliationTask] = {}
        self._discrepancy_records: dict[str, DiscrepancyRecord] = {}
        self._line_item_comparisons: dict[str, LineItemComparison] = {}
        self._reconciliation_sign_offs: dict[str, ReconciliationSignOff] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic AER reconciliation data across 3 trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Reconciliation Tasks (4 per trial) ---
        tasks_data = [
            # EYLEA
            {
                "id": "RCT-00000001",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_status": ReconciliationStatus.COMPLETED,
                "reconciliation_period_start": now - timedelta(days=180),
                "reconciliation_period_end": now - timedelta(days=150),
                "safety_db_name": "Argus Safety",
                "clinical_db_name": "Medidata Rave",
                "total_safety_records": 48,
                "total_clinical_records": 50,
                "matched_records": 46,
                "unmatched_records": 4,
                "assigned_to": "Sarah Mitchell",
                "started_date": now - timedelta(days=148),
                "completed_date": now - timedelta(days=140),
                "target_completion_date": now - timedelta(days=135),
                "notes": "Q2 reconciliation completed. 4 discrepancies identified and resolved.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "RCT-00000002",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_status": ReconciliationStatus.DISCREPANCIES_FOUND,
                "reconciliation_period_start": now - timedelta(days=90),
                "reconciliation_period_end": now - timedelta(days=60),
                "safety_db_name": "Argus Safety",
                "clinical_db_name": "Medidata Rave",
                "total_safety_records": 62,
                "total_clinical_records": 65,
                "matched_records": 58,
                "unmatched_records": 7,
                "assigned_to": "Sarah Mitchell",
                "started_date": now - timedelta(days=58),
                "completed_date": None,
                "target_completion_date": now - timedelta(days=30),
                "notes": "Q3 reconciliation in progress. 7 discrepancies under review.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RCT-00000003",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_status": ReconciliationStatus.IN_PROGRESS,
                "reconciliation_period_start": now - timedelta(days=30),
                "reconciliation_period_end": now,
                "safety_db_name": "Argus Safety",
                "clinical_db_name": "Medidata Rave",
                "total_safety_records": 35,
                "total_clinical_records": 37,
                "matched_records": 30,
                "unmatched_records": 5,
                "assigned_to": "David Park",
                "started_date": now - timedelta(days=2),
                "completed_date": None,
                "target_completion_date": now + timedelta(days=14),
                "notes": "Q4 reconciliation started.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "RCT-00000004",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_status": ReconciliationStatus.SCHEDULED,
                "reconciliation_period_start": now + timedelta(days=30),
                "reconciliation_period_end": now + timedelta(days=60),
                "safety_db_name": "Argus Safety",
                "clinical_db_name": "Medidata Rave",
                "total_safety_records": 0,
                "total_clinical_records": 0,
                "matched_records": 0,
                "unmatched_records": 0,
                "assigned_to": "David Park",
                "started_date": None,
                "completed_date": None,
                "target_completion_date": now + timedelta(days=75),
                "notes": None,
                "created_at": now - timedelta(days=1),
            },
            # DUPIXENT
            {
                "id": "RCT-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_status": ReconciliationStatus.COMPLETED,
                "reconciliation_period_start": now - timedelta(days=200),
                "reconciliation_period_end": now - timedelta(days=170),
                "safety_db_name": "Oracle Argus",
                "clinical_db_name": "Veeva Vault CDMS",
                "total_safety_records": 120,
                "total_clinical_records": 125,
                "matched_records": 118,
                "unmatched_records": 7,
                "assigned_to": "Jennifer Lee",
                "started_date": now - timedelta(days=168),
                "completed_date": now - timedelta(days=155),
                "target_completion_date": now - timedelta(days=150),
                "notes": "Initial reconciliation completed successfully.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "RCT-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_status": ReconciliationStatus.ESCALATED,
                "reconciliation_period_start": now - timedelta(days=120),
                "reconciliation_period_end": now - timedelta(days=90),
                "safety_db_name": "Oracle Argus",
                "clinical_db_name": "Veeva Vault CDMS",
                "total_safety_records": 145,
                "total_clinical_records": 140,
                "matched_records": 130,
                "unmatched_records": 15,
                "assigned_to": "Jennifer Lee",
                "started_date": now - timedelta(days=88),
                "completed_date": None,
                "target_completion_date": now - timedelta(days=60),
                "notes": "Escalated due to high number of discrepancies. Safety DB has 5 extra records.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "RCT-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_status": ReconciliationStatus.IN_PROGRESS,
                "reconciliation_period_start": now - timedelta(days=45),
                "reconciliation_period_end": now - timedelta(days=15),
                "safety_db_name": "Oracle Argus",
                "clinical_db_name": "Veeva Vault CDMS",
                "total_safety_records": 88,
                "total_clinical_records": 90,
                "matched_records": 82,
                "unmatched_records": 8,
                "assigned_to": "Robert Chen",
                "started_date": now - timedelta(days=10),
                "completed_date": None,
                "target_completion_date": now + timedelta(days=5),
                "notes": "Ongoing comparison of Q3 period.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RCT-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_status": ReconciliationStatus.CLOSED,
                "reconciliation_period_start": now - timedelta(days=300),
                "reconciliation_period_end": now - timedelta(days=270),
                "safety_db_name": "Oracle Argus",
                "clinical_db_name": "Veeva Vault CDMS",
                "total_safety_records": 95,
                "total_clinical_records": 95,
                "matched_records": 95,
                "unmatched_records": 0,
                "assigned_to": "Jennifer Lee",
                "started_date": now - timedelta(days=268),
                "completed_date": now - timedelta(days=255),
                "target_completion_date": now - timedelta(days=250),
                "notes": "Baseline reconciliation closed with no discrepancies.",
                "created_at": now - timedelta(days=270),
            },
            # LIBTAYO
            {
                "id": "RCT-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_status": ReconciliationStatus.COMPLETED,
                "reconciliation_period_start": now - timedelta(days=150),
                "reconciliation_period_end": now - timedelta(days=120),
                "safety_db_name": "ArisGlobal LifeSphere",
                "clinical_db_name": "Oracle Clinical",
                "total_safety_records": 75,
                "total_clinical_records": 78,
                "matched_records": 72,
                "unmatched_records": 6,
                "assigned_to": "Maria Santos",
                "started_date": now - timedelta(days=118),
                "completed_date": now - timedelta(days=105),
                "target_completion_date": now - timedelta(days=100),
                "notes": "Reconciliation completed. Minor date mismatches corrected.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "RCT-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_status": ReconciliationStatus.DISCREPANCIES_FOUND,
                "reconciliation_period_start": now - timedelta(days=60),
                "reconciliation_period_end": now - timedelta(days=30),
                "safety_db_name": "ArisGlobal LifeSphere",
                "clinical_db_name": "Oracle Clinical",
                "total_safety_records": 92,
                "total_clinical_records": 88,
                "matched_records": 80,
                "unmatched_records": 12,
                "assigned_to": "Maria Santos",
                "started_date": now - timedelta(days=28),
                "completed_date": None,
                "target_completion_date": now - timedelta(days=10),
                "notes": "Multiple causality and coding mismatches detected.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RCT-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_status": ReconciliationStatus.SCHEDULED,
                "reconciliation_period_start": now + timedelta(days=15),
                "reconciliation_period_end": now + timedelta(days=45),
                "safety_db_name": "ArisGlobal LifeSphere",
                "clinical_db_name": "Oracle Clinical",
                "total_safety_records": 0,
                "total_clinical_records": 0,
                "matched_records": 0,
                "unmatched_records": 0,
                "assigned_to": "Maria Santos",
                "started_date": None,
                "completed_date": None,
                "target_completion_date": now + timedelta(days=60),
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "RCT-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_status": ReconciliationStatus.IN_PROGRESS,
                "reconciliation_period_start": now - timedelta(days=20),
                "reconciliation_period_end": now - timedelta(days=5),
                "safety_db_name": "ArisGlobal LifeSphere",
                "clinical_db_name": "Oracle Clinical",
                "total_safety_records": 40,
                "total_clinical_records": 42,
                "matched_records": 35,
                "unmatched_records": 7,
                "assigned_to": "Robert Chen",
                "started_date": now - timedelta(days=3),
                "completed_date": None,
                "target_completion_date": now + timedelta(days=10),
                "notes": "Ad-hoc reconciliation requested by medical monitor.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for t in tasks_data:
            self._reconciliation_tasks[t["id"]] = ReconciliationTask(**t)

        # --- 12 Discrepancy Records (4 per trial) ---
        discrepancies_data = [
            # EYLEA
            {
                "id": "DSR-00000001",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000002",
                "discrepancy_type": DiscrepancyType.DATE_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MAJOR,
                "subject_id": "SUBJ-1001",
                "ae_identifier": "AE-2024-0045",
                "safety_db_value": "2024-09-15",
                "clinical_db_value": "2024-09-12",
                "field_name": "onset_date",
                "description": "AE onset date differs by 3 days between safety and clinical databases.",
                "root_cause": "Data entry error in clinical database",
                "corrective_action": "Clinical DB corrected to match source document",
                "resolved": True,
                "resolved_date": now - timedelta(days=20),
                "resolved_by": "Sarah Mitchell",
                "identified_by": "Sarah Mitchell",
                "identified_date": now - timedelta(days=50),
                "notes": "Source document confirmed safety DB date is correct.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "DSR-00000002",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000002",
                "discrepancy_type": DiscrepancyType.MISSING_IN_SAFETY_DB,
                "discrepancy_severity": DiscrepancySeverity.CRITICAL,
                "subject_id": "SUBJ-1015",
                "ae_identifier": "AE-2024-0078",
                "safety_db_value": None,
                "clinical_db_value": "Grade 3 Headache",
                "field_name": "ae_term",
                "description": "SAE recorded in clinical DB but missing from safety database entirely.",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "David Park",
                "identified_date": now - timedelta(days=40),
                "notes": "Escalated to safety team for immediate entry.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "DSR-00000003",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000003",
                "discrepancy_type": DiscrepancyType.SEVERITY_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MINOR,
                "subject_id": "SUBJ-1022",
                "ae_identifier": "AE-2024-0102",
                "safety_db_value": "Moderate",
                "clinical_db_value": "Mild",
                "field_name": "severity",
                "description": "Severity grading inconsistent between databases.",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "David Park",
                "identified_date": now - timedelta(days=2),
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DSR-00000004",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000001",
                "discrepancy_type": DiscrepancyType.CODING_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.ADMINISTRATIVE,
                "subject_id": "SUBJ-1008",
                "ae_identifier": "AE-2024-0033",
                "safety_db_value": "MedDRA 10019211",
                "clinical_db_value": "MedDRA 10019213",
                "field_name": "meddra_code",
                "description": "Different MedDRA PT codes used for same AE term.",
                "root_cause": "Version mismatch between databases",
                "corrective_action": "Both updated to MedDRA v27.0",
                "resolved": True,
                "resolved_date": now - timedelta(days=135),
                "resolved_by": "Sarah Mitchell",
                "identified_by": "Sarah Mitchell",
                "identified_date": now - timedelta(days=145),
                "notes": "Coding harmonized across both systems.",
                "created_at": now - timedelta(days=145),
            },
            # DUPIXENT
            {
                "id": "DSR-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000006",
                "discrepancy_type": DiscrepancyType.MISSING_IN_CLINICAL_DB,
                "discrepancy_severity": DiscrepancySeverity.CRITICAL,
                "subject_id": "SUBJ-2010",
                "ae_identifier": "AE-2024-0155",
                "safety_db_value": "Anaphylaxis",
                "clinical_db_value": None,
                "field_name": "ae_term",
                "description": "Serious AE in safety DB not captured in clinical database CRF.",
                "root_cause": "Site failed to enter AE into EDC system",
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "Jennifer Lee",
                "identified_date": now - timedelta(days=80),
                "notes": "Protocol deviation filed. Site re-training scheduled.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DSR-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000006",
                "discrepancy_type": DiscrepancyType.CAUSALITY_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MAJOR,
                "subject_id": "SUBJ-2025",
                "ae_identifier": "AE-2024-0189",
                "safety_db_value": "Related",
                "clinical_db_value": "Not Related",
                "field_name": "causality_assessment",
                "description": "Investigator and safety assessments disagree on causality.",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "Jennifer Lee",
                "identified_date": now - timedelta(days=75),
                "notes": "Medical review requested.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DSR-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000007",
                "discrepancy_type": DiscrepancyType.DATE_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MINOR,
                "subject_id": "SUBJ-2040",
                "ae_identifier": "AE-2024-0210",
                "safety_db_value": "2024-11-20",
                "clinical_db_value": "2024-11-22",
                "field_name": "resolution_date",
                "description": "AE resolution date differs by 2 days.",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "Robert Chen",
                "identified_date": now - timedelta(days=8),
                "notes": None,
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "DSR-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000005",
                "discrepancy_type": DiscrepancyType.SEVERITY_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.INFORMATIONAL,
                "subject_id": "SUBJ-2003",
                "ae_identifier": "AE-2024-0120",
                "safety_db_value": "Severe",
                "clinical_db_value": "Moderate",
                "field_name": "severity",
                "description": "Severity mismatch noted during routine reconciliation.",
                "root_cause": "Investigator upgraded severity at follow-up visit",
                "corrective_action": "Clinical DB updated to reflect latest assessment",
                "resolved": True,
                "resolved_date": now - timedelta(days=160),
                "resolved_by": "Jennifer Lee",
                "identified_by": "Jennifer Lee",
                "identified_date": now - timedelta(days=165),
                "notes": "Resolved during standard review.",
                "created_at": now - timedelta(days=165),
            },
            # LIBTAYO
            {
                "id": "DSR-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000010",
                "discrepancy_type": DiscrepancyType.CAUSALITY_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MAJOR,
                "subject_id": "SUBJ-3015",
                "ae_identifier": "AE-2024-0280",
                "safety_db_value": "Possibly Related",
                "clinical_db_value": "Unlikely Related",
                "field_name": "causality_assessment",
                "description": "Discrepant causality assessment for immune-related AE.",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "Maria Santos",
                "identified_date": now - timedelta(days=25),
                "notes": "Pending adjudication committee review.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DSR-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000010",
                "discrepancy_type": DiscrepancyType.CODING_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.MINOR,
                "subject_id": "SUBJ-3022",
                "ae_identifier": "AE-2024-0295",
                "safety_db_value": "MedDRA 10037660",
                "clinical_db_value": "MedDRA 10037661",
                "field_name": "meddra_code",
                "description": "Preferred term code mismatch for rash event.",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "Maria Santos",
                "identified_date": now - timedelta(days=22),
                "notes": None,
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "DSR-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000009",
                "discrepancy_type": DiscrepancyType.MISSING_IN_SAFETY_DB,
                "discrepancy_severity": DiscrepancySeverity.MAJOR,
                "subject_id": "SUBJ-3005",
                "ae_identifier": "AE-2024-0250",
                "safety_db_value": None,
                "clinical_db_value": "Pneumonitis Grade 2",
                "field_name": "ae_term",
                "description": "Immune-related AE in clinical DB not found in safety system.",
                "root_cause": "Late reporting by investigator site",
                "corrective_action": "Expedited safety report filed",
                "resolved": True,
                "resolved_date": now - timedelta(days=100),
                "resolved_by": "Maria Santos",
                "identified_by": "Maria Santos",
                "identified_date": now - timedelta(days=115),
                "notes": "Resolved after expedited reporting.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "DSR-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000012",
                "discrepancy_type": DiscrepancyType.DATE_MISMATCH,
                "discrepancy_severity": DiscrepancySeverity.NOT_APPLICABLE,
                "subject_id": "SUBJ-3030",
                "ae_identifier": "AE-2024-0310",
                "safety_db_value": "2024-12-01",
                "clinical_db_value": "2024-12-03",
                "field_name": "onset_date",
                "description": "Minor onset date discrepancy under investigation.",
                "root_cause": None,
                "corrective_action": None,
                "resolved": False,
                "resolved_date": None,
                "resolved_by": None,
                "identified_by": "Robert Chen",
                "identified_date": now - timedelta(days=3),
                "notes": "Awaiting source document verification.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for d in discrepancies_data:
            self._discrepancy_records[d["id"]] = DiscrepancyRecord(**d)

        # --- 12 Line Item Comparisons (4 per trial) ---
        comparisons_data = [
            # EYLEA
            {
                "id": "LIC-00000001",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000002",
                "comparison_outcome": ComparisonOutcome.MATCHED,
                "subject_id": "SUBJ-1001",
                "ae_identifier": "AE-2024-0040",
                "safety_db_record_id": "ARG-00040",
                "clinical_db_record_id": "RAVE-00040",
                "ae_term_safety": "Headache",
                "ae_term_clinical": "Headache",
                "onset_date_safety": now - timedelta(days=100),
                "onset_date_clinical": now - timedelta(days=100),
                "severity_safety": "Mild",
                "severity_clinical": "Mild",
                "compared_by": "Sarah Mitchell",
                "comparison_date": now - timedelta(days=55),
                "discrepancy_count": 0,
                "notes": "Full match on all fields.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "LIC-00000002",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000002",
                "comparison_outcome": ComparisonOutcome.MISMATCHED,
                "subject_id": "SUBJ-1015",
                "ae_identifier": "AE-2024-0078",
                "safety_db_record_id": None,
                "clinical_db_record_id": "RAVE-00078",
                "ae_term_safety": None,
                "ae_term_clinical": "Grade 3 Headache",
                "onset_date_safety": None,
                "onset_date_clinical": now - timedelta(days=85),
                "severity_safety": None,
                "severity_clinical": "Severe",
                "compared_by": "David Park",
                "comparison_date": now - timedelta(days=38),
                "discrepancy_count": 1,
                "notes": "Missing in safety DB. Discrepancy DSR-00000002 created.",
                "created_at": now - timedelta(days=38),
            },
            {
                "id": "LIC-00000003",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000003",
                "comparison_outcome": ComparisonOutcome.PENDING_REVIEW,
                "subject_id": "SUBJ-1022",
                "ae_identifier": "AE-2024-0102",
                "safety_db_record_id": "ARG-00102",
                "clinical_db_record_id": "RAVE-00102",
                "ae_term_safety": "Nausea",
                "ae_term_clinical": "Nausea",
                "onset_date_safety": now - timedelta(days=15),
                "onset_date_clinical": now - timedelta(days=15),
                "severity_safety": "Moderate",
                "severity_clinical": "Mild",
                "compared_by": "David Park",
                "comparison_date": now - timedelta(days=1),
                "discrepancy_count": 1,
                "notes": "Severity mismatch under review.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "LIC-00000004",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000001",
                "comparison_outcome": ComparisonOutcome.PARTIAL_MATCH,
                "subject_id": "SUBJ-1008",
                "ae_identifier": "AE-2024-0033",
                "safety_db_record_id": "ARG-00033",
                "clinical_db_record_id": "RAVE-00033",
                "ae_term_safety": "Dizziness",
                "ae_term_clinical": "Dizziness",
                "onset_date_safety": now - timedelta(days=170),
                "onset_date_clinical": now - timedelta(days=170),
                "severity_safety": "Mild",
                "severity_clinical": "Mild",
                "compared_by": "Sarah Mitchell",
                "comparison_date": now - timedelta(days=145),
                "discrepancy_count": 1,
                "notes": "MedDRA coding mismatch only. AE terms identical.",
                "created_at": now - timedelta(days=145),
            },
            # DUPIXENT
            {
                "id": "LIC-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000006",
                "comparison_outcome": ComparisonOutcome.NOT_FOUND,
                "subject_id": "SUBJ-2010",
                "ae_identifier": "AE-2024-0155",
                "safety_db_record_id": "ARG-00155",
                "clinical_db_record_id": None,
                "ae_term_safety": "Anaphylaxis",
                "ae_term_clinical": None,
                "onset_date_safety": now - timedelta(days=110),
                "onset_date_clinical": None,
                "severity_safety": "Life-threatening",
                "severity_clinical": None,
                "compared_by": "Jennifer Lee",
                "comparison_date": now - timedelta(days=78),
                "discrepancy_count": 1,
                "notes": "Critical: SAE not in clinical DB.",
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "LIC-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000006",
                "comparison_outcome": ComparisonOutcome.MISMATCHED,
                "subject_id": "SUBJ-2025",
                "ae_identifier": "AE-2024-0189",
                "safety_db_record_id": "ARG-00189",
                "clinical_db_record_id": "VAULT-00189",
                "ae_term_safety": "Injection site reaction",
                "ae_term_clinical": "Injection site reaction",
                "onset_date_safety": now - timedelta(days=95),
                "onset_date_clinical": now - timedelta(days=95),
                "severity_safety": "Moderate",
                "severity_clinical": "Moderate",
                "compared_by": "Jennifer Lee",
                "comparison_date": now - timedelta(days=73),
                "discrepancy_count": 1,
                "notes": "Causality assessment mismatch.",
                "created_at": now - timedelta(days=73),
            },
            {
                "id": "LIC-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000007",
                "comparison_outcome": ComparisonOutcome.MATCHED,
                "subject_id": "SUBJ-2040",
                "ae_identifier": "AE-2024-0205",
                "safety_db_record_id": "ARG-00205",
                "clinical_db_record_id": "VAULT-00205",
                "ae_term_safety": "Conjunctivitis",
                "ae_term_clinical": "Conjunctivitis",
                "onset_date_safety": now - timedelta(days=30),
                "onset_date_clinical": now - timedelta(days=30),
                "severity_safety": "Mild",
                "severity_clinical": "Mild",
                "compared_by": "Robert Chen",
                "comparison_date": now - timedelta(days=6),
                "discrepancy_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "LIC-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000005",
                "comparison_outcome": ComparisonOutcome.EXCLUDED,
                "subject_id": "SUBJ-2001",
                "ae_identifier": "AE-2024-0115",
                "safety_db_record_id": "ARG-00115",
                "clinical_db_record_id": "VAULT-00115",
                "ae_term_safety": "Fatigue",
                "ae_term_clinical": "Fatigue",
                "onset_date_safety": now - timedelta(days=195),
                "onset_date_clinical": now - timedelta(days=195),
                "severity_safety": "Mild",
                "severity_clinical": "Mild",
                "compared_by": "Jennifer Lee",
                "comparison_date": now - timedelta(days=163),
                "discrepancy_count": 0,
                "notes": "Excluded from reconciliation scope per protocol amendment.",
                "created_at": now - timedelta(days=163),
            },
            # LIBTAYO
            {
                "id": "LIC-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000010",
                "comparison_outcome": ComparisonOutcome.MISMATCHED,
                "subject_id": "SUBJ-3015",
                "ae_identifier": "AE-2024-0280",
                "safety_db_record_id": "LS-00280",
                "clinical_db_record_id": "OC-00280",
                "ae_term_safety": "Colitis",
                "ae_term_clinical": "Colitis",
                "onset_date_safety": now - timedelta(days=50),
                "onset_date_clinical": now - timedelta(days=50),
                "severity_safety": "Severe",
                "severity_clinical": "Severe",
                "compared_by": "Maria Santos",
                "comparison_date": now - timedelta(days=23),
                "discrepancy_count": 1,
                "notes": "Causality assessment diverges.",
                "created_at": now - timedelta(days=23),
            },
            {
                "id": "LIC-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000010",
                "comparison_outcome": ComparisonOutcome.PARTIAL_MATCH,
                "subject_id": "SUBJ-3022",
                "ae_identifier": "AE-2024-0295",
                "safety_db_record_id": "LS-00295",
                "clinical_db_record_id": "OC-00295",
                "ae_term_safety": "Rash maculopapular",
                "ae_term_clinical": "Rash",
                "onset_date_safety": now - timedelta(days=45),
                "onset_date_clinical": now - timedelta(days=45),
                "severity_safety": "Moderate",
                "severity_clinical": "Moderate",
                "compared_by": "Maria Santos",
                "comparison_date": now - timedelta(days=20),
                "discrepancy_count": 2,
                "notes": "Term and coding mismatch.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "LIC-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000009",
                "comparison_outcome": ComparisonOutcome.MATCHED,
                "subject_id": "SUBJ-3005",
                "ae_identifier": "AE-2024-0245",
                "safety_db_record_id": "LS-00245",
                "clinical_db_record_id": "OC-00245",
                "ae_term_safety": "Hypothyroidism",
                "ae_term_clinical": "Hypothyroidism",
                "onset_date_safety": now - timedelta(days=130),
                "onset_date_clinical": now - timedelta(days=130),
                "severity_safety": "Mild",
                "severity_clinical": "Mild",
                "compared_by": "Maria Santos",
                "comparison_date": now - timedelta(days=112),
                "discrepancy_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=112),
            },
            {
                "id": "LIC-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000012",
                "comparison_outcome": ComparisonOutcome.PENDING_REVIEW,
                "subject_id": "SUBJ-3030",
                "ae_identifier": "AE-2024-0310",
                "safety_db_record_id": "LS-00310",
                "clinical_db_record_id": "OC-00310",
                "ae_term_safety": "Pruritus",
                "ae_term_clinical": "Pruritus",
                "onset_date_safety": now - timedelta(days=10),
                "onset_date_clinical": now - timedelta(days=8),
                "severity_safety": "Mild",
                "severity_clinical": "Mild",
                "compared_by": "Robert Chen",
                "comparison_date": now - timedelta(days=2),
                "discrepancy_count": 1,
                "notes": "Onset date difference under review.",
                "created_at": now - timedelta(days=2),
            },
        ]

        for c in comparisons_data:
            self._line_item_comparisons[c["id"]] = LineItemComparison(**c)

        # --- 12 Reconciliation Sign-Offs (4 per trial) ---
        signoffs_data = [
            # EYLEA
            {
                "id": "RSO-00000001",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000001",
                "sign_off_status": SignOffStatus.SIGNED_OFF,
                "sign_off_role": "Safety Physician",
                "signer_name": "Dr. Amanda Chen",
                "sign_off_date": now - timedelta(days=138),
                "open_discrepancies_at_signoff": 0,
                "resolved_discrepancies": 4,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": None,
                "notes": "All discrepancies resolved prior to sign-off.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "RSO-00000002",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000001",
                "sign_off_status": SignOffStatus.SIGNED_OFF,
                "sign_off_role": "Data Management Lead",
                "signer_name": "Sarah Mitchell",
                "sign_off_date": now - timedelta(days=139),
                "open_discrepancies_at_signoff": 0,
                "resolved_discrepancies": 4,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": None,
                "notes": None,
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "RSO-00000003",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000002",
                "sign_off_status": SignOffStatus.REJECTED,
                "sign_off_role": "Safety Physician",
                "signer_name": "Dr. Amanda Chen",
                "sign_off_date": None,
                "open_discrepancies_at_signoff": 3,
                "resolved_discrepancies": 1,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": "Critical discrepancy DSR-00000002 remains unresolved.",
                "next_review_date": now + timedelta(days=7),
                "notes": "Cannot sign off with missing SAE in safety database.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RSO-00000004",
                "trial_id": EYLEA_TRIAL,
                "reconciliation_task_id": "RCT-00000002",
                "sign_off_status": SignOffStatus.PENDING,
                "sign_off_role": "Data Management Lead",
                "signer_name": "Sarah Mitchell",
                "sign_off_date": None,
                "open_discrepancies_at_signoff": 3,
                "resolved_discrepancies": 1,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": now + timedelta(days=7),
                "notes": "Awaiting safety physician sign-off first.",
                "created_at": now - timedelta(days=10),
            },
            # DUPIXENT
            {
                "id": "RSO-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000005",
                "sign_off_status": SignOffStatus.SIGNED_OFF,
                "sign_off_role": "Pharmacovigilance Manager",
                "signer_name": "Dr. Lisa Wang",
                "sign_off_date": now - timedelta(days=153),
                "open_discrepancies_at_signoff": 0,
                "resolved_discrepancies": 7,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": None,
                "notes": "Clean reconciliation.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "RSO-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000006",
                "sign_off_status": SignOffStatus.CONDITIONAL,
                "sign_off_role": "Safety Physician",
                "signer_name": "Dr. James Wright",
                "sign_off_date": now - timedelta(days=30),
                "open_discrepancies_at_signoff": 5,
                "resolved_discrepancies": 8,
                "waived_discrepancies": 2,
                "conditions": "Conditional upon resolution of DSR-00000005 within 14 days.",
                "rejection_reason": None,
                "next_review_date": now - timedelta(days=16),
                "notes": "Conditional sign-off granted with stipulations.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "RSO-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000008",
                "sign_off_status": SignOffStatus.SIGNED_OFF,
                "sign_off_role": "Clinical Data Manager",
                "signer_name": "Jennifer Lee",
                "sign_off_date": now - timedelta(days=253),
                "open_discrepancies_at_signoff": 0,
                "resolved_discrepancies": 0,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": None,
                "notes": "Baseline period - no discrepancies.",
                "created_at": now - timedelta(days=255),
            },
            {
                "id": "RSO-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "reconciliation_task_id": "RCT-00000006",
                "sign_off_status": SignOffStatus.DEFERRED,
                "sign_off_role": "Quality Assurance",
                "signer_name": "Patricia Kim",
                "sign_off_date": None,
                "open_discrepancies_at_signoff": 5,
                "resolved_discrepancies": 8,
                "waived_discrepancies": 2,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": now + timedelta(days=14),
                "notes": "Deferred pending CAPA closure for DSR-00000005.",
                "created_at": now - timedelta(days=20),
            },
            # LIBTAYO
            {
                "id": "RSO-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000009",
                "sign_off_status": SignOffStatus.SIGNED_OFF,
                "sign_off_role": "Safety Physician",
                "signer_name": "Dr. Michael Torres",
                "sign_off_date": now - timedelta(days=103),
                "open_discrepancies_at_signoff": 0,
                "resolved_discrepancies": 6,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": None,
                "notes": "All discrepancies resolved.",
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "RSO-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000010",
                "sign_off_status": SignOffStatus.PENDING,
                "sign_off_role": "Safety Physician",
                "signer_name": "Dr. Michael Torres",
                "sign_off_date": None,
                "open_discrepancies_at_signoff": 4,
                "resolved_discrepancies": 0,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": now + timedelta(days=5),
                "notes": "Awaiting discrepancy resolution.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "RSO-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000009",
                "sign_off_status": SignOffStatus.REVOKED,
                "sign_off_role": "Data Management Lead",
                "signer_name": "Maria Santos",
                "sign_off_date": now - timedelta(days=108),
                "open_discrepancies_at_signoff": 1,
                "resolved_discrepancies": 5,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": now - timedelta(days=95),
                "notes": "Sign-off revoked after discovery of late-reported AE.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "RSO-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "reconciliation_task_id": "RCT-00000010",
                "sign_off_status": SignOffStatus.PENDING,
                "sign_off_role": "Quality Assurance",
                "signer_name": "Patricia Kim",
                "sign_off_date": None,
                "open_discrepancies_at_signoff": 4,
                "resolved_discrepancies": 0,
                "waived_discrepancies": 0,
                "conditions": None,
                "rejection_reason": None,
                "next_review_date": now + timedelta(days=10),
                "notes": None,
                "created_at": now - timedelta(days=8),
            },
        ]

        for s in signoffs_data:
            self._reconciliation_sign_offs[s["id"]] = ReconciliationSignOff(**s)

    # ------------------------------------------------------------------
    # Reconciliation Tasks
    # ------------------------------------------------------------------

    def list_reconciliation_tasks(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ReconciliationTask]:
        """List reconciliation tasks with optional trial_id filter."""
        with self._lock:
            result = list(self._reconciliation_tasks.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]

        return sorted(result, key=lambda t: t.created_at, reverse=True)

    def get_reconciliation_task(self, task_id: str) -> ReconciliationTask | None:
        """Get a single reconciliation task by ID."""
        with self._lock:
            return self._reconciliation_tasks.get(task_id)

    def create_reconciliation_task(self, payload: ReconciliationTaskCreate) -> ReconciliationTask:
        """Create a new reconciliation task."""
        now = datetime.now(timezone.utc)
        task_id = f"RCT-{uuid4().hex[:8].upper()}"
        task = ReconciliationTask(
            id=task_id,
            trial_id=payload.trial_id,
            reconciliation_status=payload.reconciliation_status,
            reconciliation_period_start=payload.reconciliation_period_start,
            reconciliation_period_end=payload.reconciliation_period_end,
            safety_db_name=payload.safety_db_name,
            clinical_db_name=payload.clinical_db_name,
            total_safety_records=0,
            total_clinical_records=0,
            matched_records=0,
            unmatched_records=0,
            assigned_to=payload.assigned_to,
            started_date=None,
            completed_date=None,
            target_completion_date=payload.target_completion_date,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._reconciliation_tasks[task_id] = task
        logger.info("Created reconciliation task %s for trial %s", task_id, payload.trial_id)
        return task

    def update_reconciliation_task(
        self, task_id: str, payload: ReconciliationTaskUpdate
    ) -> ReconciliationTask | None:
        """Update an existing reconciliation task."""
        with self._lock:
            existing = self._reconciliation_tasks.get(task_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReconciliationTask(**data)
            self._reconciliation_tasks[task_id] = updated
        return updated

    def delete_reconciliation_task(self, task_id: str) -> bool:
        """Delete a reconciliation task. Returns True if deleted."""
        with self._lock:
            if task_id in self._reconciliation_tasks:
                del self._reconciliation_tasks[task_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Discrepancy Records
    # ------------------------------------------------------------------

    def list_discrepancy_records(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DiscrepancyRecord]:
        """List discrepancy records with optional trial_id filter."""
        with self._lock:
            result = list(self._discrepancy_records.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_discrepancy_record(self, record_id: str) -> DiscrepancyRecord | None:
        """Get a single discrepancy record by ID."""
        with self._lock:
            return self._discrepancy_records.get(record_id)

    def create_discrepancy_record(self, payload: DiscrepancyRecordCreate) -> DiscrepancyRecord:
        """Create a new discrepancy record."""
        now = datetime.now(timezone.utc)
        record_id = f"DSR-{uuid4().hex[:8].upper()}"
        record = DiscrepancyRecord(
            id=record_id,
            trial_id=payload.trial_id,
            reconciliation_task_id=payload.reconciliation_task_id,
            discrepancy_type=payload.discrepancy_type,
            discrepancy_severity=payload.discrepancy_severity,
            subject_id=payload.subject_id,
            ae_identifier=payload.ae_identifier,
            safety_db_value=None,
            clinical_db_value=None,
            field_name=payload.field_name,
            description=payload.description,
            root_cause=None,
            corrective_action=None,
            resolved=False,
            resolved_date=None,
            resolved_by=None,
            identified_by=payload.identified_by,
            identified_date=payload.identified_date,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._discrepancy_records[record_id] = record
        logger.info("Created discrepancy record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_discrepancy_record(
        self, record_id: str, payload: DiscrepancyRecordUpdate
    ) -> DiscrepancyRecord | None:
        """Update an existing discrepancy record."""
        with self._lock:
            existing = self._discrepancy_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DiscrepancyRecord(**data)
            self._discrepancy_records[record_id] = updated
        return updated

    def delete_discrepancy_record(self, record_id: str) -> bool:
        """Delete a discrepancy record. Returns True if deleted."""
        with self._lock:
            if record_id in self._discrepancy_records:
                del self._discrepancy_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Line Item Comparisons
    # ------------------------------------------------------------------

    def list_line_item_comparisons(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[LineItemComparison]:
        """List line item comparisons with optional trial_id filter."""
        with self._lock:
            result = list(self._line_item_comparisons.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_line_item_comparison(self, comparison_id: str) -> LineItemComparison | None:
        """Get a single line item comparison by ID."""
        with self._lock:
            return self._line_item_comparisons.get(comparison_id)

    def create_line_item_comparison(self, payload: LineItemComparisonCreate) -> LineItemComparison:
        """Create a new line item comparison."""
        now = datetime.now(timezone.utc)
        comparison_id = f"LIC-{uuid4().hex[:8].upper()}"
        comparison = LineItemComparison(
            id=comparison_id,
            trial_id=payload.trial_id,
            reconciliation_task_id=payload.reconciliation_task_id,
            comparison_outcome=payload.comparison_outcome,
            subject_id=payload.subject_id,
            ae_identifier=payload.ae_identifier,
            safety_db_record_id=None,
            clinical_db_record_id=None,
            ae_term_safety=None,
            ae_term_clinical=None,
            onset_date_safety=None,
            onset_date_clinical=None,
            severity_safety=None,
            severity_clinical=None,
            compared_by=payload.compared_by,
            comparison_date=payload.comparison_date,
            discrepancy_count=0,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._line_item_comparisons[comparison_id] = comparison
        logger.info("Created line item comparison %s for trial %s", comparison_id, payload.trial_id)
        return comparison

    def update_line_item_comparison(
        self, comparison_id: str, payload: LineItemComparisonUpdate
    ) -> LineItemComparison | None:
        """Update an existing line item comparison."""
        with self._lock:
            existing = self._line_item_comparisons.get(comparison_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LineItemComparison(**data)
            self._line_item_comparisons[comparison_id] = updated
        return updated

    def delete_line_item_comparison(self, comparison_id: str) -> bool:
        """Delete a line item comparison. Returns True if deleted."""
        with self._lock:
            if comparison_id in self._line_item_comparisons:
                del self._line_item_comparisons[comparison_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Reconciliation Sign-Offs
    # ------------------------------------------------------------------

    def list_reconciliation_sign_offs(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ReconciliationSignOff]:
        """List reconciliation sign-offs with optional trial_id filter."""
        with self._lock:
            result = list(self._reconciliation_sign_offs.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_reconciliation_sign_off(self, sign_off_id: str) -> ReconciliationSignOff | None:
        """Get a single reconciliation sign-off by ID."""
        with self._lock:
            return self._reconciliation_sign_offs.get(sign_off_id)

    def create_reconciliation_sign_off(
        self, payload: ReconciliationSignOffCreate
    ) -> ReconciliationSignOff:
        """Create a new reconciliation sign-off."""
        now = datetime.now(timezone.utc)
        sign_off_id = f"RSO-{uuid4().hex[:8].upper()}"
        sign_off = ReconciliationSignOff(
            id=sign_off_id,
            trial_id=payload.trial_id,
            reconciliation_task_id=payload.reconciliation_task_id,
            sign_off_status=payload.sign_off_status,
            sign_off_role=payload.sign_off_role,
            signer_name=payload.signer_name,
            sign_off_date=None,
            open_discrepancies_at_signoff=0,
            resolved_discrepancies=0,
            waived_discrepancies=0,
            conditions=None,
            rejection_reason=None,
            next_review_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._reconciliation_sign_offs[sign_off_id] = sign_off
        logger.info("Created reconciliation sign-off %s for trial %s", sign_off_id, payload.trial_id)
        return sign_off

    def update_reconciliation_sign_off(
        self, sign_off_id: str, payload: ReconciliationSignOffUpdate
    ) -> ReconciliationSignOff | None:
        """Update an existing reconciliation sign-off."""
        with self._lock:
            existing = self._reconciliation_sign_offs.get(sign_off_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReconciliationSignOff(**data)
            self._reconciliation_sign_offs[sign_off_id] = updated
        return updated

    def delete_reconciliation_sign_off(self, sign_off_id: str) -> bool:
        """Delete a reconciliation sign-off. Returns True if deleted."""
        with self._lock:
            if sign_off_id in self._reconciliation_sign_offs:
                del self._reconciliation_sign_offs[sign_off_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(
        self,
        *,
        trial_id: str | None = None,
    ) -> AdverseEventReconciliationMetrics:
        """Compute aggregated adverse event reconciliation metrics."""
        with self._lock:
            tasks = list(self._reconciliation_tasks.values())
            discrepancies = list(self._discrepancy_records.values())
            comparisons = list(self._line_item_comparisons.values())
            sign_offs = list(self._reconciliation_sign_offs.values())

        if trial_id is not None:
            tasks = [t for t in tasks if t.trial_id == trial_id]
            discrepancies = [d for d in discrepancies if d.trial_id == trial_id]
            comparisons = [c for c in comparisons if c.trial_id == trial_id]
            sign_offs = [s for s in sign_offs if s.trial_id == trial_id]

        # Tasks by status
        tasks_by_status: dict[str, int] = {}
        for t in tasks:
            key = t.reconciliation_status.value
            tasks_by_status[key] = tasks_by_status.get(key, 0) + 1

        # Discrepancies by type
        discrepancies_by_type: dict[str, int] = {}
        for d in discrepancies:
            key = d.discrepancy_type.value
            discrepancies_by_type[key] = discrepancies_by_type.get(key, 0) + 1

        # Discrepancies by severity
        discrepancies_by_severity: dict[str, int] = {}
        for d in discrepancies:
            key = d.discrepancy_severity.value
            discrepancies_by_severity[key] = discrepancies_by_severity.get(key, 0) + 1

        # Resolution rate
        total_disc = len(discrepancies)
        resolved_disc = sum(1 for d in discrepancies if d.resolved)
        resolution_rate = round(
            (resolved_disc / total_disc * 100.0) if total_disc > 0 else 0.0, 1
        )

        # Comparisons by outcome
        comparisons_by_outcome: dict[str, int] = {}
        for c in comparisons:
            key = c.comparison_outcome.value
            comparisons_by_outcome[key] = comparisons_by_outcome.get(key, 0) + 1

        # Match rate
        total_comp = len(comparisons)
        matched_comp = sum(
            1 for c in comparisons if c.comparison_outcome == ComparisonOutcome.MATCHED
        )
        match_rate = round(
            (matched_comp / total_comp * 100.0) if total_comp > 0 else 0.0, 1
        )

        # Sign-offs by status
        sign_offs_by_status: dict[str, int] = {}
        for s in sign_offs:
            key = s.sign_off_status.value
            sign_offs_by_status[key] = sign_offs_by_status.get(key, 0) + 1

        return AdverseEventReconciliationMetrics(
            total_reconciliation_tasks=len(tasks),
            tasks_by_status=tasks_by_status,
            total_discrepancies=total_disc,
            discrepancies_by_type=discrepancies_by_type,
            discrepancies_by_severity=discrepancies_by_severity,
            discrepancy_resolution_rate=resolution_rate,
            total_comparisons=total_comp,
            comparisons_by_outcome=comparisons_by_outcome,
            match_rate=match_rate,
            total_sign_offs=len(sign_offs),
            sign_offs_by_status=sign_offs_by_status,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AdverseEventReconciliationService | None = None
_instance_lock = threading.Lock()


def get_adverse_event_reconciliation_service() -> AdverseEventReconciliationService:
    """Return the singleton AdverseEventReconciliationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AdverseEventReconciliationService()
    return _instance


def reset_adverse_event_reconciliation_service() -> AdverseEventReconciliationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = AdverseEventReconciliationService()
    return _instance
