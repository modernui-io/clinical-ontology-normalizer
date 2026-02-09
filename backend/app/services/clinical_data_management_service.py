"""Clinical Data Management & Data Cleaning Service (CLINICAL-2).

Manages data queries, validation rules, CDISC-compliant dataset lifecycle,
audit trails, and data cleaning metrics for clinical trials.

Usage:
    from app.services.clinical_data_management_service import (
        get_clinical_data_management_service,
    )

    svc = get_clinical_data_management_service()
    query = svc.create_query(...)
    metrics = svc.get_cleaning_metrics(trial_id)
"""

from __future__ import annotations

import logging
import statistics
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from app.schemas.clinical_data_management import (
    AuditTrailEntry,
    BatchValidationResponse,
    CDISCConformanceReport,
    CDISCDomain,
    CDISCDomainConformanceResult,
    CDISCStandard,
    ClinicalDataset,
    ClinicalDatasetCreate,
    ClinicalDatasetUpdate,
    DataCleaningMetrics,
    DataLockLevel,
    DataQuery,
    DataQueryAnswer,
    DataQueryClose,
    DataQueryCreate,
    DataQueryRequery,
    DataQueryUpdate,
    DatasetComparisonResult,
    DatasetFreezeRequest,
    DatasetLockRequest,
    DatasetReleaseRequest,
    DatasetStatus,
    QueryCategory,
    QueryResolutionMetrics,
    QueryStatus,
    ValidationResult,
    ValidationRule,
    ValidationRuleCreate,
    ValidationRuleType,
    ValidationRuleUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trial IDs matching the rest of the platform
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# ---------------------------------------------------------------------------
# Valid dataset status transitions
# ---------------------------------------------------------------------------

VALID_DATASET_TRANSITIONS: dict[DatasetStatus, set[DatasetStatus]] = {
    DatasetStatus.DRAFT: {DatasetStatus.IN_REVIEW},
    DatasetStatus.IN_REVIEW: {DatasetStatus.CLEANED, DatasetStatus.DRAFT},
    DatasetStatus.CLEANED: {DatasetStatus.FROZEN, DatasetStatus.IN_REVIEW},
    DatasetStatus.FROZEN: {DatasetStatus.LOCKED, DatasetStatus.CLEANED},
    DatasetStatus.LOCKED: {DatasetStatus.RELEASED},
    DatasetStatus.RELEASED: {DatasetStatus.ARCHIVED},
    DatasetStatus.ARCHIVED: set(),
}

# Valid query status transitions
VALID_QUERY_TRANSITIONS: dict[QueryStatus, set[QueryStatus]] = {
    QueryStatus.OPEN: {QueryStatus.ANSWERED, QueryStatus.CANCELLED},
    QueryStatus.ANSWERED: {QueryStatus.CLOSED, QueryStatus.REQUERIED},
    QueryStatus.CLOSED: set(),
    QueryStatus.CANCELLED: set(),
    QueryStatus.REQUERIED: {QueryStatus.ANSWERED, QueryStatus.CANCELLED},
}


class ClinicalDataManagementService:
    """In-memory clinical data management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._queries: dict[str, DataQuery] = {}
        self._rules: dict[str, ValidationRule] = {}
        self._results: dict[str, ValidationResult] = {}
        self._datasets: dict[str, ClinicalDataset] = {}
        self._domains: dict[str, CDISCDomain] = {}
        self._audit_trail: list[AuditTrailEntry] = []
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic clinical data management data."""
        now = datetime.now(timezone.utc)

        # --- Validation Rules (15) ---
        rules_seed: list[dict] = [
            {"rule_name": "DM_AGE_RANGE", "rule_type": ValidationRuleType.RANGE_CHECK,
             "description": "Subject age must be between 18 and 99",
             "expression": "DM.AGE >= 18 AND DM.AGE <= 99", "domain": "DM",
             "fields": ["AGE"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "DM_SEX_FORMAT", "rule_type": ValidationRuleType.FORMAT,
             "description": "Sex must be M or F",
             "expression": "DM.SEX IN ('M', 'F')", "domain": "DM",
             "fields": ["SEX"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "DM_RACE_COMPLETENESS", "rule_type": ValidationRuleType.COMPLETENESS,
             "description": "Race must not be blank",
             "expression": "DM.RACE IS NOT NULL", "domain": "DM",
             "fields": ["RACE"], "severity": "WARNING", "auto_query": False},
            {"rule_name": "AE_ONSET_TEMPORAL", "rule_type": ValidationRuleType.TEMPORAL,
             "description": "AE onset date must be on or after informed consent date",
             "expression": "AE.AESTDTC >= DS.DSSTDTC[INFORMED CONSENT]", "domain": "AE",
             "fields": ["AESTDTC"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "AE_SEVERITY_FORMAT", "rule_type": ValidationRuleType.FORMAT,
             "description": "AE severity must be MILD, MODERATE, or SEVERE",
             "expression": "AE.AESEV IN ('MILD','MODERATE','SEVERE')", "domain": "AE",
             "fields": ["AESEV"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "LB_RESULT_RANGE", "rule_type": ValidationRuleType.RANGE_CHECK,
             "description": "Lab result must be within 5x normal range",
             "expression": "LB.LBSTRESN <= LB.LBSTNRHI * 5", "domain": "LB",
             "fields": ["LBSTRESN", "LBSTNRHI"], "severity": "WARNING", "auto_query": False},
            {"rule_name": "VS_BP_SYSTOLIC_RANGE", "rule_type": ValidationRuleType.RANGE_CHECK,
             "description": "Systolic BP must be between 60 and 250 mmHg",
             "expression": "VS.VSSTRESN >= 60 AND VS.VSSTRESN <= 250 WHERE VSTESTCD='SYSBP'",
             "domain": "VS", "fields": ["VSSTRESN"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "VS_BP_CONSISTENCY", "rule_type": ValidationRuleType.CROSS_FIELD,
             "description": "Systolic BP must be greater than diastolic BP",
             "expression": "VS.SYSBP > VS.DIABP", "domain": "VS",
             "fields": ["SYSBP", "DIABP"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "CM_DATE_TEMPORAL", "rule_type": ValidationRuleType.TEMPORAL,
             "description": "CM start date must be before or equal to end date",
             "expression": "CM.CMSTDTC <= CM.CMENDTC", "domain": "CM",
             "fields": ["CMSTDTC", "CMENDTC"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "EX_DOSE_RANGE", "rule_type": ValidationRuleType.RANGE_CHECK,
             "description": "Exposure dose must be positive",
             "expression": "EX.EXDOSE > 0", "domain": "EX",
             "fields": ["EXDOSE"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "DM_SUBJID_REFERENTIAL", "rule_type": ValidationRuleType.REFERENTIAL_INTEGRITY,
             "description": "Every AE subject must exist in DM",
             "expression": "AE.USUBJID IN DM.USUBJID", "domain": "AE",
             "fields": ["USUBJID"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "DS_DISPOSITION_COMPLETENESS", "rule_type": ValidationRuleType.COMPLETENESS,
             "description": "Disposition term must not be blank for completed subjects",
             "expression": "DS.DSTERM IS NOT NULL WHERE DSDECOD='COMPLETED'", "domain": "DS",
             "fields": ["DSTERM"], "severity": "WARNING", "auto_query": False},
            {"rule_name": "MH_ONGOING_BUSINESS", "rule_type": ValidationRuleType.BUSINESS_RULE,
             "description": "Ongoing medical history must have blank end date",
             "expression": "IF MH.MHENRF='ONGOING' THEN MH.MHENDTC IS NULL", "domain": "MH",
             "fields": ["MHENRF", "MHENDTC"], "severity": "ERROR", "auto_query": True},
            {"rule_name": "LB_FASTING_COMPLETENESS", "rule_type": ValidationRuleType.COMPLETENESS,
             "description": "Fasting status must be recorded for glucose tests",
             "expression": "LB.LBFAST IS NOT NULL WHERE LBTESTCD='GLUC'", "domain": "LB",
             "fields": ["LBFAST"], "severity": "WARNING", "auto_query": False},
            {"rule_name": "AE_CAUSALITY_BUSINESS", "rule_type": ValidationRuleType.BUSINESS_RULE,
             "description": "Serious AEs must have causality assessment completed",
             "expression": "IF AE.AESER='Y' THEN AE.AEREL IS NOT NULL", "domain": "AE",
             "fields": ["AESER", "AEREL"], "severity": "ERROR", "auto_query": True},
        ]

        for i, r in enumerate(rules_seed):
            rule_id = f"VR-{i + 1:04d}"
            self._rules[rule_id] = ValidationRule(
                id=rule_id,
                created_at=now - timedelta(days=90 - i),
                **r,
            )

        # --- Data Queries (25 across 3 trials) ---
        # Distribution: 5 OPEN, 8 ANSWERED, 10 CLOSED, 2 CANCELLED
        query_seeds: list[dict] = [
            # OPEN queries (5)
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-001", "patient_id": "PAT-E001",
             "form_name": "Demographics", "field_name": "AGE", "query_category": QueryCategory.OUT_OF_RANGE,
             "description": "Age value 150 exceeds maximum allowed range (18-99)",
             "current_value": "150", "expected_value": "18-99", "status": QueryStatus.OPEN,
             "opened_by": "data_manager_1", "auto_generated": True},
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-002", "patient_id": "PAT-E005",
             "form_name": "Adverse Events", "field_name": "AESTDTC", "query_category": QueryCategory.INCONSISTENT,
             "description": "AE onset date precedes informed consent date by 3 days",
             "current_value": "2024-01-10", "expected_value": ">= 2024-01-13", "status": QueryStatus.OPEN,
             "opened_by": "data_manager_1", "auto_generated": True},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-003", "patient_id": "PAT-D002",
             "form_name": "Lab Results", "field_name": "LBSTRESN", "query_category": QueryCategory.OUT_OF_RANGE,
             "description": "ALT value 850 U/L exceeds 5x upper limit of normal",
             "current_value": "850", "expected_value": "<= 200", "status": QueryStatus.OPEN,
             "opened_by": "medical_monitor", "auto_generated": False},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-004", "patient_id": "PAT-D007",
             "form_name": "Vital Signs", "field_name": "SYSBP", "query_category": QueryCategory.INCONSISTENT,
             "description": "Systolic BP (110) is less than Diastolic BP (120)",
             "current_value": "110/120", "expected_value": "SBP > DBP", "status": QueryStatus.OPEN,
             "opened_by": "data_manager_2", "auto_generated": True},
            {"trial_id": LIBTAYO_TRIAL, "site_id": "SITE-005", "patient_id": "PAT-L001",
             "form_name": "Concomitant Meds", "field_name": "CMSTDTC", "query_category": QueryCategory.MISSING_DATA,
             "description": "Start date is missing for concomitant medication Metformin",
             "current_value": None, "expected_value": "Valid date required", "status": QueryStatus.OPEN,
             "opened_by": "data_manager_1", "auto_generated": False},

            # ANSWERED queries (8)
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-001", "patient_id": "PAT-E002",
             "form_name": "Demographics", "field_name": "RACE", "query_category": QueryCategory.MISSING_DATA,
             "description": "Race field is blank", "status": QueryStatus.ANSWERED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_1",
             "answer_text": "Race updated to WHITE. Data entry error corrected.", "auto_generated": True},
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-002", "patient_id": "PAT-E003",
             "form_name": "Lab Results", "field_name": "LBFAST", "query_category": QueryCategory.MISSING_DATA,
             "description": "Fasting status not recorded for glucose test", "status": QueryStatus.ANSWERED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_2",
             "answer_text": "Subject was fasting. Updated LBFAST to Y.", "auto_generated": True},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-003", "patient_id": "PAT-D001",
             "form_name": "Adverse Events", "field_name": "AEREL", "query_category": QueryCategory.MISSING_DATA,
             "description": "Causality assessment missing for serious AE", "status": QueryStatus.ANSWERED,
             "opened_by": "medical_monitor", "answered_by": "investigator_1",
             "answer_text": "Assessed as POSSIBLY RELATED. Updated.", "auto_generated": True},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-003", "patient_id": "PAT-D003",
             "form_name": "Exposure", "field_name": "EXDOSE", "query_category": QueryCategory.TRANSCRIPTION,
             "description": "Dose recorded as 0 mg - please verify", "status": QueryStatus.ANSWERED,
             "opened_by": "data_manager_2", "answered_by": "site_coord_3",
             "answer_text": "Transcription error. Correct dose is 300mg. Updated.", "auto_generated": False},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-004", "patient_id": "PAT-D005",
             "form_name": "Medical History", "field_name": "MHENDTC", "query_category": QueryCategory.INCONSISTENT,
             "description": "Ongoing condition has end date populated", "status": QueryStatus.ANSWERED,
             "opened_by": "data_manager_2", "answered_by": "site_coord_4",
             "answer_text": "Condition resolved. Updated MHENRF to RESOLVED.", "auto_generated": True},
            {"trial_id": LIBTAYO_TRIAL, "site_id": "SITE-005", "patient_id": "PAT-L002",
             "form_name": "Adverse Events", "field_name": "AESEV", "query_category": QueryCategory.CODING_ERROR,
             "description": "Severity coded as MODERETE - not a valid term", "status": QueryStatus.ANSWERED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_5",
             "answer_text": "Corrected to MODERATE. Typo in original entry.", "auto_generated": True},
            {"trial_id": LIBTAYO_TRIAL, "site_id": "SITE-006", "patient_id": "PAT-L004",
             "form_name": "Disposition", "field_name": "DSTERM", "query_category": QueryCategory.MISSING_DATA,
             "description": "Disposition term missing for completed subject", "status": QueryStatus.ANSWERED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_6",
             "answer_text": "Completed per protocol. DSTERM updated.", "auto_generated": True},
            {"trial_id": LIBTAYO_TRIAL, "site_id": "SITE-005", "patient_id": "PAT-L003",
             "form_name": "Demographics", "field_name": "SEX", "query_category": QueryCategory.CODING_ERROR,
             "description": "Sex coded as 'Male' instead of 'M'", "status": QueryStatus.ANSWERED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_5",
             "answer_text": "Corrected to M.", "auto_generated": True},

            # CLOSED queries (10)
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-001", "patient_id": "PAT-E004",
             "form_name": "Demographics", "field_name": "BRTHDTC", "query_category": QueryCategory.MISSING_DATA,
             "description": "Birth date missing", "status": QueryStatus.CLOSED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_1",
             "answer_text": "Birth date added: 1955-03-22", "closed_by": "data_manager_1",
             "auto_generated": True},
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-001", "patient_id": "PAT-E006",
             "form_name": "Vital Signs", "field_name": "VSSTRESN", "query_category": QueryCategory.OUT_OF_RANGE,
             "description": "Heart rate 220 bpm exceeds physiological range",
             "current_value": "220", "expected_value": "40-200", "status": QueryStatus.CLOSED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_1",
             "answer_text": "Confirmed 220 during tachycardia episode. SAE reported.",
             "closed_by": "data_manager_1", "auto_generated": True},
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-002", "patient_id": "PAT-E007",
             "form_name": "Concomitant Meds", "field_name": "CMDECOD", "query_category": QueryCategory.CODING_ERROR,
             "description": "Medication coded incorrectly as C01234 instead of C05678",
             "status": QueryStatus.CLOSED, "opened_by": "data_manager_1", "answered_by": "site_coord_2",
             "answer_text": "Corrected coding to C05678.", "closed_by": "data_manager_1",
             "auto_generated": False},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-003", "patient_id": "PAT-D004",
             "form_name": "Lab Results", "field_name": "LBDTC", "query_category": QueryCategory.TIMELINESS,
             "description": "Lab results entered 30 days after collection",
             "status": QueryStatus.CLOSED, "opened_by": "data_manager_2", "answered_by": "site_coord_3",
             "answer_text": "Site backlog cleared. Results now current.",
             "closed_by": "data_manager_2", "auto_generated": False},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-003", "patient_id": "PAT-D006",
             "form_name": "Adverse Events", "field_name": "AEENDTC", "query_category": QueryCategory.INCONSISTENT,
             "description": "AE end date before start date",
             "status": QueryStatus.CLOSED, "opened_by": "data_manager_2", "answered_by": "site_coord_3",
             "answer_text": "Dates swapped in error. Corrected.",
             "closed_by": "data_manager_2", "auto_generated": True},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-004", "patient_id": "PAT-D008",
             "form_name": "Exposure", "field_name": "EXDOSE", "query_category": QueryCategory.PROTOCOL_VIOLATION,
             "description": "Dose 600mg exceeds protocol maximum of 300mg",
             "status": QueryStatus.CLOSED, "opened_by": "medical_monitor", "answered_by": "investigator_2",
             "answer_text": "Protocol deviation documented. Dose was 300mg, entry corrected.",
             "closed_by": "medical_monitor", "auto_generated": False},
            {"trial_id": LIBTAYO_TRIAL, "site_id": "SITE-005", "patient_id": "PAT-L005",
             "form_name": "Demographics", "field_name": "COUNTRY", "query_category": QueryCategory.CODING_ERROR,
             "description": "Country coded as 'United States' instead of ISO code 'USA'",
             "status": QueryStatus.CLOSED, "opened_by": "data_manager_1", "answered_by": "site_coord_5",
             "answer_text": "Updated to USA.", "closed_by": "data_manager_1", "auto_generated": True},
            {"trial_id": LIBTAYO_TRIAL, "site_id": "SITE-005", "patient_id": "PAT-L006",
             "form_name": "Lab Results", "field_name": "LBSTRESN", "query_category": QueryCategory.DUPLICATE,
             "description": "Duplicate lab record found for same visit and test",
             "status": QueryStatus.CLOSED, "opened_by": "data_manager_1", "answered_by": "site_coord_5",
             "answer_text": "Duplicate removed.", "closed_by": "data_manager_1", "auto_generated": True},
            {"trial_id": LIBTAYO_TRIAL, "site_id": "SITE-006", "patient_id": "PAT-L007",
             "form_name": "Vital Signs", "field_name": "VSSTRESN", "query_category": QueryCategory.OUT_OF_RANGE,
             "description": "Weight 500 kg exceeds maximum range",
             "current_value": "500", "expected_value": "30-300", "status": QueryStatus.CLOSED,
             "opened_by": "data_manager_1", "answered_by": "site_coord_6",
             "answer_text": "Unit error. Correct weight is 50 kg.",
             "closed_by": "data_manager_1", "auto_generated": True},
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-002", "patient_id": "PAT-E008",
             "form_name": "Adverse Events", "field_name": "AEDECOD", "query_category": QueryCategory.CODING_ERROR,
             "description": "AE term not found in MedDRA dictionary",
             "status": QueryStatus.CLOSED, "opened_by": "data_manager_1", "answered_by": "site_coord_2",
             "answer_text": "Re-coded to valid MedDRA PT 'Headache'.",
             "closed_by": "data_manager_1", "auto_generated": False},

            # CANCELLED queries (2)
            {"trial_id": EYLEA_TRIAL, "site_id": "SITE-001", "patient_id": "PAT-E009",
             "form_name": "Demographics", "field_name": "ETHNIC", "query_category": QueryCategory.MISSING_DATA,
             "description": "Ethnicity field blank", "status": QueryStatus.CANCELLED,
             "opened_by": "data_manager_1", "auto_generated": True},
            {"trial_id": DUPIXENT_TRIAL, "site_id": "SITE-004", "patient_id": "PAT-D009",
             "form_name": "Lab Results", "field_name": "LBORRES", "query_category": QueryCategory.TRANSCRIPTION,
             "description": "Original query superseded by protocol amendment",
             "status": QueryStatus.CANCELLED, "opened_by": "data_manager_2", "auto_generated": False},
        ]

        for i, q in enumerate(query_seeds):
            qid = f"DQ-{i + 1:04d}"
            opened_at = now - timedelta(days=60 - i * 2, hours=i)

            answered_at = None
            closed_at = None
            if q.get("answered_by"):
                answered_at = opened_at + timedelta(days=3 + (i % 5))
            if q.get("closed_by"):
                closed_at = (answered_at or opened_at) + timedelta(days=2 + (i % 3))

            self._queries[qid] = DataQuery(
                id=qid,
                trial_id=q["trial_id"],
                site_id=q["site_id"],
                patient_id=q["patient_id"],
                form_name=q["form_name"],
                field_name=q["field_name"],
                query_category=q["query_category"],
                description=q["description"],
                current_value=q.get("current_value"),
                expected_value=q.get("expected_value"),
                status=q["status"],
                opened_by=q["opened_by"],
                opened_at=opened_at,
                answered_by=q.get("answered_by"),
                answered_at=answered_at,
                answer_text=q.get("answer_text"),
                closed_by=q.get("closed_by"),
                closed_at=closed_at,
                auto_generated=q.get("auto_generated", False),
                requery_count=0,
            )

        # --- Validation Results (40) ---
        rule_ids = list(self._rules.keys())
        result_idx = 0
        for trial_id, patient_prefix, count in [
            (EYLEA_TRIAL, "PAT-E", 15),
            (DUPIXENT_TRIAL, "PAT-D", 15),
            (LIBTAYO_TRIAL, "PAT-L", 10),
        ]:
            for j in range(count):
                result_idx += 1
                rid = f"VRR-{result_idx:04d}"
                rule = self._rules[rule_ids[j % len(rule_ids)]]
                passed = result_idx % 3 != 0  # ~67% pass rate
                self._results[rid] = ValidationResult(
                    id=rid,
                    rule_id=rule.id,
                    rule_name=rule.rule_name,
                    trial_id=trial_id,
                    patient_id=f"{patient_prefix}{(j + 1):03d}",
                    field_name=rule.fields[0] if rule.fields else "UNKNOWN",
                    current_value=str(100 + j * 5) if not passed else str(50 + j),
                    expected_range=rule.expression[:40],
                    passed=passed,
                    message=f"{'PASS' if passed else 'FAIL'}: {rule.description}",
                    checked_at=now - timedelta(hours=result_idx),
                )

        # --- Clinical Datasets (3) ---
        datasets_seed = [
            {
                "trial_id": EYLEA_TRIAL, "trial_name": "EYLEA HD DME Phase III",
                "name": "EYLEA_SDTM_v2.1", "cdisc_standard": CDISCStandard.SDTM,
                "version": "2.1", "status": DatasetStatus.IN_REVIEW,
                "total_records": 12450, "total_variables": 342,
                "completeness_percent": 94.5, "conformance_percent": 97.2,
            },
            {
                "trial_id": DUPIXENT_TRIAL, "trial_name": "Dupixent Asthma Phase III",
                "name": "DUPIXENT_ADaM_v1.3", "cdisc_standard": CDISCStandard.ADAM,
                "version": "1.3", "status": DatasetStatus.FROZEN,
                "total_records": 28900, "total_variables": 518,
                "completeness_percent": 98.1, "conformance_percent": 99.0,
                "frozen_at": now - timedelta(days=14),
            },
            {
                "trial_id": LIBTAYO_TRIAL, "trial_name": "Libtayo NSCLC Phase III",
                "name": "LIBTAYO_SDTM_v1.0", "cdisc_standard": CDISCStandard.SDTM,
                "version": "1.0", "status": DatasetStatus.DRAFT,
                "total_records": 5200, "total_variables": 198,
                "completeness_percent": 78.3, "conformance_percent": 88.5,
            },
        ]

        for i, d in enumerate(datasets_seed):
            did = f"DS-{i + 1:04d}"
            self._datasets[did] = ClinicalDataset(
                id=did,
                created_at=now - timedelta(days=120 - i * 30),
                updated_at=now - timedelta(days=i * 5),
                **d,
            )

        # --- CDISC Domains (12) ---
        domains_seed = [
            {"name": "DM", "description": "Demographics", "key_variables": ["STUDYID", "USUBJID"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "AGE", "SEX", "RACE"],
             "total_records": 450, "conformance_issues": 3},
            {"name": "AE", "description": "Adverse Events", "key_variables": ["STUDYID", "USUBJID", "AESEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "AETERM", "AEDECOD", "AESTDTC"],
             "total_records": 1250, "conformance_issues": 12},
            {"name": "LB", "description": "Laboratory Test Results", "key_variables": ["STUDYID", "USUBJID", "LBSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "LBTESTCD", "LBTEST", "LBORRES"],
             "total_records": 8900, "conformance_issues": 8},
            {"name": "VS", "description": "Vital Signs", "key_variables": ["STUDYID", "USUBJID", "VSSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "VSTESTCD", "VSTEST", "VSORRES"],
             "total_records": 3600, "conformance_issues": 5},
            {"name": "CM", "description": "Concomitant Medications", "key_variables": ["STUDYID", "USUBJID", "CMSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "CMTRT", "CMDECOD"],
             "total_records": 2100, "conformance_issues": 7},
            {"name": "EX", "description": "Exposure", "key_variables": ["STUDYID", "USUBJID", "EXSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "EXTRT", "EXDOSE", "EXDOSU"],
             "total_records": 1800, "conformance_issues": 2},
            {"name": "DS", "description": "Disposition", "key_variables": ["STUDYID", "USUBJID", "DSSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "DSTERM", "DSDECOD"],
             "total_records": 450, "conformance_issues": 1},
            {"name": "MH", "description": "Medical History", "key_variables": ["STUDYID", "USUBJID", "MHSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "MHTERM", "MHDECOD"],
             "total_records": 1650, "conformance_issues": 4},
            {"name": "PE", "description": "Physical Examination", "key_variables": ["STUDYID", "USUBJID", "PESEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "PETESTCD", "PETEST"],
             "total_records": 900, "conformance_issues": 2},
            {"name": "SC", "description": "Subject Characteristics", "key_variables": ["STUDYID", "USUBJID", "SCSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "SCTESTCD", "SCTEST"],
             "total_records": 450, "conformance_issues": 0},
            {"name": "SV", "description": "Subject Visits", "key_variables": ["STUDYID", "USUBJID", "VISITNUM"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "VISITNUM", "SVSTDTC"],
             "total_records": 2700, "conformance_issues": 3},
            {"name": "TU", "description": "Tumor Identification", "key_variables": ["STUDYID", "USUBJID", "TUSEQ"],
             "required_variables": ["STUDYID", "DOMAIN", "USUBJID", "TUTESTCD", "TUTEST"],
             "total_records": 320, "conformance_issues": 1},
        ]

        for d in domains_seed:
            self._domains[d["name"]] = CDISCDomain(**d)

        # --- Seed audit trail for datasets ---
        for did, ds in self._datasets.items():
            self._audit_trail.append(AuditTrailEntry(
                id=str(uuid4()),
                dataset_id=did,
                action="CREATE",
                field_name=None,
                old_value=None,
                new_value=ds.name,
                reason="Initial dataset creation",
                actor="data_manager_1",
                timestamp=ds.created_at,
            ))

        logger.info(
            "Clinical data management seed: %d queries, %d rules, %d results, %d datasets, %d domains",
            len(self._queries), len(self._rules), len(self._results),
            len(self._datasets), len(self._domains),
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return summary statistics."""
        with self._lock:
            return {
                "queries": len(self._queries),
                "rules": len(self._rules),
                "results": len(self._results),
                "datasets": len(self._datasets),
                "domains": len(self._domains),
                "audit_entries": len(self._audit_trail),
            }

    # ==================================================================
    # Data Query CRUD
    # ==================================================================

    def list_queries(
        self,
        trial_id: Optional[str] = None,
        site_id: Optional[str] = None,
        status: Optional[QueryStatus] = None,
        category: Optional[QueryCategory] = None,
        patient_id: Optional[str] = None,
        auto_generated: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DataQuery], int]:
        """List data queries with optional filters."""
        with self._lock:
            items = list(self._queries.values())

        if trial_id:
            items = [q for q in items if q.trial_id == trial_id]
        if site_id:
            items = [q for q in items if q.site_id == site_id]
        if status:
            items = [q for q in items if q.status == status]
        if category:
            items = [q for q in items if q.query_category == category]
        if patient_id:
            items = [q for q in items if q.patient_id == patient_id]
        if auto_generated is not None:
            items = [q for q in items if q.auto_generated == auto_generated]

        total = len(items)
        items.sort(key=lambda q: q.opened_at, reverse=True)
        return items[offset:offset + limit], total

    def get_query(self, query_id: str) -> Optional[DataQuery]:
        """Get a single data query by ID."""
        with self._lock:
            return self._queries.get(query_id)

    def create_query(self, req: DataQueryCreate) -> DataQuery:
        """Create a new data query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            qid = f"DQ-{len(self._queries) + 1:04d}"
            # Ensure unique ID
            while qid in self._queries:
                qid = f"DQ-{int(qid.split('-')[1]) + 1:04d}"
            query = DataQuery(
                id=qid,
                trial_id=req.trial_id,
                site_id=req.site_id,
                patient_id=req.patient_id,
                form_name=req.form_name,
                field_name=req.field_name,
                query_category=req.query_category,
                description=req.description,
                current_value=req.current_value,
                expected_value=req.expected_value,
                status=QueryStatus.OPEN,
                opened_by=req.opened_by,
                opened_at=now,
                auto_generated=req.auto_generated,
                requery_count=0,
            )
            self._queries[qid] = query
            return query

    def update_query(self, query_id: str, req: DataQueryUpdate) -> Optional[DataQuery]:
        """Update mutable fields of a data query."""
        with self._lock:
            query = self._queries.get(query_id)
            if not query:
                return None
            data = query.model_dump()
            updates = req.model_dump(exclude_none=True)
            data.update(updates)
            updated = DataQuery(**data)
            self._queries[query_id] = updated
            return updated

    def answer_query(self, query_id: str, req: DataQueryAnswer) -> Optional[DataQuery]:
        """Answer an OPEN or REQUERIED query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            query = self._queries.get(query_id)
            if not query:
                return None
            if query.status not in (QueryStatus.OPEN, QueryStatus.REQUERIED):
                raise ValueError(
                    f"Cannot answer query in status {query.status.value}. "
                    f"Must be OPEN or REQUERIED."
                )
            data = query.model_dump()
            data["status"] = QueryStatus.ANSWERED
            data["answered_by"] = req.answered_by
            data["answered_at"] = now
            data["answer_text"] = req.answer_text
            updated = DataQuery(**data)
            self._queries[query_id] = updated
            return updated

    def close_query(self, query_id: str, req: DataQueryClose) -> Optional[DataQuery]:
        """Close an ANSWERED query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            query = self._queries.get(query_id)
            if not query:
                return None
            if query.status != QueryStatus.ANSWERED:
                raise ValueError(
                    f"Cannot close query in status {query.status.value}. "
                    f"Must be ANSWERED."
                )
            data = query.model_dump()
            data["status"] = QueryStatus.CLOSED
            data["closed_by"] = req.closed_by
            data["closed_at"] = now
            updated = DataQuery(**data)
            self._queries[query_id] = updated
            return updated

    def requery(self, query_id: str, req: DataQueryRequery) -> Optional[DataQuery]:
        """Requery an ANSWERED query (send it back for additional info)."""
        with self._lock:
            query = self._queries.get(query_id)
            if not query:
                return None
            if query.status != QueryStatus.ANSWERED:
                raise ValueError(
                    f"Cannot requery in status {query.status.value}. "
                    f"Must be ANSWERED."
                )
            data = query.model_dump()
            data["status"] = QueryStatus.REQUERIED
            data["requery_count"] = query.requery_count + 1
            data["answered_by"] = None
            data["answered_at"] = None
            data["answer_text"] = None
            data["description"] = f"{query.description} [Requeried: {req.reason}]"
            updated = DataQuery(**data)
            self._queries[query_id] = updated
            return updated

    def cancel_query(self, query_id: str) -> Optional[DataQuery]:
        """Cancel an OPEN or REQUERIED query."""
        with self._lock:
            query = self._queries.get(query_id)
            if not query:
                return None
            if query.status not in (QueryStatus.OPEN, QueryStatus.REQUERIED):
                raise ValueError(
                    f"Cannot cancel query in status {query.status.value}. "
                    f"Must be OPEN or REQUERIED."
                )
            data = query.model_dump()
            data["status"] = QueryStatus.CANCELLED
            updated = DataQuery(**data)
            self._queries[query_id] = updated
            return updated

    # ==================================================================
    # Validation Rules CRUD
    # ==================================================================

    def list_rules(
        self,
        domain: Optional[str] = None,
        rule_type: Optional[ValidationRuleType] = None,
        active: Optional[bool] = None,
    ) -> tuple[list[ValidationRule], int]:
        """List validation rules with optional filters."""
        with self._lock:
            items = list(self._rules.values())

        if domain:
            items = [r for r in items if r.domain == domain]
        if rule_type:
            items = [r for r in items if r.rule_type == rule_type]
        if active is not None:
            items = [r for r in items if r.active == active]

        return items, len(items)

    def get_rule(self, rule_id: str) -> Optional[ValidationRule]:
        """Get a single validation rule."""
        with self._lock:
            return self._rules.get(rule_id)

    def create_rule(self, req: ValidationRuleCreate) -> ValidationRule:
        """Create a new validation rule."""
        now = datetime.now(timezone.utc)
        with self._lock:
            rid = f"VR-{len(self._rules) + 1:04d}"
            while rid in self._rules:
                rid = f"VR-{int(rid.split('-')[1]) + 1:04d}"
            rule = ValidationRule(
                id=rid,
                rule_name=req.rule_name,
                rule_type=req.rule_type,
                description=req.description,
                expression=req.expression,
                domain=req.domain,
                fields=req.fields,
                severity=req.severity,
                active=req.active,
                auto_query=req.auto_query,
                created_at=now,
            )
            self._rules[rid] = rule
            return rule

    def update_rule(self, rule_id: str, req: ValidationRuleUpdate) -> Optional[ValidationRule]:
        """Update a validation rule."""
        with self._lock:
            rule = self._rules.get(rule_id)
            if not rule:
                return None
            data = rule.model_dump()
            updates = req.model_dump(exclude_none=True)
            data.update(updates)
            updated = ValidationRule(**data)
            self._rules[rule_id] = updated
            return updated

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a validation rule."""
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    def run_batch_validation(self, trial_id: str, rule_ids: Optional[list[str]] = None) -> BatchValidationResponse:
        """Execute validation rules against a trial's data.

        In a real system this would query the database. Here we simulate
        results using existing seed data and generate new results.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            if rule_ids:
                rules_to_run = [r for r in self._rules.values() if r.id in rule_ids and r.active]
            else:
                rules_to_run = [r for r in self._rules.values() if r.active]

        new_results: list[ValidationResult] = []
        passed_count = 0
        failed_count = 0

        for i, rule in enumerate(rules_to_run):
            # Simulate 3 checks per rule
            for j in range(3):
                result_id = f"VRR-{len(self._results) + len(new_results) + 1:04d}"
                did_pass = (i + j) % 4 != 0  # ~75% pass rate
                result = ValidationResult(
                    id=result_id,
                    rule_id=rule.id,
                    rule_name=rule.rule_name,
                    trial_id=trial_id,
                    patient_id=f"PAT-BATCH-{j + 1:03d}",
                    field_name=rule.fields[0] if rule.fields else "UNKNOWN",
                    current_value=str(50 + j * 10),
                    expected_range=rule.expression[:40],
                    passed=did_pass,
                    message=f"{'PASS' if did_pass else 'FAIL'}: {rule.description}",
                    checked_at=now,
                )
                new_results.append(result)
                if did_pass:
                    passed_count += 1
                else:
                    failed_count += 1

        with self._lock:
            for r in new_results:
                self._results[r.id] = r

        return BatchValidationResponse(
            trial_id=trial_id,
            rules_executed=len(rules_to_run),
            total_checks=len(new_results),
            passed=passed_count,
            failed=failed_count,
            results=new_results,
        )

    # ==================================================================
    # Validation Results
    # ==================================================================

    def list_results(
        self,
        trial_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        passed: Optional[bool] = None,
        patient_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ValidationResult], int]:
        """List validation results with optional filters."""
        with self._lock:
            items = list(self._results.values())

        if trial_id:
            items = [r for r in items if r.trial_id == trial_id]
        if rule_id:
            items = [r for r in items if r.rule_id == rule_id]
        if passed is not None:
            items = [r for r in items if r.passed == passed]
        if patient_id:
            items = [r for r in items if r.patient_id == patient_id]

        total = len(items)
        items.sort(key=lambda r: r.checked_at, reverse=True)
        return items[offset:offset + limit], total

    def get_result(self, result_id: str) -> Optional[ValidationResult]:
        """Get a single validation result."""
        with self._lock:
            return self._results.get(result_id)

    # ==================================================================
    # Clinical Dataset CRUD + Lifecycle
    # ==================================================================

    def list_datasets(
        self,
        trial_id: Optional[str] = None,
        status: Optional[DatasetStatus] = None,
        cdisc_standard: Optional[CDISCStandard] = None,
    ) -> tuple[list[ClinicalDataset], int]:
        """List clinical datasets with optional filters."""
        with self._lock:
            items = list(self._datasets.values())

        if trial_id:
            items = [d for d in items if d.trial_id == trial_id]
        if status:
            items = [d for d in items if d.status == status]
        if cdisc_standard:
            items = [d for d in items if d.cdisc_standard == cdisc_standard]

        return items, len(items)

    def get_dataset(self, dataset_id: str) -> Optional[ClinicalDataset]:
        """Get a single clinical dataset."""
        with self._lock:
            return self._datasets.get(dataset_id)

    def create_dataset(self, req: ClinicalDatasetCreate) -> ClinicalDataset:
        """Create a new clinical dataset."""
        now = datetime.now(timezone.utc)
        with self._lock:
            did = f"DS-{len(self._datasets) + 1:04d}"
            while did in self._datasets:
                did = f"DS-{int(did.split('-')[1]) + 1:04d}"
            ds = ClinicalDataset(
                id=did,
                trial_id=req.trial_id,
                trial_name=req.trial_name,
                name=req.name,
                cdisc_standard=req.cdisc_standard,
                version=req.version,
                status=DatasetStatus.DRAFT,
                total_records=req.total_records,
                total_variables=req.total_variables,
                completeness_percent=0.0,
                conformance_percent=0.0,
                created_at=now,
                updated_at=now,
            )
            self._datasets[did] = ds
            self._add_audit_entry(did, "CREATE", None, None, ds.name, "Initial creation", "system")
            return ds

    def update_dataset(self, dataset_id: str, req: ClinicalDatasetUpdate) -> Optional[ClinicalDataset]:
        """Update mutable dataset fields."""
        now = datetime.now(timezone.utc)
        with self._lock:
            ds = self._datasets.get(dataset_id)
            if not ds:
                return None
            if ds.status in (DatasetStatus.LOCKED, DatasetStatus.RELEASED, DatasetStatus.ARCHIVED):
                raise ValueError(f"Cannot update dataset in {ds.status.value} status")
            data = ds.model_dump()
            updates = req.model_dump(exclude_none=True)
            for k, v in updates.items():
                old_val = str(data.get(k))
                data[k] = v
                self._add_audit_entry(dataset_id, "UPDATE", k, old_val, str(v), "Field update", "system")
            data["updated_at"] = now
            updated = ClinicalDataset(**data)
            self._datasets[dataset_id] = updated
            return updated

    def freeze_dataset(self, dataset_id: str, req: DatasetFreezeRequest) -> Optional[ClinicalDataset]:
        """Freeze a CLEANED dataset (prevents edits, allows lock)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            ds = self._datasets.get(dataset_id)
            if not ds:
                return None
            if ds.status not in (DatasetStatus.CLEANED, DatasetStatus.IN_REVIEW):
                raise ValueError(
                    f"Cannot freeze dataset in {ds.status.value} status. "
                    f"Must be CLEANED or IN_REVIEW."
                )
            data = ds.model_dump()
            data["status"] = DatasetStatus.FROZEN
            data["frozen_at"] = now
            data["updated_at"] = now
            updated = ClinicalDataset(**data)
            self._datasets[dataset_id] = updated
            self._add_audit_entry(dataset_id, "FREEZE", "status", ds.status.value,
                                  DatasetStatus.FROZEN.value, req.reason, req.frozen_by)
            return updated

    def lock_dataset(self, dataset_id: str, req: DatasetLockRequest) -> Optional[ClinicalDataset]:
        """Lock a FROZEN dataset (regulatory hold)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            ds = self._datasets.get(dataset_id)
            if not ds:
                return None
            if ds.status != DatasetStatus.FROZEN:
                raise ValueError(
                    f"Cannot lock dataset in {ds.status.value} status. Must be FROZEN."
                )
            data = ds.model_dump()
            data["status"] = DatasetStatus.LOCKED
            data["lock_level"] = req.lock_level
            data["locked_at"] = now
            data["locked_by"] = req.locked_by
            data["updated_at"] = now
            updated = ClinicalDataset(**data)
            self._datasets[dataset_id] = updated
            self._add_audit_entry(dataset_id, "LOCK", "status", ds.status.value,
                                  DatasetStatus.LOCKED.value, req.reason, req.locked_by)
            return updated

    def release_dataset(self, dataset_id: str, req: DatasetReleaseRequest) -> Optional[ClinicalDataset]:
        """Release a LOCKED dataset for submission."""
        now = datetime.now(timezone.utc)
        with self._lock:
            ds = self._datasets.get(dataset_id)
            if not ds:
                return None
            if ds.status != DatasetStatus.LOCKED:
                raise ValueError(
                    f"Cannot release dataset in {ds.status.value} status. Must be LOCKED."
                )
            data = ds.model_dump()
            data["status"] = DatasetStatus.RELEASED
            data["release_notes"] = req.release_notes
            data["updated_at"] = now
            updated = ClinicalDataset(**data)
            self._datasets[dataset_id] = updated
            self._add_audit_entry(dataset_id, "RELEASE", "status", ds.status.value,
                                  DatasetStatus.RELEASED.value, req.release_notes, req.released_by)
            return updated

    def archive_dataset(self, dataset_id: str, actor: str) -> Optional[ClinicalDataset]:
        """Archive a RELEASED dataset."""
        now = datetime.now(timezone.utc)
        with self._lock:
            ds = self._datasets.get(dataset_id)
            if not ds:
                return None
            if ds.status != DatasetStatus.RELEASED:
                raise ValueError(
                    f"Cannot archive dataset in {ds.status.value} status. Must be RELEASED."
                )
            data = ds.model_dump()
            data["status"] = DatasetStatus.ARCHIVED
            data["updated_at"] = now
            updated = ClinicalDataset(**data)
            self._datasets[dataset_id] = updated
            self._add_audit_entry(dataset_id, "ARCHIVE", "status", ds.status.value,
                                  DatasetStatus.ARCHIVED.value, "Archived for long-term storage", actor)
            return updated

    # ==================================================================
    # CDISC Domains & Conformance
    # ==================================================================

    def list_domains(self) -> list[CDISCDomain]:
        """List all known CDISC domains."""
        with self._lock:
            return list(self._domains.values())

    def get_domain(self, domain_name: str) -> Optional[CDISCDomain]:
        """Get a single CDISC domain."""
        with self._lock:
            return self._domains.get(domain_name)

    def run_conformance_check(self, dataset_id: str) -> Optional[CDISCConformanceReport]:
        """Run CDISC conformance checks against a dataset."""
        with self._lock:
            ds = self._datasets.get(dataset_id)
            if not ds:
                return None
            domains = list(self._domains.values())

        domain_results: list[CDISCDomainConformanceResult] = []
        total_issues = 0
        critical = 0
        warnings = 0
        info = 0

        for dom in domains:
            checks = max(5, dom.total_records // 100)
            failed = dom.conformance_issues
            issues_list = []
            for k in range(failed):
                issue_type = "CRITICAL" if k == 0 and failed > 2 else ("WARNING" if k < 2 else "INFO")
                issues_list.append(f"{issue_type}: {dom.name} variable check #{k + 1} failed")
                if issue_type == "CRITICAL":
                    critical += 1
                elif issue_type == "WARNING":
                    warnings += 1
                else:
                    info += 1
                total_issues += 1

            domain_results.append(CDISCDomainConformanceResult(
                domain=dom.name,
                total_checks=checks,
                passed=checks - failed,
                failed=failed,
                issues=issues_list,
            ))

        total_checks = sum(dr.total_checks for dr in domain_results)
        total_passed = sum(dr.passed for dr in domain_results)
        conformance_pct = (total_passed / total_checks * 100) if total_checks > 0 else 0.0

        return CDISCConformanceReport(
            dataset_id=dataset_id,
            dataset_name=ds.name,
            standard=ds.cdisc_standard,
            domains_checked=len(domains),
            total_issues=total_issues,
            critical_issues=critical,
            warning_issues=warnings,
            info_issues=info,
            conformance_percent=round(conformance_pct, 1),
            domain_results=domain_results,
        )

    # ==================================================================
    # Audit Trail
    # ==================================================================

    def _add_audit_entry(
        self,
        dataset_id: str,
        action: str,
        field_name: Optional[str],
        old_value: Optional[str],
        new_value: Optional[str],
        reason: Optional[str],
        actor: str,
    ) -> AuditTrailEntry:
        """Add an audit trail entry (must be called under _lock)."""
        entry = AuditTrailEntry(
            id=str(uuid4()),
            dataset_id=dataset_id,
            action=action,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            actor=actor,
            timestamp=datetime.now(timezone.utc),
        )
        self._audit_trail.append(entry)
        return entry

    def get_audit_trail(
        self,
        dataset_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditTrailEntry], int]:
        """List audit trail entries with optional filters."""
        with self._lock:
            items = list(self._audit_trail)

        if dataset_id:
            items = [e for e in items if e.dataset_id == dataset_id]
        if action:
            items = [e for e in items if e.action == action]

        total = len(items)
        items.sort(key=lambda e: e.timestamp, reverse=True)
        return items[offset:offset + limit], total

    # ==================================================================
    # Metrics
    # ==================================================================

    def get_cleaning_metrics(self, trial_id: str) -> DataCleaningMetrics:
        """Compute data cleaning metrics for a trial."""
        with self._lock:
            queries = [q for q in self._queries.values() if q.trial_id == trial_id]
            results = [r for r in self._results.values() if r.trial_id == trial_id]
            datasets = [d for d in self._datasets.values() if d.trial_id == trial_id]

        trial_name = datasets[0].trial_name if datasets else trial_id

        open_count = sum(1 for q in queries if q.status == QueryStatus.OPEN)
        answered_count = sum(1 for q in queries if q.status == QueryStatus.ANSWERED)
        closed_count = sum(1 for q in queries if q.status == QueryStatus.CLOSED)
        cancelled_count = sum(1 for q in queries if q.status == QueryStatus.CANCELLED)
        requeried_count = sum(1 for q in queries if q.status == QueryStatus.REQUERIED)
        auto_count = sum(1 for q in queries if q.auto_generated)

        total_queries = len(queries)
        # Simulate ~50 CRF pages per trial
        query_rate = total_queries / 50.0 if total_queries > 0 else 0.0
        auto_pct = (auto_count / total_queries * 100) if total_queries > 0 else 0.0

        cat_counts: dict[str, int] = {}
        for q in queries:
            cat_counts[q.query_category.value] = cat_counts.get(q.query_category.value, 0) + 1

        total_checks = len(results)
        failed_checks = sum(1 for r in results if not r.passed)
        pass_rate = ((total_checks - failed_checks) / total_checks * 100) if total_checks > 0 else 0.0

        completeness = datasets[0].completeness_percent if datasets else 0.0

        return DataCleaningMetrics(
            trial_id=trial_id,
            trial_name=trial_name,
            total_queries=total_queries,
            open_queries=open_count,
            answered_queries=answered_count,
            closed_queries=closed_count,
            cancelled_queries=cancelled_count,
            requeried_queries=requeried_count,
            query_rate_per_page=round(query_rate, 2),
            auto_generated_percent=round(auto_pct, 1),
            queries_by_category=cat_counts,
            validation_pass_rate=round(pass_rate, 1),
            total_validation_checks=total_checks,
            failed_validation_checks=failed_checks,
            data_completeness_percent=completeness,
        )

    def get_resolution_metrics(self, trial_id: str) -> QueryResolutionMetrics:
        """Compute query resolution metrics for a trial."""
        with self._lock:
            queries = [q for q in self._queries.values() if q.trial_id == trial_id]

        resolved = [q for q in queries if q.status == QueryStatus.CLOSED and q.opened_at and q.closed_at]
        resolution_days: list[float] = []
        within_7 = 0
        within_14 = 0
        after_14 = 0

        for q in resolved:
            days = (q.closed_at - q.opened_at).total_seconds() / 86400  # type: ignore[operator]
            resolution_days.append(days)
            if days <= 7:
                within_7 += 1
            elif days <= 14:
                within_14 += 1
            else:
                after_14 += 1

        avg_days = statistics.mean(resolution_days) if resolution_days else 0.0
        median_days = statistics.median(resolution_days) if resolution_days else 0.0

        requeried = sum(1 for q in queries if q.requery_count > 0)
        total = len(queries)
        requery_rate = (requeried / total * 100) if total > 0 else 0.0

        # Resolution time by category
        cat_times: dict[str, list[float]] = {}
        for q in resolved:
            days = (q.closed_at - q.opened_at).total_seconds() / 86400  # type: ignore[operator]
            cat = q.query_category.value
            cat_times.setdefault(cat, []).append(days)

        resolution_by_cat = {c: round(statistics.mean(times), 1) for c, times in cat_times.items()}

        return QueryResolutionMetrics(
            trial_id=trial_id,
            avg_resolution_days=round(avg_days, 1),
            median_resolution_days=round(median_days, 1),
            queries_resolved_within_7_days=within_7,
            queries_resolved_within_14_days=within_14,
            queries_resolved_after_14_days=after_14,
            total_resolved=len(resolved),
            requery_rate=round(requery_rate, 1),
            resolution_by_category=resolution_by_cat,
        )

    # ==================================================================
    # Dataset Comparison
    # ==================================================================

    def compare_datasets(self, dataset_a_id: str, dataset_b_id: str) -> Optional[DatasetComparisonResult]:
        """Compare two dataset versions."""
        with self._lock:
            ds_a = self._datasets.get(dataset_a_id)
            ds_b = self._datasets.get(dataset_b_id)

        if not ds_a or not ds_b:
            return None

        records_diff = abs(ds_b.total_records - ds_a.total_records)
        vars_diff = abs(ds_b.total_variables - ds_a.total_variables)
        completeness_delta = ds_b.completeness_percent - ds_a.completeness_percent
        conformance_delta = ds_b.conformance_percent - ds_a.conformance_percent

        # Simulate some changes
        added = max(0, ds_b.total_records - ds_a.total_records)
        removed = max(0, ds_a.total_records - ds_b.total_records)
        modified = int(min(ds_a.total_records, ds_b.total_records) * 0.05)

        vars_added = max(0, ds_b.total_variables - ds_a.total_variables)
        vars_removed = max(0, ds_a.total_variables - ds_b.total_variables)

        summary_parts = []
        if added:
            summary_parts.append(f"{added} records added")
        if removed:
            summary_parts.append(f"{removed} records removed")
        if modified:
            summary_parts.append(f"{modified} records modified")
        if completeness_delta != 0:
            summary_parts.append(f"completeness {'improved' if completeness_delta > 0 else 'decreased'} by {abs(completeness_delta):.1f}%")

        return DatasetComparisonResult(
            dataset_a_id=dataset_a_id,
            dataset_a_name=ds_a.name,
            dataset_b_id=dataset_b_id,
            dataset_b_name=ds_b.name,
            records_added=added,
            records_removed=removed,
            records_modified=modified,
            variables_added=vars_added,
            variables_removed=vars_removed,
            completeness_delta=round(completeness_delta, 1),
            conformance_delta=round(conformance_delta, 1),
            summary="; ".join(summary_parts) if summary_parts else "No differences detected",
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: Optional[ClinicalDataManagementService] = None
_service_lock = threading.Lock()


def get_clinical_data_management_service() -> ClinicalDataManagementService:
    """Return the singleton service instance (lazy init)."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = ClinicalDataManagementService()
    return _service


def reset_clinical_data_management_service() -> ClinicalDataManagementService:
    """Reset the singleton with fresh seed data (for tests)."""
    global _service
    with _service_lock:
        _service = ClinicalDataManagementService()
    return _service
