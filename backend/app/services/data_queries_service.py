"""Data Queries & Discrepancy Management Service (CLINICAL-18).

Manages clinical data query lifecycle: query generation and routing, response
tracking, auto-query rule engine, query aging reports, discrepancy resolution
workflow, bulk operations, and query metrics for CRO data management.

Usage:
    from app.services.data_queries_service import get_data_queries_service

    svc = get_data_queries_service()
    queries = svc.list_queries()
    metrics = svc.get_query_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.data_queries import (
    AgingBucket,
    AutoQueryRule,
    AutoQueryRuleCreate,
    AutoQueryRuleUpdate,
    BulkAssignRequest,
    BulkCloseRequest,
    BulkOperationResult,
    DataQuery,
    DataQueryCreate,
    DataQueryUpdate,
    DiscrepancyResolution,
    QueryAgingReport,
    QueryCategory,
    QueryCloseRequest,
    QueryMetrics,
    QueryPriority,
    QueryResponse,
    QueryResponseCreate,
    QuerySource,
    QueryStatus,
    ResolutionType,
    SiteQuerySummary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DataQueriesService:
    """In-memory Data Queries & Discrepancy Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._queries: dict[str, DataQuery] = {}
        self._responses: dict[str, QueryResponse] = {}
        self._auto_rules: dict[str, AutoQueryRule] = {}
        self._resolutions: dict[str, DiscrepancyResolution] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic data query scenarios across sites/trials."""
        now = datetime.now(timezone.utc)

        # --- 25 Data Queries ---
        queries_data = [
            {
                "id": "DQ-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "visit_name": "Screening",
                "form_name": "Informed Consent",
                "field_name": "consent_date",
                "query_text": "Informed consent date is missing. Please provide the date the subject signed the informed consent form.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.MISSING_DATA,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Site Coordinator",
                "auto_rule_id": "AQR-001",
                "opened_date": now - timedelta(days=12),
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "DQ-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1002",
                "visit_name": "Visit 2",
                "form_name": "Vital Signs",
                "field_name": "systolic_bp",
                "query_text": "Systolic blood pressure value of 280 mmHg appears out of range. Please verify or correct.",
                "status": QueryStatus.ANSWERED,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.OUT_OF_RANGE,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Investigator",
                "auto_rule_id": "AQR-003",
                "opened_date": now - timedelta(days=20),
                "answered_date": now - timedelta(days=15),
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "DQ-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-1010",
                "visit_name": "Visit 4",
                "form_name": "Adverse Events",
                "field_name": "ae_onset_date",
                "query_text": "AE onset date is before the subject's first dose date. Please verify the onset date.",
                "status": QueryStatus.CLOSED,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.INCONSISTENT,
                "source": QuerySource.SDV,
                "assigned_to": "Data Manager",
                "opened_date": now - timedelta(days=45),
                "answered_date": now - timedelta(days=40),
                "closed_date": now - timedelta(days=35),
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DQ-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-1020",
                "visit_name": "Visit 3",
                "form_name": "Concomitant Medications",
                "field_name": "medication_name",
                "query_text": "Concomitant medication 'asprin' appears to be misspelled. Please verify the medication name and WHO Drug coding.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.MEDIUM,
                "category": QueryCategory.CODING_ERROR,
                "source": QuerySource.MEDICAL_REVIEW,
                "assigned_to": "Site Coordinator",
                "opened_date": now - timedelta(days=8),
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "DQ-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2001",
                "visit_name": "Screening",
                "form_name": "Demographics",
                "field_name": "date_of_birth",
                "query_text": "Subject age calculated from date of birth does not meet eligibility criteria (18-75 years). Please verify date of birth.",
                "status": QueryStatus.REQUERIED,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.INCONSISTENT,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Investigator",
                "auto_rule_id": "AQR-005",
                "opened_date": now - timedelta(days=25),
                "answered_date": now - timedelta(days=18),
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DQ-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-2010",
                "visit_name": "Visit 1",
                "form_name": "Lab Results",
                "field_name": "creatinine",
                "query_text": "Serum creatinine value of 8.5 mg/dL is significantly above normal range (0.7-1.3). Please confirm this value against source documents.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.OUT_OF_RANGE,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Investigator",
                "auto_rule_id": "AQR-004",
                "opened_date": now - timedelta(days=5),
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DQ-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-2011",
                "visit_name": "Visit 2",
                "form_name": "Efficacy Assessment",
                "field_name": "eczema_score",
                "query_text": "EASI score is missing for this visit. This is a primary efficacy endpoint and must be completed.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.MISSING_DATA,
                "source": QuerySource.MANUAL,
                "assigned_to": "Site Coordinator",
                "opened_date": now - timedelta(days=3),
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DQ-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-2020",
                "visit_name": "Visit 5",
                "form_name": "Study Drug Log",
                "field_name": "dose_date",
                "query_text": "Study drug administration date is after the visit date. Please verify the dosing date.",
                "status": QueryStatus.ANSWERED,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.INCONSISTENT,
                "source": QuerySource.SDV,
                "assigned_to": "Data Manager",
                "opened_date": now - timedelta(days=18),
                "answered_date": now - timedelta(days=10),
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "DQ-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-3001",
                "visit_name": "Screening",
                "form_name": "Informed Consent",
                "field_name": "consent_version",
                "query_text": "Subject was consented using ICF version 2.0, but the current approved version is 3.0. Please clarify if re-consent was obtained.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.CONSENT,
                "source": QuerySource.SDV,
                "assigned_to": "Investigator",
                "opened_date": now - timedelta(days=15),
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "DQ-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-3010",
                "visit_name": "Visit 3",
                "form_name": "Protocol Deviations",
                "field_name": "deviation_description",
                "query_text": "Protocol deviation reported but description field is empty. Please provide details of the deviation.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.MISSING_DATA,
                "source": QuerySource.MANUAL,
                "assigned_to": "Site Coordinator",
                "opened_date": now - timedelta(days=6),
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "DQ-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-3011",
                "visit_name": "Visit 1",
                "form_name": "Medical History",
                "field_name": "condition_code",
                "query_text": "MedDRA coding for 'heart condition' is too vague. Please provide a more specific preferred term for accurate coding.",
                "status": QueryStatus.ANSWERED,
                "priority": QueryPriority.MEDIUM,
                "category": QueryCategory.CODING_ERROR,
                "source": QuerySource.MEDICAL_REVIEW,
                "assigned_to": "Medical Coder",
                "opened_date": now - timedelta(days=22),
                "answered_date": now - timedelta(days=14),
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "DQ-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-3020",
                "visit_name": "Visit 2",
                "form_name": "Tumor Assessment",
                "field_name": "lesion_measurement",
                "query_text": "Target lesion measurement decreased from 45mm to 4mm between visits. Please verify this is not a data entry error.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.OUT_OF_RANGE,
                "source": QuerySource.MANUAL,
                "assigned_to": "Investigator",
                "opened_date": now - timedelta(days=10),
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DQ-013",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-1030",
                "visit_name": "Visit 6",
                "form_name": "Visual Acuity",
                "field_name": "bcva_score",
                "query_text": "BCVA score of 120 exceeds the maximum possible score of 100 letters. Please correct.",
                "status": QueryStatus.CLOSED,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.OUT_OF_RANGE,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Site Coordinator",
                "auto_rule_id": "AQR-003",
                "opened_date": now - timedelta(days=30),
                "answered_date": now - timedelta(days=25),
                "closed_date": now - timedelta(days=22),
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DQ-014",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-1040",
                "visit_name": "Visit 2",
                "form_name": "Vital Signs",
                "field_name": "heart_rate",
                "query_text": "Heart rate recorded as 0 bpm. Please verify this value.",
                "status": QueryStatus.CLOSED,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.OUT_OF_RANGE,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Investigator",
                "auto_rule_id": "AQR-003",
                "opened_date": now - timedelta(days=40),
                "answered_date": now - timedelta(days=38),
                "closed_date": now - timedelta(days=36),
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "DQ-015",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-2030",
                "visit_name": "Visit 4",
                "form_name": "Lab Results",
                "field_name": "hemoglobin",
                "query_text": "Hemoglobin value changed from 14.2 to 7.1 g/dL between visits without an associated AE. Please verify.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.INCONSISTENT,
                "source": QuerySource.MEDICAL_REVIEW,
                "assigned_to": "Investigator",
                "opened_date": now - timedelta(days=4),
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "DQ-016",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-3030",
                "visit_name": "Visit 1",
                "form_name": "Inclusion/Exclusion",
                "field_name": "exclusion_criterion_7",
                "query_text": "Subject appears to meet exclusion criterion #7 (prior anti-PD-1 therapy) based on medical history. Please clarify.",
                "status": QueryStatus.CANCELLED,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.PROTOCOL_DEVIATION,
                "source": QuerySource.MEDICAL_REVIEW,
                "assigned_to": "Investigator",
                "opened_date": now - timedelta(days=35),
                "closed_date": now - timedelta(days=30),
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "DQ-017",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-1011",
                "visit_name": "Visit 3",
                "form_name": "OCT Assessment",
                "field_name": "central_subfield_thickness",
                "query_text": "CST measurement missing for this visit. OCT assessment is required per protocol.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.MISSING_DATA,
                "source": QuerySource.MANUAL,
                "assigned_to": "Site Coordinator",
                "opened_date": now - timedelta(days=2),
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DQ-018",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-2002",
                "visit_name": "Visit 6",
                "form_name": "Adverse Events",
                "field_name": "ae_severity",
                "query_text": "AE severity is marked as 'Mild' but the subject was hospitalized. Please reconcile severity with outcome.",
                "status": QueryStatus.ANSWERED,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.INCONSISTENT,
                "source": QuerySource.MEDICAL_REVIEW,
                "assigned_to": "Investigator",
                "opened_date": now - timedelta(days=16),
                "answered_date": now - timedelta(days=9),
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "DQ-019",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-3040",
                "visit_name": "Screening",
                "form_name": "Informed Consent",
                "field_name": "consent_date",
                "query_text": "Informed consent date is after the date of first study procedure. Consent must be obtained before any study procedures.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.CONSENT,
                "source": QuerySource.SDV,
                "assigned_to": "Investigator",
                "opened_date": now - timedelta(days=11),
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "DQ-020",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-1050",
                "visit_name": "Visit 5",
                "form_name": "Injection Log",
                "field_name": "injection_eye",
                "query_text": "Injection eye recorded as 'Left' but the subject is enrolled for treatment of the right eye. Please verify.",
                "status": QueryStatus.CLOSED,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.PROTOCOL_DEVIATION,
                "source": QuerySource.SDV,
                "assigned_to": "Investigator",
                "opened_date": now - timedelta(days=50),
                "answered_date": now - timedelta(days=45),
                "closed_date": now - timedelta(days=42),
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "DQ-021",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-2040",
                "visit_name": "Visit 3",
                "form_name": "IGA Score",
                "field_name": "iga_value",
                "query_text": "IGA score field is blank. This is a key secondary endpoint and must be completed.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.MISSING_DATA,
                "source": QuerySource.MANUAL,
                "assigned_to": "Site Coordinator",
                "opened_date": now - timedelta(days=7),
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DQ-022",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-3021",
                "visit_name": "Visit 4",
                "form_name": "Lab Results",
                "field_name": "alt_value",
                "query_text": "ALT value of 450 U/L exceeds 10x ULN. Was a hepatic event AE reported? Please verify and report if applicable.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.CRITICAL,
                "category": QueryCategory.OUT_OF_RANGE,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Investigator",
                "auto_rule_id": "AQR-004",
                "opened_date": now - timedelta(days=1),
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "DQ-023",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-1021",
                "visit_name": "Visit 7",
                "form_name": "Adverse Events",
                "field_name": "ae_end_date",
                "query_text": "AE end date is before AE start date. Please correct the dates.",
                "status": QueryStatus.CLOSED,
                "priority": QueryPriority.MEDIUM,
                "category": QueryCategory.INCONSISTENT,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Site Coordinator",
                "auto_rule_id": "AQR-006",
                "opened_date": now - timedelta(days=28),
                "answered_date": now - timedelta(days=24),
                "closed_date": now - timedelta(days=20),
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "DQ-024",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-2050",
                "visit_name": "Visit 2",
                "form_name": "Study Drug Log",
                "field_name": "batch_number",
                "query_text": "Study drug batch number does not match inventory records. Please verify the batch number administered.",
                "status": QueryStatus.OPEN,
                "priority": QueryPriority.MEDIUM,
                "category": QueryCategory.INCONSISTENT,
                "source": QuerySource.SDV,
                "assigned_to": "Pharmacist",
                "opened_date": now - timedelta(days=9),
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "DQ-025",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-3050",
                "visit_name": "Visit 1",
                "form_name": "ECG",
                "field_name": "qtcf_interval",
                "query_text": "QTcF interval of 520 ms exceeds protocol-defined threshold of 500 ms. Was this reported as an AE?",
                "status": QueryStatus.ANSWERED,
                "priority": QueryPriority.HIGH,
                "category": QueryCategory.OUT_OF_RANGE,
                "source": QuerySource.AUTO_RULE,
                "assigned_to": "Investigator",
                "auto_rule_id": "AQR-004",
                "opened_date": now - timedelta(days=14),
                "answered_date": now - timedelta(days=7),
                "created_at": now - timedelta(days=14),
            },
        ]

        for q_data in queries_data:
            self._queries[q_data["id"]] = DataQuery(**q_data)

        # --- Responses for answered/closed queries ---
        responses_data = [
            {
                "id": "QR-001",
                "query_id": "DQ-002",
                "responder": "Dr. Sarah Chen, Investigator",
                "response_text": "Confirmed: the systolic BP of 280 mmHg was correctly recorded. Patient experienced a hypertensive crisis and was managed with IV labetalol. AE has been reported.",
                "attachments": ["bp_source_doc.pdf"],
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "QR-002",
                "query_id": "DQ-003",
                "responder": "Maria Lopez, Site Coordinator",
                "response_text": "AE onset date has been corrected from 2025-12-01 to 2026-01-15. The original entry was a typographical error. Source document attached.",
                "attachments": ["ae_source_verification.pdf"],
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "QR-003",
                "query_id": "DQ-005",
                "responder": "Dr. James Wilson, Investigator",
                "response_text": "Date of birth was incorrectly entered as 1940 instead of 1960. Subject is 65 years old and meets criteria.",
                "attachments": [],
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "QR-004",
                "query_id": "DQ-005",
                "responder": "Data Manager",
                "response_text": "Re-queried: The correction was applied but the calculated age still shows 85. Please re-verify the year of birth.",
                "attachments": [],
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "QR-005",
                "query_id": "DQ-008",
                "responder": "Jennifer Park, Site Coordinator",
                "response_text": "The dose date has been corrected. Subject received study drug on the visit date (Jan 10) not Jan 12 as originally recorded.",
                "attachments": ["dosing_log_corrected.pdf"],
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "QR-006",
                "query_id": "DQ-011",
                "responder": "Dr. Robert Kim, Medical Coder",
                "response_text": "Condition has been recoded to MedDRA PT 'Congestive heart failure' (SOC: Cardiac disorders). Verified with site.",
                "attachments": [],
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "QR-007",
                "query_id": "DQ-013",
                "responder": "Tom Harris, Site Coordinator",
                "response_text": "BCVA score has been corrected to 82 letters. The original entry of 120 was a data entry error.",
                "attachments": [],
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "QR-008",
                "query_id": "DQ-014",
                "responder": "Dr. Emily Zhang, Investigator",
                "response_text": "Heart rate has been corrected to 72 bpm. The field was inadvertently left as 0 during data entry.",
                "attachments": ["vitals_source.pdf"],
                "created_at": now - timedelta(days=38),
            },
            {
                "id": "QR-009",
                "query_id": "DQ-018",
                "responder": "Dr. Michael Brown, Investigator",
                "response_text": "Severity has been changed to 'Severe'. The hospitalization was related to this AE. SAE form has been submitted.",
                "attachments": ["sae_form.pdf"],
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "QR-010",
                "query_id": "DQ-020",
                "responder": "Dr. Anna White, Investigator",
                "response_text": "Confirmed this was a data entry error. Injection was administered to the right eye as per protocol. CRF has been corrected.",
                "attachments": [],
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "QR-011",
                "query_id": "DQ-023",
                "responder": "Linda Martinez, Site Coordinator",
                "response_text": "AE dates have been corrected. End date was entered as start date and vice versa. Corrected: start 2025-12-10, end 2025-12-18.",
                "attachments": [],
                "created_at": now - timedelta(days=24),
            },
            {
                "id": "QR-012",
                "query_id": "DQ-025",
                "responder": "Dr. David Lee, Investigator",
                "response_text": "QTcF prolongation has been reported as an AE (Grade 2). Dose was held and repeat ECG performed at 48h showed normalization.",
                "attachments": ["ecg_follow_up.pdf"],
                "created_at": now - timedelta(days=7),
            },
        ]

        for r_data in responses_data:
            resp = QueryResponse(**r_data)
            self._responses[resp.id] = resp
            # Attach to parent query
            q = self._queries.get(resp.query_id)
            if q:
                updated = q.model_dump()
                updated["responses"] = list(q.responses) + [resp]
                self._queries[q.id] = DataQuery(**updated)

        # --- Resolutions for closed queries ---
        resolutions_data = [
            {
                "query_id": "DQ-003",
                "resolution_type": ResolutionType.DATA_CORRECTED,
                "resolution_notes": "AE onset date corrected per source document verification.",
                "resolved_by": "Sarah Mitchell, CRA",
                "resolved_date": now - timedelta(days=35),
            },
            {
                "query_id": "DQ-013",
                "resolution_type": ResolutionType.DATA_CORRECTED,
                "resolution_notes": "BCVA score corrected from 120 to 82 letters. Data entry error confirmed.",
                "resolved_by": "David Park, Data Manager",
                "resolved_date": now - timedelta(days=22),
            },
            {
                "query_id": "DQ-014",
                "resolution_type": ResolutionType.DATA_CORRECTED,
                "resolution_notes": "Heart rate corrected from 0 to 72 bpm. Inadvertent omission during data entry.",
                "resolved_by": "Jennifer Lee, CRA",
                "resolved_date": now - timedelta(days=36),
            },
            {
                "query_id": "DQ-016",
                "resolution_type": ResolutionType.QUERY_WITHDRAWN,
                "resolution_notes": "Query cancelled - medical history review confirmed no prior anti-PD-1 therapy. Initial flag was based on incomplete data.",
                "resolved_by": "Dr. Lisa Chang, Medical Monitor",
                "resolved_date": now - timedelta(days=30),
            },
            {
                "query_id": "DQ-020",
                "resolution_type": ResolutionType.DATA_CORRECTED,
                "resolution_notes": "Injection eye corrected to 'Right' per protocol and source documents.",
                "resolved_by": "Sarah Mitchell, CRA",
                "resolved_date": now - timedelta(days=42),
            },
            {
                "query_id": "DQ-023",
                "resolution_type": ResolutionType.DATA_CORRECTED,
                "resolution_notes": "AE dates corrected: start and end dates were swapped in the original entry.",
                "resolved_by": "David Park, Data Manager",
                "resolved_date": now - timedelta(days=20),
            },
        ]

        for res_data in resolutions_data:
            res = DiscrepancyResolution(**res_data)
            self._resolutions[res.query_id] = res

        # --- 8 Auto-Query Rules ---
        rules_data = [
            {
                "id": "AQR-001",
                "rule_name": "Missing Informed Consent Date",
                "condition": "consent_date IS NULL",
                "form": "Informed Consent",
                "field": "consent_date",
                "message_template": "Informed consent date is missing for subject {subject_id}. Please provide the date the subject signed the informed consent form.",
                "category": QueryCategory.CONSENT,
                "priority": QueryPriority.CRITICAL,
                "active": True,
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AQR-002",
                "rule_name": "Missing Primary Endpoint",
                "condition": "primary_endpoint_value IS NULL AND visit_type = 'assessment'",
                "form": "Efficacy Assessment",
                "field": "primary_endpoint",
                "message_template": "Primary efficacy endpoint value is missing for subject {subject_id} at {visit_name}. This must be completed.",
                "category": QueryCategory.MISSING_DATA,
                "priority": QueryPriority.HIGH,
                "active": True,
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AQR-003",
                "rule_name": "Vital Signs Out of Range",
                "condition": "value < lower_limit OR value > upper_limit",
                "form": "Vital Signs",
                "field": "*",
                "message_template": "{field_name} value of {value} is outside the expected range ({lower_limit}-{upper_limit}). Please verify or correct.",
                "category": QueryCategory.OUT_OF_RANGE,
                "priority": QueryPriority.HIGH,
                "active": True,
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AQR-004",
                "rule_name": "Lab Value Clinically Significant",
                "condition": "value > ULN * 3 OR value < LLN * 0.5",
                "form": "Lab Results",
                "field": "*",
                "message_template": "{field_name} value of {value} is clinically significant (>{multiplier}x normal). Please verify against source and report AE if applicable.",
                "category": QueryCategory.OUT_OF_RANGE,
                "priority": QueryPriority.CRITICAL,
                "active": True,
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AQR-005",
                "rule_name": "Age Eligibility Check",
                "condition": "calculated_age < min_age OR calculated_age > max_age",
                "form": "Demographics",
                "field": "date_of_birth",
                "message_template": "Subject age ({calculated_age}) does not meet eligibility criteria ({min_age}-{max_age} years). Please verify date of birth.",
                "category": QueryCategory.INCONSISTENT,
                "priority": QueryPriority.CRITICAL,
                "active": True,
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AQR-006",
                "rule_name": "Date Chronology Check",
                "condition": "end_date < start_date",
                "form": "*",
                "field": "*_end_date",
                "message_template": "End date ({end_date}) is before start date ({start_date}) for {field_name}. Please correct the dates.",
                "category": QueryCategory.INCONSISTENT,
                "priority": QueryPriority.MEDIUM,
                "active": True,
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AQR-007",
                "rule_name": "SAE Without Hospitalization Detail",
                "condition": "sae_reported = TRUE AND hospitalization_detail IS NULL",
                "form": "Adverse Events",
                "field": "hospitalization_detail",
                "message_template": "SAE reported for subject {subject_id} but hospitalization details are missing. Please complete.",
                "category": QueryCategory.MISSING_DATA,
                "priority": QueryPriority.HIGH,
                "active": True,
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "AQR-008",
                "rule_name": "Duplicate Subject Entry",
                "condition": "COUNT(subject_id) > 1 WHERE site_id = current_site",
                "form": "Demographics",
                "field": "subject_id",
                "message_template": "Possible duplicate entry detected for subject {subject_id} at site {site_id}. Please verify this is not a duplicate enrollment.",
                "category": QueryCategory.OTHER,
                "priority": QueryPriority.HIGH,
                "active": False,
                "created_at": now - timedelta(days=60),
            },
        ]

        for r_data in rules_data:
            self._auto_rules[r_data["id"]] = AutoQueryRule(**r_data)

    # ------------------------------------------------------------------
    # Query CRUD
    # ------------------------------------------------------------------

    def list_queries(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: QueryStatus | None = None,
        priority: QueryPriority | None = None,
        category: QueryCategory | None = None,
        source: QuerySource | None = None,
        assigned_to: str | None = None,
    ) -> list[DataQuery]:
        """List data queries with optional filters."""
        with self._lock:
            result = list(self._queries.values())

        if trial_id is not None:
            result = [q for q in result if q.trial_id == trial_id]
        if site_id is not None:
            result = [q for q in result if q.site_id == site_id]
        if status is not None:
            result = [q for q in result if q.status == status]
        if priority is not None:
            result = [q for q in result if q.priority == priority]
        if category is not None:
            result = [q for q in result if q.category == category]
        if source is not None:
            result = [q for q in result if q.source == source]
        if assigned_to is not None:
            result = [q for q in result if q.assigned_to == assigned_to]

        return sorted(result, key=lambda q: q.opened_date, reverse=True)

    def get_query(self, query_id: str) -> DataQuery | None:
        """Get a single data query by ID."""
        with self._lock:
            return self._queries.get(query_id)

    def create_query(self, payload: DataQueryCreate) -> DataQuery:
        """Create a new data query."""
        now = datetime.now(timezone.utc)
        query_id = f"DQ-{uuid4().hex[:8].upper()}"
        query = DataQuery(
            id=query_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            visit_name=payload.visit_name,
            form_name=payload.form_name,
            field_name=payload.field_name,
            query_text=payload.query_text,
            status=QueryStatus.OPEN,
            priority=payload.priority,
            category=payload.category,
            source=payload.source,
            assigned_to=payload.assigned_to,
            opened_date=now,
            created_at=now,
        )
        with self._lock:
            self._queries[query_id] = query
        logger.info("Created data query %s for site %s", query_id, payload.site_id)
        return query

    def update_query(self, query_id: str, payload: DataQueryUpdate) -> DataQuery | None:
        """Update a data query."""
        with self._lock:
            existing = self._queries.get(query_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataQuery(**data)
            self._queries[query_id] = updated
        return updated

    def delete_query(self, query_id: str) -> bool:
        """Delete a data query. Returns True if deleted, False if not found."""
        with self._lock:
            if query_id in self._queries:
                del self._queries[query_id]
                # Clean up related responses and resolutions
                self._responses = {
                    k: v for k, v in self._responses.items() if v.query_id != query_id
                }
                self._resolutions.pop(query_id, None)
                return True
            return False

    # ------------------------------------------------------------------
    # Query Lifecycle
    # ------------------------------------------------------------------

    def open_query(self, payload: DataQueryCreate) -> DataQuery:
        """Open a new data query (alias for create_query)."""
        return self.create_query(payload)

    def respond_to_query(
        self, query_id: str, payload: QueryResponseCreate
    ) -> QueryResponse | None:
        """Add a response to a data query and transition status to answered."""
        now = datetime.now(timezone.utc)
        with self._lock:
            query = self._queries.get(query_id)
            if query is None:
                return None

            if query.status in (QueryStatus.CLOSED, QueryStatus.CANCELLED):
                raise ValueError(
                    f"Cannot respond to query '{query_id}' with status '{query.status.value}'"
                )

            response_id = f"QR-{uuid4().hex[:8].upper()}"
            response = QueryResponse(
                id=response_id,
                query_id=query_id,
                responder=payload.responder,
                response_text=payload.response_text,
                attachments=payload.attachments,
                created_at=now,
            )
            self._responses[response_id] = response

            # Update query status and add response
            data = query.model_dump()
            data["status"] = QueryStatus.ANSWERED
            data["answered_date"] = now
            data["responses"] = list(query.responses) + [response]
            self._queries[query_id] = DataQuery(**data)

        logger.info("Response %s added to query %s", response_id, query_id)
        return response

    def close_query(
        self, query_id: str, payload: QueryCloseRequest
    ) -> DataQuery | None:
        """Close a data query with resolution details."""
        now = datetime.now(timezone.utc)
        with self._lock:
            query = self._queries.get(query_id)
            if query is None:
                return None

            if query.status == QueryStatus.CLOSED:
                raise ValueError(f"Query '{query_id}' is already closed")
            if query.status == QueryStatus.CANCELLED:
                raise ValueError(f"Cannot close cancelled query '{query_id}'")

            # Create resolution record
            resolution = DiscrepancyResolution(
                query_id=query_id,
                resolution_type=payload.resolution_type,
                resolution_notes=payload.resolution_notes,
                resolved_by=payload.resolved_by,
                resolved_date=now,
            )
            self._resolutions[query_id] = resolution

            # Update query
            data = query.model_dump()
            data["status"] = QueryStatus.CLOSED
            data["closed_date"] = now
            updated = DataQuery(**data)
            self._queries[query_id] = updated

        logger.info("Closed query %s by %s", query_id, payload.resolved_by)
        return updated

    def requery(self, query_id: str, query_text: str) -> DataQuery | None:
        """Re-query an answered query (send it back to the site)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            query = self._queries.get(query_id)
            if query is None:
                return None

            if query.status not in (QueryStatus.ANSWERED, QueryStatus.OPEN):
                raise ValueError(
                    f"Cannot requery query '{query_id}' with status '{query.status.value}'. "
                    "Only open or answered queries can be requeried."
                )

            data = query.model_dump()
            data["status"] = QueryStatus.REQUERIED
            data["query_text"] = query_text
            data["answered_date"] = None
            updated = DataQuery(**data)
            self._queries[query_id] = updated

        logger.info("Re-queried query %s", query_id)
        return updated

    def cancel_query(self, query_id: str) -> DataQuery | None:
        """Cancel a data query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            query = self._queries.get(query_id)
            if query is None:
                return None

            if query.status == QueryStatus.CLOSED:
                raise ValueError(f"Cannot cancel closed query '{query_id}'")
            if query.status == QueryStatus.CANCELLED:
                raise ValueError(f"Query '{query_id}' is already cancelled")

            data = query.model_dump()
            data["status"] = QueryStatus.CANCELLED
            data["closed_date"] = now
            updated = DataQuery(**data)
            self._queries[query_id] = updated

        logger.info("Cancelled query %s", query_id)
        return updated

    # ------------------------------------------------------------------
    # Auto-Query Rules
    # ------------------------------------------------------------------

    def list_auto_rules(
        self, *, active: bool | None = None
    ) -> list[AutoQueryRule]:
        """List auto-query rules with optional active filter."""
        with self._lock:
            result = list(self._auto_rules.values())

        if active is not None:
            result = [r for r in result if r.active == active]

        return sorted(result, key=lambda r: r.id)

    def get_auto_rule(self, rule_id: str) -> AutoQueryRule | None:
        """Get a single auto-query rule by ID."""
        with self._lock:
            return self._auto_rules.get(rule_id)

    def create_auto_rule(self, payload: AutoQueryRuleCreate) -> AutoQueryRule:
        """Create a new auto-query rule."""
        now = datetime.now(timezone.utc)
        rule_id = f"AQR-{uuid4().hex[:8].upper()}"
        rule = AutoQueryRule(
            id=rule_id,
            rule_name=payload.rule_name,
            condition=payload.condition,
            form=payload.form,
            field=payload.field,
            message_template=payload.message_template,
            category=payload.category,
            priority=payload.priority,
            active=payload.active,
            created_at=now,
        )
        with self._lock:
            self._auto_rules[rule_id] = rule
        logger.info("Created auto-query rule %s: %s", rule_id, payload.rule_name)
        return rule

    def update_auto_rule(
        self, rule_id: str, payload: AutoQueryRuleUpdate
    ) -> AutoQueryRule | None:
        """Update an auto-query rule."""
        with self._lock:
            existing = self._auto_rules.get(rule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AutoQueryRule(**data)
            self._auto_rules[rule_id] = updated
        return updated

    def delete_auto_rule(self, rule_id: str) -> bool:
        """Delete an auto-query rule. Returns True if deleted."""
        with self._lock:
            if rule_id in self._auto_rules:
                del self._auto_rules[rule_id]
                return True
            return False

    def evaluate_auto_rules(
        self, trial_id: str, site_id: str
    ) -> list[DataQuery]:
        """Evaluate all active auto-query rules and generate queries.

        In a real system this would evaluate rules against actual CRF data.
        Here we simulate by generating one query per active rule.
        """
        now = datetime.now(timezone.utc)
        generated: list[DataQuery] = []

        with self._lock:
            active_rules = [r for r in self._auto_rules.values() if r.active]

        for rule in active_rules:
            query_id = f"DQ-{uuid4().hex[:8].upper()}"
            query = DataQuery(
                id=query_id,
                trial_id=trial_id,
                site_id=site_id,
                form_name=rule.form,
                field_name=rule.field,
                query_text=rule.message_template,
                status=QueryStatus.OPEN,
                priority=rule.priority,
                category=rule.category,
                source=QuerySource.AUTO_RULE,
                auto_rule_id=rule.id,
                opened_date=now,
                created_at=now,
            )
            with self._lock:
                self._queries[query_id] = query
            generated.append(query)

        logger.info(
            "Auto-query evaluation generated %d queries for trial=%s site=%s",
            len(generated), trial_id, site_id,
        )
        return generated

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def list_responses(self, query_id: str) -> list[QueryResponse]:
        """List all responses for a given query."""
        with self._lock:
            return [
                r for r in self._responses.values() if r.query_id == query_id
            ]

    # ------------------------------------------------------------------
    # Resolutions
    # ------------------------------------------------------------------

    def get_resolution(self, query_id: str) -> DiscrepancyResolution | None:
        """Get resolution details for a query."""
        with self._lock:
            return self._resolutions.get(query_id)

    def list_resolutions(self) -> list[DiscrepancyResolution]:
        """List all discrepancy resolutions."""
        with self._lock:
            return list(self._resolutions.values())

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_aging_report(self) -> QueryAgingReport:
        """Generate a query aging report for all open queries."""
        now = datetime.now(timezone.utc)

        with self._lock:
            open_queries = [
                q for q in self._queries.values()
                if q.status in (QueryStatus.OPEN, QueryStatus.REQUERIED, QueryStatus.ANSWERED)
            ]

        buckets_def = [
            ("0-7d", 0, 7),
            ("8-14d", 8, 14),
            ("15-30d", 15, 30),
            ("30+d", 31, 999999),
        ]

        buckets: list[AgingBucket] = []
        oldest_days = 0

        for label, min_days, max_days in buckets_def:
            matching_ids = []
            for q in open_queries:
                age_days = (now - q.opened_date).days
                if min_days <= age_days <= max_days:
                    matching_ids.append(q.id)
                if age_days > oldest_days:
                    oldest_days = age_days
            buckets.append(AgingBucket(
                bucket=label,
                count=len(matching_ids),
                query_ids=matching_ids,
            ))

        return QueryAgingReport(
            total_open=len(open_queries),
            buckets=buckets,
            oldest_query_days=oldest_days,
            generated_at=now,
        )

    def get_query_metrics(self) -> QueryMetrics:
        """Compute aggregated data query metrics."""
        with self._lock:
            queries = list(self._queries.values())

        total = len(queries)
        open_count = sum(1 for q in queries if q.status == QueryStatus.OPEN)
        answered_count = sum(1 for q in queries if q.status == QueryStatus.ANSWERED)
        closed_count = sum(1 for q in queries if q.status == QueryStatus.CLOSED)
        cancelled_count = sum(1 for q in queries if q.status == QueryStatus.CANCELLED)
        requeried_count = sum(1 for q in queries if q.status == QueryStatus.REQUERIED)

        # Average resolution time for closed queries
        resolution_days: list[float] = []
        for q in queries:
            if q.status == QueryStatus.CLOSED and q.closed_date and q.opened_date:
                days = (q.closed_date - q.opened_date).total_seconds() / 86400
                resolution_days.append(days)
        avg_resolution = (
            round(sum(resolution_days) / len(resolution_days), 1)
            if resolution_days
            else 0.0
        )

        # By category
        by_category: dict[str, int] = {}
        for q in queries:
            key = q.category.value
            by_category[key] = by_category.get(key, 0) + 1

        # By site
        by_site: dict[str, int] = {}
        for q in queries:
            by_site[q.site_id] = by_site.get(q.site_id, 0) + 1

        # By priority
        by_priority: dict[str, int] = {}
        for q in queries:
            key = q.priority.value
            by_priority[key] = by_priority.get(key, 0) + 1

        auto_count = sum(1 for q in queries if q.source == QuerySource.AUTO_RULE)
        manual_count = sum(1 for q in queries if q.source == QuerySource.MANUAL)

        return QueryMetrics(
            total_queries=total,
            open_queries=open_count,
            answered_queries=answered_count,
            closed_queries=closed_count,
            cancelled_queries=cancelled_count,
            requeried_queries=requeried_count,
            avg_resolution_days=avg_resolution,
            queries_by_category=by_category,
            queries_by_site=by_site,
            queries_by_priority=by_priority,
            auto_query_count=auto_count,
            manual_query_count=manual_count,
        )

    def get_site_query_summary(
        self, site_id: str | None = None
    ) -> list[SiteQuerySummary]:
        """Get query summary per site, optionally for a specific site."""
        with self._lock:
            queries = list(self._queries.values())

        # Group by site
        site_queries: dict[str, list[DataQuery]] = {}
        for q in queries:
            if site_id is not None and q.site_id != site_id:
                continue
            site_queries.setdefault(q.site_id, []).append(q)

        summaries: list[SiteQuerySummary] = []
        for sid, sq in sorted(site_queries.items()):
            total = len(sq)
            open_q = sum(1 for q in sq if q.status == QueryStatus.OPEN)
            answered_q = sum(1 for q in sq if q.status == QueryStatus.ANSWERED)
            closed_q = sum(1 for q in sq if q.status == QueryStatus.CLOSED)
            requeried_q = sum(1 for q in sq if q.status == QueryStatus.REQUERIED)

            resolution_days: list[float] = []
            for q in sq:
                if q.status == QueryStatus.CLOSED and q.closed_date and q.opened_date:
                    days = (q.closed_date - q.opened_date).total_seconds() / 86400
                    resolution_days.append(days)

            avg_days = (
                round(sum(resolution_days) / len(resolution_days), 1)
                if resolution_days
                else 0.0
            )

            summaries.append(SiteQuerySummary(
                site_id=sid,
                total_queries=total,
                open_queries=open_q,
                answered_queries=answered_q,
                closed_queries=closed_q,
                requeried_queries=requeried_q,
                avg_resolution_days=avg_days,
            ))

        return summaries

    # ------------------------------------------------------------------
    # Bulk Operations
    # ------------------------------------------------------------------

    def bulk_close_queries(self, payload: BulkCloseRequest) -> BulkOperationResult:
        """Close multiple queries at once."""
        succeeded: list[str] = []
        failed: list[str] = []

        for qid in payload.query_ids:
            try:
                close_req = QueryCloseRequest(
                    resolution_type=payload.resolution_type,
                    resolution_notes=payload.resolution_notes,
                    resolved_by=payload.resolved_by,
                )
                result = self.close_query(qid, close_req)
                if result is not None:
                    succeeded.append(qid)
                else:
                    failed.append(qid)
            except ValueError:
                failed.append(qid)

        return BulkOperationResult(
            succeeded=succeeded,
            failed=failed,
            total_succeeded=len(succeeded),
            total_failed=len(failed),
        )

    def bulk_assign_queries(self, payload: BulkAssignRequest) -> BulkOperationResult:
        """Assign multiple queries to a person."""
        succeeded: list[str] = []
        failed: list[str] = []

        for qid in payload.query_ids:
            update_payload = DataQueryUpdate(assigned_to=payload.assigned_to)
            result = self.update_query(qid, update_payload)
            if result is not None:
                succeeded.append(qid)
            else:
                failed.append(qid)

        return BulkOperationResult(
            succeeded=succeeded,
            failed=failed,
            total_succeeded=len(succeeded),
            total_failed=len(failed),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DataQueriesService | None = None
_instance_lock = threading.Lock()


def get_data_queries_service() -> DataQueriesService:
    """Return the singleton DataQueriesService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DataQueriesService()
    return _instance


def reset_data_queries_service() -> DataQueriesService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DataQueriesService()
    return _instance
