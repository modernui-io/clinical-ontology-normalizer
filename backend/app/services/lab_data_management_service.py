"""Lab Data Management Service (LAB-DATA).

Manages laboratory data operations: lab normal range definitions, lab alert
rules, specimen tracking, lab result management, reference range validation,
and lab data operational metrics.

Usage:
    from app.services.lab_data_management_service import (
        get_lab_data_management_service,
    )

    svc = get_lab_data_management_service()
    results = svc.list_results(trial_id="...")
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.lab_data_management import (
    AbnormalFlag,
    AlertSeverity,
    GradeLevel,
    LabAlert,
    LabAlertRule,
    LabAlertRuleCreate,
    LabAlertRuleUpdate,
    LabAlertUpdate,
    LabCategory,
    LabDataMetrics,
    LabNormalRange,
    LabNormalRangeCreate,
    LabResult,
    LabResultCreate,
    LabResultUpdate,
    LabSpecimen,
    LabSpecimenCreate,
    LabSpecimenUpdate,
    ResultStatus,
    SpecimenStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class LabDataManagementService:
    """In-memory Lab Data Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._normal_ranges: dict[str, LabNormalRange] = {}
        self._alert_rules: dict[str, LabAlertRule] = {}
        self._specimens: dict[str, LabSpecimen] = {}
        self._results: dict[str, LabResult] = {}
        self._alerts: dict[str, LabAlert] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic lab data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Normal Ranges ---
        ranges_data = [
            {"id": "NR-001", "test_name": "Hemoglobin", "test_code": "HGB", "category": LabCategory.HEMATOLOGY, "unit": "g/dL", "lower_limit": 12.0, "upper_limit": 17.5, "critical_low": 7.0, "critical_high": 20.0, "gender_specific": True, "gender": "M", "age_min": 18, "age_max": 99, "lab_id": "CLAB-001", "effective_date": now - timedelta(days=365), "source": "WHO Guidelines 2024"},
            {"id": "NR-002", "test_name": "Hemoglobin", "test_code": "HGB", "category": LabCategory.HEMATOLOGY, "unit": "g/dL", "lower_limit": 11.5, "upper_limit": 15.5, "critical_low": 7.0, "critical_high": 20.0, "gender_specific": True, "gender": "F", "age_min": 18, "age_max": 99, "lab_id": "CLAB-001", "effective_date": now - timedelta(days=365), "source": "WHO Guidelines 2024"},
            {"id": "NR-003", "test_name": "White Blood Cell Count", "test_code": "WBC", "category": LabCategory.HEMATOLOGY, "unit": "10^3/uL", "lower_limit": 4.5, "upper_limit": 11.0, "critical_low": 2.0, "critical_high": 30.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-001", "effective_date": now - timedelta(days=365), "source": "CLSI EP28-A3c"},
            {"id": "NR-004", "test_name": "Platelet Count", "test_code": "PLT", "category": LabCategory.HEMATOLOGY, "unit": "10^3/uL", "lower_limit": 150.0, "upper_limit": 400.0, "critical_low": 50.0, "critical_high": 1000.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-001", "effective_date": now - timedelta(days=365), "source": "CLSI EP28-A3c"},
            {"id": "NR-005", "test_name": "Alanine Aminotransferase", "test_code": "ALT", "category": LabCategory.HEPATIC, "unit": "U/L", "lower_limit": 7.0, "upper_limit": 56.0, "critical_low": None, "critical_high": 1000.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-002", "effective_date": now - timedelta(days=300), "source": "AACC Laboratory Reference Ranges"},
            {"id": "NR-006", "test_name": "Aspartate Aminotransferase", "test_code": "AST", "category": LabCategory.HEPATIC, "unit": "U/L", "lower_limit": 10.0, "upper_limit": 40.0, "critical_low": None, "critical_high": 1000.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-002", "effective_date": now - timedelta(days=300), "source": "AACC Laboratory Reference Ranges"},
            {"id": "NR-007", "test_name": "Creatinine", "test_code": "CREAT", "category": LabCategory.RENAL, "unit": "mg/dL", "lower_limit": 0.7, "upper_limit": 1.3, "critical_low": None, "critical_high": 10.0, "gender_specific": True, "gender": "M", "age_min": 18, "age_max": 99, "lab_id": "CLAB-002", "effective_date": now - timedelta(days=300), "source": "KDIGO Guidelines 2024"},
            {"id": "NR-008", "test_name": "Creatinine", "test_code": "CREAT", "category": LabCategory.RENAL, "unit": "mg/dL", "lower_limit": 0.6, "upper_limit": 1.1, "critical_low": None, "critical_high": 10.0, "gender_specific": True, "gender": "F", "age_min": 18, "age_max": 99, "lab_id": "CLAB-002", "effective_date": now - timedelta(days=300), "source": "KDIGO Guidelines 2024"},
            {"id": "NR-009", "test_name": "Total Cholesterol", "test_code": "CHOL", "category": LabCategory.LIPID, "unit": "mg/dL", "lower_limit": None, "upper_limit": 200.0, "critical_low": None, "critical_high": 500.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-003", "effective_date": now - timedelta(days=200), "source": "ACC/AHA Lipid Guidelines 2023"},
            {"id": "NR-010", "test_name": "Thyroid Stimulating Hormone", "test_code": "TSH", "category": LabCategory.ENDOCRINE, "unit": "mIU/L", "lower_limit": 0.4, "upper_limit": 4.0, "critical_low": 0.01, "critical_high": 100.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-003", "effective_date": now - timedelta(days=200), "source": "ATA Thyroid Guidelines 2023"},
            {"id": "NR-011", "test_name": "C-Reactive Protein", "test_code": "CRP", "category": LabCategory.IMMUNOLOGY, "unit": "mg/L", "lower_limit": None, "upper_limit": 5.0, "critical_low": None, "critical_high": 200.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-001", "effective_date": now - timedelta(days=180), "source": "EULAR Recommendations 2024"},
            {"id": "NR-012", "test_name": "Troponin I", "test_code": "TROP-I", "category": LabCategory.CARDIAC, "unit": "ng/mL", "lower_limit": None, "upper_limit": 0.04, "critical_low": None, "critical_high": 2.0, "gender_specific": False, "gender": None, "age_min": 18, "age_max": 99, "lab_id": "CLAB-002", "effective_date": now - timedelta(days=180), "source": "ESC/ACC Cardiac Biomarker Guidelines"},
        ]

        for r in ranges_data:
            self._normal_ranges[r["id"]] = LabNormalRange(**r)

        # --- 12 Alert Rules ---
        alert_rules_data = [
            {"id": "AR-001", "trial_id": EYLEA_TRIAL, "test_name": "Hemoglobin", "test_code": "HGB", "severity": AlertSeverity.CRITICAL, "condition": "value < 7.0", "threshold_value": 7.0, "threshold_unit": "g/dL", "grade_level": GradeLevel.GRADE_4, "action_required": "Notify PI immediately; consider transfusion", "notification_list": ["PI", "Medical Monitor", "Sponsor Safety"], "active": True, "created_by": "Dr. Sarah Kim", "created_at": now - timedelta(days=90)},
            {"id": "AR-002", "trial_id": EYLEA_TRIAL, "test_name": "ALT", "test_code": "ALT", "severity": AlertSeverity.HIGH, "condition": "value > 3x ULN", "threshold_value": 168.0, "threshold_unit": "U/L", "grade_level": GradeLevel.GRADE_3, "action_required": "Hold treatment; obtain hepatic panel; report to medical monitor", "notification_list": ["PI", "Medical Monitor"], "active": True, "created_by": "Dr. Sarah Kim", "created_at": now - timedelta(days=90)},
            {"id": "AR-003", "trial_id": EYLEA_TRIAL, "test_name": "Platelet Count", "test_code": "PLT", "severity": AlertSeverity.HIGH, "condition": "value < 75", "threshold_value": 75.0, "threshold_unit": "10^3/uL", "grade_level": GradeLevel.GRADE_3, "action_required": "Monitor closely; consider dose modification", "notification_list": ["PI", "Medical Monitor"], "active": True, "created_by": "Dr. Sarah Kim", "created_at": now - timedelta(days=85)},
            {"id": "AR-004", "trial_id": EYLEA_TRIAL, "test_name": "Creatinine", "test_code": "CREAT", "severity": AlertSeverity.MEDIUM, "condition": "value > 2x ULN", "threshold_value": 2.6, "threshold_unit": "mg/dL", "grade_level": GradeLevel.GRADE_2, "action_required": "Repeat test in 48 hours; monitor renal function", "notification_list": ["PI"], "active": True, "created_by": "Dr. James Lin", "created_at": now - timedelta(days=80)},
            {"id": "AR-005", "trial_id": DUPIXENT_TRIAL, "test_name": "Hemoglobin", "test_code": "HGB", "severity": AlertSeverity.CRITICAL, "condition": "value < 7.0", "threshold_value": 7.0, "threshold_unit": "g/dL", "grade_level": GradeLevel.GRADE_4, "action_required": "Notify PI immediately; evaluate for blood loss", "notification_list": ["PI", "Medical Monitor", "Sponsor Safety"], "active": True, "created_by": "Dr. Angela Martinez", "created_at": now - timedelta(days=75)},
            {"id": "AR-006", "trial_id": DUPIXENT_TRIAL, "test_name": "WBC", "test_code": "WBC", "severity": AlertSeverity.HIGH, "condition": "value < 2.0", "threshold_value": 2.0, "threshold_unit": "10^3/uL", "grade_level": GradeLevel.GRADE_3, "action_required": "Hold study drug; obtain differential; consider G-CSF", "notification_list": ["PI", "Medical Monitor"], "active": True, "created_by": "Dr. Angela Martinez", "created_at": now - timedelta(days=75)},
            {"id": "AR-007", "trial_id": DUPIXENT_TRIAL, "test_name": "CRP", "test_code": "CRP", "severity": AlertSeverity.MEDIUM, "condition": "value > 50.0", "threshold_value": 50.0, "threshold_unit": "mg/L", "grade_level": GradeLevel.GRADE_2, "action_required": "Assess for infection; consider discontinuation", "notification_list": ["PI"], "active": True, "created_by": "Dr. Angela Martinez", "created_at": now - timedelta(days=70)},
            {"id": "AR-008", "trial_id": DUPIXENT_TRIAL, "test_name": "IgE Total", "test_code": "IGE", "severity": AlertSeverity.INFO, "condition": "value > 5000", "threshold_value": 5000.0, "threshold_unit": "IU/mL", "grade_level": None, "action_required": "Note in eCRF; discuss at next monitoring visit", "notification_list": ["PI"], "active": True, "created_by": "Dr. David Park", "created_at": now - timedelta(days=65)},
            {"id": "AR-009", "trial_id": LIBTAYO_TRIAL, "test_name": "ALT", "test_code": "ALT", "severity": AlertSeverity.CRITICAL, "condition": "value > 10x ULN", "threshold_value": 560.0, "threshold_unit": "U/L", "grade_level": GradeLevel.GRADE_4, "action_required": "Discontinue study drug; initiate hepatotoxicity workup; SAE reporting", "notification_list": ["PI", "Medical Monitor", "Sponsor Safety", "DSMB"], "active": True, "created_by": "Dr. Catherine Liu", "created_at": now - timedelta(days=60)},
            {"id": "AR-010", "trial_id": LIBTAYO_TRIAL, "test_name": "TSH", "test_code": "TSH", "severity": AlertSeverity.HIGH, "condition": "value > 10.0 or value < 0.1", "threshold_value": 10.0, "threshold_unit": "mIU/L", "grade_level": GradeLevel.GRADE_3, "action_required": "Evaluate for immune-related thyroiditis; endocrine consult", "notification_list": ["PI", "Medical Monitor"], "active": True, "created_by": "Dr. Catherine Liu", "created_at": now - timedelta(days=55)},
            {"id": "AR-011", "trial_id": LIBTAYO_TRIAL, "test_name": "Troponin I", "test_code": "TROP-I", "severity": AlertSeverity.PANIC, "condition": "value > 0.5", "threshold_value": 0.5, "threshold_unit": "ng/mL", "grade_level": GradeLevel.GRADE_4, "action_required": "URGENT: evaluate for myocarditis; cardiology consult; hold immunotherapy", "notification_list": ["PI", "Medical Monitor", "Sponsor Safety", "DSMB", "Cardiology"], "active": True, "created_by": "Dr. Catherine Liu", "created_at": now - timedelta(days=50)},
            {"id": "AR-012", "trial_id": LIBTAYO_TRIAL, "test_name": "Creatinine", "test_code": "CREAT", "severity": AlertSeverity.HIGH, "condition": "value > 3x baseline", "threshold_value": 3.0, "threshold_unit": "mg/dL", "grade_level": GradeLevel.GRADE_3, "action_required": "Evaluate for immune-related nephritis; consider biopsy", "notification_list": ["PI", "Medical Monitor"], "active": False, "created_by": "Dr. Andrew Foster", "created_at": now - timedelta(days=45)},
        ]

        for ar in alert_rules_data:
            self._alert_rules[ar["id"]] = LabAlertRule(**ar)

        # --- 15 Specimens ---
        specimens_data = [
            {"id": "SPEC-001", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "visit": "Screening", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=120), "collection_time": "08:15", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "Covance Central Lab", "accession_number": "ACC-2024-0001", "received_date": now - timedelta(days=118), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-101"},
            {"id": "SPEC-002", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "visit": "Week 4", "specimen_type": "Serum", "collection_date": now - timedelta(days=90), "collection_time": "08:30", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "Covance Central Lab", "accession_number": "ACC-2024-0002", "received_date": now - timedelta(days=88), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-101"},
            {"id": "SPEC-003", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1002", "visit": "Screening", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=115), "collection_time": "09:00", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "Covance Central Lab", "accession_number": "ACC-2024-0003", "received_date": now - timedelta(days=113), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-102"},
            {"id": "SPEC-004", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1003", "visit": "Week 8", "specimen_type": "Urine", "collection_date": now - timedelta(days=60), "collection_time": "07:45", "fasting": False, "status": SpecimenStatus.RECEIVED, "central_lab": "Covance Central Lab", "accession_number": "ACC-2024-0004", "received_date": now - timedelta(days=58), "condition_on_receipt": "Hemolyzed", "storage_temperature": "Room Temperature", "site_id": "SITE-103"},
            {"id": "SPEC-005", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1004", "visit": "Week 12", "specimen_type": "Plasma", "collection_date": now - timedelta(days=30), "collection_time": "10:00", "fasting": True, "status": SpecimenStatus.IN_TRANSIT, "central_lab": "Covance Central Lab", "accession_number": None, "received_date": None, "condition_on_receipt": None, "storage_temperature": "-20C", "site_id": "SITE-101"},
            {"id": "SPEC-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2001", "visit": "Screening", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=100), "collection_time": "08:00", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "Q2 Solutions", "accession_number": "ACC-2024-0006", "received_date": now - timedelta(days=98), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-104"},
            {"id": "SPEC-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2001", "visit": "Week 16", "specimen_type": "Serum", "collection_date": now - timedelta(days=50), "collection_time": "08:45", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "Q2 Solutions", "accession_number": "ACC-2024-0007", "received_date": now - timedelta(days=48), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-104"},
            {"id": "SPEC-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2002", "visit": "Screening", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=95), "collection_time": "09:15", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "Q2 Solutions", "accession_number": "ACC-2024-0008", "received_date": now - timedelta(days=93), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-105"},
            {"id": "SPEC-009", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2003", "visit": "Week 4", "specimen_type": "Plasma", "collection_date": now - timedelta(days=40), "collection_time": "07:30", "fasting": True, "status": SpecimenStatus.PROCESSING, "central_lab": "Q2 Solutions", "accession_number": "ACC-2024-0009", "received_date": now - timedelta(days=38), "condition_on_receipt": "Acceptable", "storage_temperature": "-20C", "site_id": "SITE-106"},
            {"id": "SPEC-010", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2004", "visit": "Week 8", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=20), "collection_time": "08:00", "fasting": True, "status": SpecimenStatus.COLLECTED, "central_lab": "Q2 Solutions", "accession_number": None, "received_date": None, "condition_on_receipt": None, "storage_temperature": "2-8C", "site_id": "SITE-105"},
            {"id": "SPEC-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "visit": "Cycle 1 Day 1", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=110), "collection_time": "07:00", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "ICON Central Lab", "accession_number": "ACC-2024-0011", "received_date": now - timedelta(days=108), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-107"},
            {"id": "SPEC-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "visit": "Cycle 4 Day 1", "specimen_type": "Serum", "collection_date": now - timedelta(days=50), "collection_time": "07:30", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "ICON Central Lab", "accession_number": "ACC-2024-0012", "received_date": now - timedelta(days=48), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-107"},
            {"id": "SPEC-013", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3002", "visit": "Cycle 1 Day 1", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=105), "collection_time": "08:00", "fasting": True, "status": SpecimenStatus.ANALYZED, "central_lab": "ICON Central Lab", "accession_number": "ACC-2024-0013", "received_date": now - timedelta(days=103), "condition_on_receipt": "Acceptable", "storage_temperature": "2-8C", "site_id": "SITE-108"},
            {"id": "SPEC-014", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3003", "visit": "Cycle 2 Day 1", "specimen_type": "Urine", "collection_date": now - timedelta(days=70), "collection_time": "06:30", "fasting": False, "status": SpecimenStatus.STORED, "central_lab": "ICON Central Lab", "accession_number": "ACC-2024-0014", "received_date": now - timedelta(days=68), "condition_on_receipt": "Acceptable", "storage_temperature": "-80C", "site_id": "SITE-108"},
            {"id": "SPEC-015", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3004", "visit": "Cycle 3 Day 1", "specimen_type": "Whole Blood", "collection_date": now - timedelta(days=10), "collection_time": "09:00", "fasting": True, "status": SpecimenStatus.LOST, "central_lab": "ICON Central Lab", "accession_number": None, "received_date": None, "condition_on_receipt": None, "storage_temperature": None, "site_id": "SITE-107"},
        ]

        for s in specimens_data:
            self._specimens[s["id"]] = LabSpecimen(**s)

        # --- 18 Lab Results ---
        results_data = [
            {"id": "RES-001", "specimen_id": "SPEC-001", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "test_name": "Hemoglobin", "test_code": "HGB", "category": LabCategory.HEMATOLOGY, "value": 14.2, "value_text": None, "unit": "g/dL", "reference_low": 12.0, "reference_high": 17.5, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=117), "verified_by": "Dr. Anna Brooks", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-002", "specimen_id": "SPEC-001", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "test_name": "WBC", "test_code": "WBC", "category": LabCategory.HEMATOLOGY, "value": 7.8, "value_text": None, "unit": "10^3/uL", "reference_low": 4.5, "reference_high": 11.0, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=117), "verified_by": "Dr. Anna Brooks", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-003", "specimen_id": "SPEC-001", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "test_name": "Platelet Count", "test_code": "PLT", "category": LabCategory.HEMATOLOGY, "value": 245.0, "value_text": None, "unit": "10^3/uL", "reference_low": 150.0, "reference_high": 400.0, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=117), "verified_by": "Dr. Anna Brooks", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-004", "specimen_id": "SPEC-002", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "test_name": "ALT", "test_code": "ALT", "category": LabCategory.HEPATIC, "value": 85.0, "value_text": None, "unit": "U/L", "reference_low": 7.0, "reference_high": 56.0, "abnormal_flag": AbnormalFlag.HIGH, "grade": GradeLevel.GRADE_1, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=87), "verified_by": "Dr. Anna Brooks", "clinically_significant": True, "investigator_comment": "Mild transaminase elevation; continue monitoring"},
            {"id": "RES-005", "specimen_id": "SPEC-002", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "test_name": "AST", "test_code": "AST", "category": LabCategory.HEPATIC, "value": 52.0, "value_text": None, "unit": "U/L", "reference_low": 10.0, "reference_high": 40.0, "abnormal_flag": AbnormalFlag.HIGH, "grade": GradeLevel.GRADE_1, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=87), "verified_by": "Dr. Anna Brooks", "clinically_significant": True, "investigator_comment": "Consistent with ALT elevation"},
            {"id": "RES-006", "specimen_id": "SPEC-003", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1002", "test_name": "Hemoglobin", "test_code": "HGB", "category": LabCategory.HEMATOLOGY, "value": 10.8, "value_text": None, "unit": "g/dL", "reference_low": 11.5, "reference_high": 15.5, "abnormal_flag": AbnormalFlag.LOW, "grade": GradeLevel.GRADE_1, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=112), "verified_by": "Dr. Tom Chen", "clinically_significant": True, "investigator_comment": "Mild anemia; check iron studies"},
            {"id": "RES-007", "specimen_id": "SPEC-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2001", "test_name": "Hemoglobin", "test_code": "HGB", "category": LabCategory.HEMATOLOGY, "value": 13.5, "value_text": None, "unit": "g/dL", "reference_low": 12.0, "reference_high": 17.5, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=97), "verified_by": "Dr. Lisa Wang", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-008", "specimen_id": "SPEC-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2001", "test_name": "WBC", "test_code": "WBC", "category": LabCategory.HEMATOLOGY, "value": 5.2, "value_text": None, "unit": "10^3/uL", "reference_low": 4.5, "reference_high": 11.0, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=97), "verified_by": "Dr. Lisa Wang", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-009", "specimen_id": "SPEC-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2001", "test_name": "CRP", "test_code": "CRP", "category": LabCategory.IMMUNOLOGY, "value": 62.0, "value_text": None, "unit": "mg/L", "reference_low": None, "reference_high": 5.0, "abnormal_flag": AbnormalFlag.CRITICAL_HIGH, "grade": GradeLevel.GRADE_3, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=47), "verified_by": "Dr. Lisa Wang", "clinically_significant": True, "investigator_comment": "Significant inflammation; assess for infection vs flare"},
            {"id": "RES-010", "specimen_id": "SPEC-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2002", "test_name": "Hemoglobin", "test_code": "HGB", "category": LabCategory.HEMATOLOGY, "value": 14.8, "value_text": None, "unit": "g/dL", "reference_low": 12.0, "reference_high": 17.5, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=92), "verified_by": "Dr. Lisa Wang", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-011", "specimen_id": "SPEC-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2002", "test_name": "ALT", "test_code": "ALT", "category": LabCategory.HEPATIC, "value": 32.0, "value_text": None, "unit": "U/L", "reference_low": 7.0, "reference_high": 56.0, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=92), "verified_by": "Dr. Lisa Wang", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-012", "specimen_id": "SPEC-009", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2003", "test_name": "Creatinine", "test_code": "CREAT", "category": LabCategory.RENAL, "value": 1.5, "value_text": None, "unit": "mg/dL", "reference_low": 0.7, "reference_high": 1.3, "abnormal_flag": AbnormalFlag.HIGH, "grade": GradeLevel.GRADE_1, "status": ResultStatus.PRELIMINARY, "result_date": now - timedelta(days=37), "verified_by": None, "clinically_significant": None, "investigator_comment": None},
            {"id": "RES-013", "specimen_id": "SPEC-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "test_name": "Hemoglobin", "test_code": "HGB", "category": LabCategory.HEMATOLOGY, "value": 11.2, "value_text": None, "unit": "g/dL", "reference_low": 12.0, "reference_high": 17.5, "abnormal_flag": AbnormalFlag.LOW, "grade": GradeLevel.GRADE_1, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=107), "verified_by": "Dr. Mark Evans", "clinically_significant": True, "investigator_comment": "Anemia likely treatment-related; monitor closely"},
            {"id": "RES-014", "specimen_id": "SPEC-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "test_name": "TSH", "test_code": "TSH", "category": LabCategory.ENDOCRINE, "value": 18.5, "value_text": None, "unit": "mIU/L", "reference_low": 0.4, "reference_high": 4.0, "abnormal_flag": AbnormalFlag.CRITICAL_HIGH, "grade": GradeLevel.GRADE_3, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=47), "verified_by": "Dr. Mark Evans", "clinically_significant": True, "investigator_comment": "Suspected immune-related thyroiditis; endocrine consult ordered"},
            {"id": "RES-015", "specimen_id": "SPEC-013", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3002", "test_name": "ALT", "test_code": "ALT", "category": LabCategory.HEPATIC, "value": 620.0, "value_text": None, "unit": "U/L", "reference_low": 7.0, "reference_high": 56.0, "abnormal_flag": AbnormalFlag.CRITICAL_HIGH, "grade": GradeLevel.GRADE_4, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=102), "verified_by": "Dr. Mark Evans", "clinically_significant": True, "investigator_comment": "Severe hepatotoxicity; study drug discontinued; SAE reported"},
            {"id": "RES-016", "specimen_id": "SPEC-013", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3002", "test_name": "Troponin I", "test_code": "TROP-I", "category": LabCategory.CARDIAC, "value": 0.85, "value_text": None, "unit": "ng/mL", "reference_low": None, "reference_high": 0.04, "abnormal_flag": AbnormalFlag.CRITICAL_HIGH, "grade": GradeLevel.GRADE_4, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=102), "verified_by": "Dr. Mark Evans", "clinically_significant": True, "investigator_comment": "Elevated troponin; cardiology consult for myocarditis workup"},
            {"id": "RES-017", "specimen_id": "SPEC-014", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3003", "test_name": "Creatinine", "test_code": "CREAT", "category": LabCategory.RENAL, "value": 0.9, "value_text": None, "unit": "mg/dL", "reference_low": 0.6, "reference_high": 1.1, "abnormal_flag": AbnormalFlag.NORMAL, "grade": GradeLevel.GRADE_0, "status": ResultStatus.FINAL, "result_date": now - timedelta(days=67), "verified_by": "Dr. Mark Evans", "clinically_significant": False, "investigator_comment": None},
            {"id": "RES-018", "specimen_id": "SPEC-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "test_name": "WBC", "test_code": "WBC", "category": LabCategory.HEMATOLOGY, "value": 3.1, "value_text": None, "unit": "10^3/uL", "reference_low": 4.5, "reference_high": 11.0, "abnormal_flag": AbnormalFlag.LOW, "grade": GradeLevel.GRADE_1, "status": ResultStatus.PENDING, "result_date": None, "verified_by": None, "clinically_significant": None, "investigator_comment": None},
        ]

        for r in results_data:
            self._results[r["id"]] = LabResult(**r)

        # --- 10 Alerts ---
        alerts_data = [
            {"id": "ALERT-001", "result_id": "RES-004", "rule_id": "AR-002", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "severity": AlertSeverity.HIGH, "message": "ALT elevated to 85 U/L (>1.5x ULN). Grade 1 hepatotoxicity.", "acknowledged": True, "acknowledged_by": "Dr. Sarah Kim", "acknowledged_date": now - timedelta(days=86), "action_taken": "Treatment continued; repeat labs in 2 weeks", "generated_date": now - timedelta(days=87)},
            {"id": "ALERT-002", "result_id": "RES-006", "rule_id": "AR-001", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1002", "severity": AlertSeverity.MEDIUM, "message": "Hemoglobin low at 10.8 g/dL. Mild anemia detected.", "acknowledged": True, "acknowledged_by": "Dr. Tom Chen", "acknowledged_date": now - timedelta(days=111), "action_taken": "Iron studies ordered; nutritional assessment", "generated_date": now - timedelta(days=112)},
            {"id": "ALERT-003", "result_id": "RES-009", "rule_id": "AR-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2001", "severity": AlertSeverity.HIGH, "message": "CRP critically elevated to 62 mg/L (>50 mg/L threshold). Grade 3.", "acknowledged": True, "acknowledged_by": "Dr. Angela Martinez", "acknowledged_date": now - timedelta(days=46), "action_taken": "Infection workup initiated; blood cultures pending", "generated_date": now - timedelta(days=47)},
            {"id": "ALERT-004", "result_id": "RES-012", "rule_id": "AR-004", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2003", "severity": AlertSeverity.MEDIUM, "message": "Creatinine elevated to 1.5 mg/dL. Above reference range.", "acknowledged": False, "acknowledged_by": None, "acknowledged_date": None, "action_taken": None, "generated_date": now - timedelta(days=37)},
            {"id": "ALERT-005", "result_id": "RES-013", "rule_id": "AR-001", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "severity": AlertSeverity.MEDIUM, "message": "Hemoglobin low at 11.2 g/dL. Possible treatment-related anemia.", "acknowledged": True, "acknowledged_by": "Dr. Mark Evans", "acknowledged_date": now - timedelta(days=106), "action_taken": "Monitoring continued; consider dose adjustment if worsens", "generated_date": now - timedelta(days=107)},
            {"id": "ALERT-006", "result_id": "RES-014", "rule_id": "AR-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "severity": AlertSeverity.HIGH, "message": "TSH elevated to 18.5 mIU/L (>10.0 threshold). Suspected immune-related thyroiditis.", "acknowledged": True, "acknowledged_by": "Dr. Catherine Liu", "acknowledged_date": now - timedelta(days=46), "action_taken": "Endocrine consult ordered; levothyroxine initiated", "generated_date": now - timedelta(days=47)},
            {"id": "ALERT-007", "result_id": "RES-015", "rule_id": "AR-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3002", "severity": AlertSeverity.CRITICAL, "message": "ALT critically elevated to 620 U/L (>10x ULN). GRADE 4 hepatotoxicity.", "acknowledged": True, "acknowledged_by": "Dr. Catherine Liu", "acknowledged_date": now - timedelta(days=101), "action_taken": "Study drug permanently discontinued; SAE reported; hepatology consult", "generated_date": now - timedelta(days=102)},
            {"id": "ALERT-008", "result_id": "RES-016", "rule_id": "AR-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3002", "severity": AlertSeverity.PANIC, "message": "PANIC: Troponin I at 0.85 ng/mL (>0.5 threshold). Possible myocarditis.", "acknowledged": True, "acknowledged_by": "Dr. Catherine Liu", "acknowledged_date": now - timedelta(days=101), "action_taken": "Emergent cardiology consult; echocardiogram ordered; immunotherapy held", "generated_date": now - timedelta(days=102)},
            {"id": "ALERT-009", "result_id": "RES-018", "rule_id": "AR-006", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "severity": AlertSeverity.MEDIUM, "message": "WBC low at 3.1 (below normal range). Monitor for neutropenia.", "acknowledged": False, "acknowledged_by": None, "acknowledged_date": None, "action_taken": None, "generated_date": now - timedelta(days=47)},
            {"id": "ALERT-010", "result_id": "RES-005", "rule_id": "AR-002", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "severity": AlertSeverity.LOW, "message": "AST mildly elevated to 52 U/L. Grade 1; concurrent with ALT elevation.", "acknowledged": True, "acknowledged_by": "Dr. Anna Brooks", "acknowledged_date": now - timedelta(days=86), "action_taken": "Continue monitoring; correlates with ALT elevation in ALERT-001", "generated_date": now - timedelta(days=87)},
        ]

        for a in alerts_data:
            self._alerts[a["id"]] = LabAlert(**a)

    # ------------------------------------------------------------------
    # Normal Range CRUD
    # ------------------------------------------------------------------

    def list_normal_ranges(
        self,
        *,
        category: LabCategory | None = None,
        test_code: str | None = None,
    ) -> list[LabNormalRange]:
        """List normal ranges with optional filters."""
        with self._lock:
            result = list(self._normal_ranges.values())
        if category is not None:
            result = [r for r in result if r.category == category]
        if test_code is not None:
            result = [r for r in result if r.test_code == test_code]
        return sorted(result, key=lambda r: r.id)

    def get_normal_range(self, range_id: str) -> LabNormalRange | None:
        """Get a single normal range by ID."""
        with self._lock:
            return self._normal_ranges.get(range_id)

    def create_normal_range(self, payload: LabNormalRangeCreate) -> LabNormalRange:
        """Create a new normal range."""
        range_id = f"NR-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        normal_range = LabNormalRange(
            id=range_id,
            test_name=payload.test_name,
            test_code=payload.test_code,
            category=payload.category,
            unit=payload.unit,
            lower_limit=payload.lower_limit,
            upper_limit=payload.upper_limit,
            critical_low=payload.critical_low,
            critical_high=payload.critical_high,
            gender_specific=payload.gender_specific,
            gender=payload.gender,
            age_min=None,
            age_max=None,
            lab_id=None,
            effective_date=now,
            source=payload.source,
        )
        with self._lock:
            self._normal_ranges[range_id] = normal_range
        logger.info("Created normal range %s: %s", range_id, payload.test_name)
        return normal_range

    def update_normal_range(
        self, range_id: str, payload: LabNormalRangeCreate
    ) -> LabNormalRange | None:
        """Update an existing normal range."""
        with self._lock:
            existing = self._normal_ranges.get(range_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabNormalRange(**data)
            self._normal_ranges[range_id] = updated
        return updated

    def delete_normal_range(self, range_id: str) -> bool:
        """Delete a normal range. Returns True if deleted."""
        with self._lock:
            if range_id in self._normal_ranges:
                del self._normal_ranges[range_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Alert Rule CRUD
    # ------------------------------------------------------------------

    def list_alert_rules(
        self,
        *,
        trial_id: str | None = None,
        active: bool | None = None,
    ) -> list[LabAlertRule]:
        """List alert rules with optional filters."""
        with self._lock:
            result = list(self._alert_rules.values())
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if active is not None:
            result = [r for r in result if r.active == active]
        return sorted(result, key=lambda r: r.id)

    def get_alert_rule(self, rule_id: str) -> LabAlertRule | None:
        """Get a single alert rule by ID."""
        with self._lock:
            return self._alert_rules.get(rule_id)

    def create_alert_rule(self, payload: LabAlertRuleCreate) -> LabAlertRule:
        """Create a new alert rule."""
        rule_id = f"AR-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        rule = LabAlertRule(
            id=rule_id,
            trial_id=payload.trial_id,
            test_name=payload.test_name,
            test_code=payload.test_code,
            severity=payload.severity,
            condition=payload.condition,
            threshold_value=payload.threshold_value,
            threshold_unit=payload.threshold_unit,
            grade_level=None,
            action_required=payload.action_required,
            notification_list=payload.notification_list,
            active=True,
            created_by=payload.created_by,
            created_at=now,
        )
        with self._lock:
            self._alert_rules[rule_id] = rule
        logger.info("Created alert rule %s: %s for trial %s", rule_id, payload.test_name, payload.trial_id)
        return rule

    def update_alert_rule(
        self, rule_id: str, payload: LabAlertRuleUpdate
    ) -> LabAlertRule | None:
        """Update an existing alert rule."""
        with self._lock:
            existing = self._alert_rules.get(rule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabAlertRule(**data)
            self._alert_rules[rule_id] = updated
        return updated

    def delete_alert_rule(self, rule_id: str) -> bool:
        """Delete an alert rule. Returns True if deleted."""
        with self._lock:
            if rule_id in self._alert_rules:
                del self._alert_rules[rule_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Specimen CRUD
    # ------------------------------------------------------------------

    def list_specimens(
        self,
        *,
        trial_id: str | None = None,
        status: SpecimenStatus | None = None,
        subject_id: str | None = None,
    ) -> list[LabSpecimen]:
        """List specimens with optional filters."""
        with self._lock:
            result = list(self._specimens.values())
        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if subject_id is not None:
            result = [s for s in result if s.subject_id == subject_id]
        return sorted(result, key=lambda s: s.id)

    def get_specimen(self, specimen_id: str) -> LabSpecimen | None:
        """Get a single specimen by ID."""
        with self._lock:
            return self._specimens.get(specimen_id)

    def create_specimen(self, payload: LabSpecimenCreate) -> LabSpecimen:
        """Create a new specimen."""
        specimen_id = f"SPEC-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        specimen = LabSpecimen(
            id=specimen_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            visit=payload.visit,
            specimen_type=payload.specimen_type,
            collection_date=now,
            collection_time=None,
            fasting=payload.fasting,
            status=SpecimenStatus.COLLECTED,
            central_lab=payload.central_lab,
            accession_number=None,
            received_date=None,
            condition_on_receipt=None,
            storage_temperature=None,
            site_id=payload.site_id,
        )
        with self._lock:
            self._specimens[specimen_id] = specimen
        logger.info("Created specimen %s for subject %s", specimen_id, payload.subject_id)
        return specimen

    def update_specimen(
        self, specimen_id: str, payload: LabSpecimenUpdate
    ) -> LabSpecimen | None:
        """Update an existing specimen."""
        with self._lock:
            existing = self._specimens.get(specimen_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabSpecimen(**data)
            self._specimens[specimen_id] = updated
        return updated

    def delete_specimen(self, specimen_id: str) -> bool:
        """Delete a specimen. Returns True if deleted."""
        with self._lock:
            if specimen_id in self._specimens:
                del self._specimens[specimen_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Result CRUD
    # ------------------------------------------------------------------

    def list_results(
        self,
        *,
        trial_id: str | None = None,
        status: ResultStatus | None = None,
        subject_id: str | None = None,
        category: LabCategory | None = None,
        abnormal_flag: AbnormalFlag | None = None,
    ) -> list[LabResult]:
        """List results with optional filters."""
        with self._lock:
            result = list(self._results.values())
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        if subject_id is not None:
            result = [r for r in result if r.subject_id == subject_id]
        if category is not None:
            result = [r for r in result if r.category == category]
        if abnormal_flag is not None:
            result = [r for r in result if r.abnormal_flag == abnormal_flag]
        return sorted(result, key=lambda r: r.id)

    def get_result(self, result_id: str) -> LabResult | None:
        """Get a single result by ID."""
        with self._lock:
            return self._results.get(result_id)

    def create_result(self, payload: LabResultCreate) -> LabResult:
        """Create a new lab result."""
        result_id = f"RES-{uuid4().hex[:8].upper()}"
        lab_result = LabResult(
            id=result_id,
            specimen_id=payload.specimen_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            test_name=payload.test_name,
            test_code=payload.test_code,
            category=payload.category,
            value=payload.value,
            value_text=payload.value_text,
            unit=payload.unit,
            reference_low=None,
            reference_high=None,
            abnormal_flag=AbnormalFlag.NORMAL,
            grade=None,
            status=ResultStatus.PENDING,
            result_date=None,
            verified_by=None,
            clinically_significant=None,
            investigator_comment=None,
        )
        with self._lock:
            self._results[result_id] = lab_result
        logger.info("Created result %s: %s for subject %s", result_id, payload.test_name, payload.subject_id)
        return lab_result

    def update_result(
        self, result_id: str, payload: LabResultUpdate
    ) -> LabResult | None:
        """Update an existing lab result."""
        with self._lock:
            existing = self._results.get(result_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabResult(**data)
            self._results[result_id] = updated
        return updated

    def delete_result(self, result_id: str) -> bool:
        """Delete a result. Returns True if deleted."""
        with self._lock:
            if result_id in self._results:
                del self._results[result_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Alert CRUD
    # ------------------------------------------------------------------

    def list_alerts(
        self,
        *,
        trial_id: str | None = None,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
    ) -> list[LabAlert]:
        """List alerts with optional filters."""
        with self._lock:
            result = list(self._alerts.values())
        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if severity is not None:
            result = [a for a in result if a.severity == severity]
        if acknowledged is not None:
            result = [a for a in result if a.acknowledged == acknowledged]
        return sorted(result, key=lambda a: a.id)

    def get_alert(self, alert_id: str) -> LabAlert | None:
        """Get a single alert by ID."""
        with self._lock:
            return self._alerts.get(alert_id)

    def create_alert(
        self,
        *,
        result_id: str,
        rule_id: str,
        trial_id: str,
        subject_id: str,
        severity: AlertSeverity,
        message: str,
    ) -> LabAlert:
        """Create a new lab alert."""
        alert_id = f"ALERT-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        alert = LabAlert(
            id=alert_id,
            result_id=result_id,
            rule_id=rule_id,
            trial_id=trial_id,
            subject_id=subject_id,
            severity=severity,
            message=message,
            acknowledged=False,
            acknowledged_by=None,
            acknowledged_date=None,
            action_taken=None,
            generated_date=now,
        )
        with self._lock:
            self._alerts[alert_id] = alert
        logger.info("Created alert %s: %s", alert_id, message[:80])
        return alert

    def update_alert(
        self, alert_id: str, payload: LabAlertUpdate
    ) -> LabAlert | None:
        """Update an existing alert (typically to acknowledge)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._alerts.get(alert_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set acknowledged_date when acknowledging
            if updates.get("acknowledged") is True and not existing.acknowledged:
                updates["acknowledged_date"] = now
            data.update(updates)
            updated = LabAlert(**data)
            self._alerts[alert_id] = updated
        return updated

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert. Returns True if deleted."""
        with self._lock:
            if alert_id in self._alerts:
                del self._alerts[alert_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> LabDataMetrics:
        """Compute aggregated lab data metrics."""
        with self._lock:
            ranges = list(self._normal_ranges.values())
            rules = list(self._alert_rules.values())
            specimens = list(self._specimens.values())
            results = list(self._results.values())
            alerts = list(self._alerts.values())

        # Filter by trial_id where applicable
        if trial_id is not None:
            rules = [r for r in rules if r.trial_id == trial_id]
            specimens = [s for s in specimens if s.trial_id == trial_id]
            results = [r for r in results if r.trial_id == trial_id]
            alerts = [a for a in alerts if a.trial_id == trial_id]

        # Ranges by category
        ranges_by_category: dict[str, int] = {}
        for r in ranges:
            key = r.category.value
            ranges_by_category[key] = ranges_by_category.get(key, 0) + 1

        # Specimens by status
        specimens_by_status: dict[str, int] = {}
        for s in specimens:
            key = s.status.value
            specimens_by_status[key] = specimens_by_status.get(key, 0) + 1

        # Results by status
        results_by_status: dict[str, int] = {}
        for r in results:
            key = r.status.value
            results_by_status[key] = results_by_status.get(key, 0) + 1

        # Results by flag
        results_by_flag: dict[str, int] = {}
        for r in results:
            key = r.abnormal_flag.value
            results_by_flag[key] = results_by_flag.get(key, 0) + 1

        # Abnormal rate
        total_results = len(results)
        abnormal_count = sum(
            1 for r in results if r.abnormal_flag != AbnormalFlag.NORMAL
        )
        abnormal_rate = (
            round(abnormal_count / total_results * 100.0, 1)
            if total_results > 0
            else 0.0
        )

        # Critical results
        critical_results = sum(
            1
            for r in results
            if r.abnormal_flag
            in (AbnormalFlag.CRITICAL_LOW, AbnormalFlag.CRITICAL_HIGH)
        )

        # Alerts by severity
        alerts_by_severity: dict[str, int] = {}
        for a in alerts:
            key = a.severity.value
            alerts_by_severity[key] = alerts_by_severity.get(key, 0) + 1

        unacknowledged = sum(1 for a in alerts if not a.acknowledged)

        active_rules = sum(1 for r in rules if r.active)

        return LabDataMetrics(
            total_normal_ranges=len(ranges),
            ranges_by_category=ranges_by_category,
            total_alert_rules=len(rules),
            active_alert_rules=active_rules,
            total_specimens=len(specimens),
            specimens_by_status=specimens_by_status,
            total_results=total_results,
            results_by_status=results_by_status,
            results_by_flag=results_by_flag,
            abnormal_rate_pct=abnormal_rate,
            critical_results=critical_results,
            total_alerts=len(alerts),
            alerts_by_severity=alerts_by_severity,
            unacknowledged_alerts=unacknowledged,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: LabDataManagementService | None = None
_instance_lock = threading.Lock()


def get_lab_data_management_service() -> LabDataManagementService:
    """Return the singleton LabDataManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LabDataManagementService()
    return _instance


def reset_lab_data_management_service() -> LabDataManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = LabDataManagementService()
    return _instance
