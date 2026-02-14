"""CRF Management Service (CRF-MGT).

Manages case report form operations: CRF version control, field definitions,
edit check rules, CRF deployment tracking, CRF annotations, and CRF metrics.

Usage:
    from app.services.crf_management_service import (
        get_crf_management_service,
    )

    svc = get_crf_management_service()
    versions = svc.list_crf_versions()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.crf_management import (
    AnnotationType,
    CRFAnnotation,
    CRFAnnotationCreate,
    CRFAnnotationUpdate,
    CRFDeployment,
    CRFDeploymentCreate,
    CRFDeploymentUpdate,
    CRFField,
    CRFFieldCreate,
    CRFFieldUpdate,
    CRFManagementMetrics,
    CRFStatus,
    CRFVersion,
    CRFVersionCreate,
    CRFVersionUpdate,
    DeploymentStatus,
    EditCheckRule,
    EditCheckRuleCreate,
    EditCheckRuleUpdate,
    EditCheckSeverity,
    FieldType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class CRFManagementService:
    """In-memory CRF Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._crf_versions: dict[str, CRFVersion] = {}
        self._crf_fields: dict[str, CRFField] = {}
        self._edit_check_rules: dict[str, EditCheckRule] = {}
        self._crf_deployments: dict[str, CRFDeployment] = {}
        self._crf_annotations: dict[str, CRFAnnotation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic CRF management data."""
        now = datetime.now(timezone.utc)

        # --- 12 CRF Versions ---
        versions_data = [
            {
                "id": "CRF-001",
                "trial_id": EYLEA_TRIAL,
                "crf_name": "Demographics",
                "version_number": "1.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 15,
                "total_pages": 2,
                "authored_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wilson",
                "approved_by": "Dr. Emily Roberts",
                "effective_date": now - timedelta(days=120),
                "retirement_date": None,
                "change_summary": "Initial version of demographics CRF.",
                "notes": "Includes all ICH E6 required demographics fields.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CRF-002",
                "trial_id": EYLEA_TRIAL,
                "crf_name": "Vital Signs",
                "version_number": "2.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 12,
                "total_pages": 1,
                "authored_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wilson",
                "approved_by": "Dr. Emily Roberts",
                "effective_date": now - timedelta(days=90),
                "retirement_date": None,
                "change_summary": "Added orthostatic BP measurements.",
                "notes": "Version 2 supersedes v1 with additional vital sign parameters.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CRF-003",
                "trial_id": EYLEA_TRIAL,
                "crf_name": "Adverse Events",
                "version_number": "1.0",
                "crf_status": CRFStatus.APPROVED,
                "total_fields": 20,
                "total_pages": 3,
                "authored_by": "Dr. Michael Torres",
                "reviewed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. Emily Roberts",
                "effective_date": now - timedelta(days=60),
                "retirement_date": None,
                "change_summary": "Standard adverse event collection form.",
                "notes": "MedDRA coding integrated for AE term classification.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "CRF-004",
                "trial_id": EYLEA_TRIAL,
                "crf_name": "Concomitant Medications",
                "version_number": "1.1",
                "crf_status": CRFStatus.IN_REVIEW,
                "total_fields": 10,
                "total_pages": 1,
                "authored_by": "Dr. Sarah Chen",
                "reviewed_by": None,
                "approved_by": None,
                "effective_date": None,
                "retirement_date": None,
                "change_summary": "Added route of administration field.",
                "notes": "Pending clinical review for protocol alignment.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CRF-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Eligibility Criteria",
                "version_number": "1.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 25,
                "total_pages": 4,
                "authored_by": "Dr. Karen Liu",
                "reviewed_by": "Dr. Mark Phillips",
                "approved_by": "Dr. Angela Martinez",
                "effective_date": now - timedelta(days=110),
                "retirement_date": None,
                "change_summary": "Complete inclusion/exclusion criteria CRF.",
                "notes": "Covers all protocol-specified eligibility assessments.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "CRF-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Skin Assessment (EASI)",
                "version_number": "1.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 18,
                "total_pages": 3,
                "authored_by": "Dr. Karen Liu",
                "reviewed_by": "Dr. Mark Phillips",
                "approved_by": "Dr. Angela Martinez",
                "effective_date": now - timedelta(days=100),
                "retirement_date": None,
                "change_summary": "EASI scoring form for atopic dermatitis assessment.",
                "notes": "Validated EASI scoring algorithm with auto-calculation.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "CRF-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Laboratory Results",
                "version_number": "2.1",
                "crf_status": CRFStatus.APPROVED,
                "total_fields": 30,
                "total_pages": 4,
                "authored_by": "Dr. Rachel Green",
                "reviewed_by": "Dr. Karen Liu",
                "approved_by": "Dr. Angela Martinez",
                "effective_date": None,
                "retirement_date": None,
                "change_summary": "Added IgE and eosinophil biomarker fields.",
                "notes": "Aligned with central lab panel specifications.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CRF-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Patient Diary",
                "version_number": "1.0",
                "crf_status": CRFStatus.DRAFT,
                "total_fields": 8,
                "total_pages": 1,
                "authored_by": "Dr. Karen Liu",
                "reviewed_by": None,
                "approved_by": None,
                "effective_date": None,
                "retirement_date": None,
                "change_summary": "Daily symptom diary for itch and sleep quality.",
                "notes": "ePRO integration pending technical review.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CRF-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "Tumor Assessment",
                "version_number": "1.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 22,
                "total_pages": 3,
                "authored_by": "Dr. David Park",
                "reviewed_by": "Dr. Grace Lee",
                "approved_by": "Dr. Elena Voss",
                "effective_date": now - timedelta(days=95),
                "retirement_date": None,
                "change_summary": "RECIST 1.1 tumor measurement form.",
                "notes": "Supports target, non-target, and new lesion tracking.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "CRF-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "Immune-Related AE",
                "version_number": "1.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 16,
                "total_pages": 2,
                "authored_by": "Dr. David Park",
                "reviewed_by": "Dr. Grace Lee",
                "approved_by": "Dr. Elena Voss",
                "effective_date": now - timedelta(days=85),
                "retirement_date": None,
                "change_summary": "irAE-specific collection form for checkpoint inhibitors.",
                "notes": "Includes CTCAE grading and management actions.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "CRF-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "ECOG Performance Status",
                "version_number": "1.0",
                "crf_status": CRFStatus.RETIRED,
                "total_fields": 5,
                "total_pages": 1,
                "authored_by": "Dr. David Park",
                "reviewed_by": "Dr. Grace Lee",
                "approved_by": "Dr. Elena Voss",
                "effective_date": now - timedelta(days=130),
                "retirement_date": now - timedelta(days=40),
                "change_summary": "Original ECOG assessment form.",
                "notes": "Retired in favor of combined functional assessment CRF.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "CRF-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "Biomarker Collection",
                "version_number": "1.0",
                "crf_status": CRFStatus.SUPERSEDED,
                "total_fields": 14,
                "total_pages": 2,
                "authored_by": "Dr. Kevin Owens",
                "reviewed_by": "Dr. David Park",
                "approved_by": "Dr. Elena Voss",
                "effective_date": now - timedelta(days=120),
                "retirement_date": now - timedelta(days=50),
                "change_summary": "PD-L1 and TMB collection form.",
                "notes": "Superseded by v2.0 with expanded biomarker panel.",
                "created_at": now - timedelta(days=145),
            },
        ]

        for v in versions_data:
            self._crf_versions[v["id"]] = CRFVersion(**v)

        # --- 12 CRF Fields ---
        fields_data = [
            {
                "id": "FLD-001",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_name": "subject_initials",
                "field_label": "Subject Initials",
                "field_type": FieldType.TEXT,
                "page_number": 1,
                "display_order": 1,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "DM",
                "sdtm_variable": "RFICDTC",
                "codelist_name": None,
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Maximum 3 characters. Auto-masked for privacy.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "FLD-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_name": "date_of_birth",
                "field_label": "Date of Birth",
                "field_type": FieldType.DATE,
                "page_number": 1,
                "display_order": 2,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "DM",
                "sdtm_variable": "BRTHDTC",
                "codelist_name": None,
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Format: DD-MON-YYYY. Age calculated automatically.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "FLD-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_name": "sex",
                "field_label": "Sex",
                "field_type": FieldType.DROPDOWN,
                "page_number": 1,
                "display_order": 3,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "DM",
                "sdtm_variable": "SEX",
                "codelist_name": "SEX",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Values: Male, Female, Undifferentiated.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "FLD-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "field_name": "systolic_bp",
                "field_label": "Systolic Blood Pressure (mmHg)",
                "field_type": FieldType.NUMERIC,
                "page_number": 1,
                "display_order": 1,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "VS",
                "sdtm_variable": "VSSTRESN",
                "codelist_name": None,
                "min_value": 50.0,
                "max_value": 300.0,
                "default_value": None,
                "notes": "Range check: 50-300 mmHg. Hard edit if outside range.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "FLD-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "field_name": "informed_consent",
                "field_label": "Informed Consent Obtained",
                "field_type": FieldType.CHECKBOX,
                "page_number": 1,
                "display_order": 1,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "DS",
                "sdtm_variable": "DSSTDTC",
                "codelist_name": None,
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Must be checked before any study procedures.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "FLD-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "field_name": "age_eligible",
                "field_label": "Age >= 18 years",
                "field_type": FieldType.RADIO,
                "page_number": 1,
                "display_order": 2,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "IE",
                "sdtm_variable": "IETEST",
                "codelist_name": "NY",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Auto-calculated from date of birth if available.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "FLD-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "field_name": "easi_total_score",
                "field_label": "EASI Total Score",
                "field_type": FieldType.NUMERIC,
                "page_number": 3,
                "display_order": 18,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "QS",
                "sdtm_variable": "QSSTRESN",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 72.0,
                "default_value": None,
                "notes": "Auto-calculated from body region sub-scores.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "FLD-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-007",
                "field_name": "ige_level",
                "field_label": "Total IgE (IU/mL)",
                "field_type": FieldType.NUMERIC,
                "page_number": 2,
                "display_order": 10,
                "is_required": False,
                "is_key_field": False,
                "sdtm_domain": "LB",
                "sdtm_variable": "LBSTRESN",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 50000.0,
                "default_value": None,
                "notes": "Central lab result. Auto-populated from lab feed if available.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "FLD-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_name": "target_lesion_sum",
                "field_label": "Sum of Target Lesion Diameters (mm)",
                "field_type": FieldType.NUMERIC,
                "page_number": 2,
                "display_order": 8,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "TR",
                "sdtm_variable": "TRSTRESN",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 999.0,
                "default_value": None,
                "notes": "Auto-summed from individual target lesion measurements.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "FLD-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_name": "overall_response",
                "field_label": "Overall Response (RECIST 1.1)",
                "field_type": FieldType.DROPDOWN,
                "page_number": 3,
                "display_order": 15,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "RS",
                "sdtm_variable": "RSSTRESC",
                "codelist_name": "RSRESULT",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "CR, PR, SD, PD, NE per RECIST 1.1 criteria.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "FLD-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_name": "irae_grade",
                "field_label": "irAE CTCAE Grade",
                "field_type": FieldType.DROPDOWN,
                "page_number": 1,
                "display_order": 5,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "AE",
                "sdtm_variable": "AETOXGR",
                "codelist_name": "CTCAE_GRADE",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Grades 1-5 per CTCAE v5.0.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "FLD-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_name": "steroid_initiated",
                "field_label": "Systemic Steroids Initiated",
                "field_type": FieldType.CHECKBOX,
                "page_number": 2,
                "display_order": 10,
                "is_required": False,
                "is_key_field": False,
                "sdtm_domain": "CM",
                "sdtm_variable": "CMTRT",
                "codelist_name": None,
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Check if systemic corticosteroids were started for irAE management.",
                "created_at": now - timedelta(days=115),
            },
        ]

        for f in fields_data:
            self._crf_fields[f["id"]] = CRFField(**f)

        # --- 12 Edit Check Rules ---
        edit_checks_data = [
            {
                "id": "ECR-001",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "rule_name": "DOB_FUTURE_CHECK",
                "rule_expression": "date_of_birth <= current_date",
                "edit_check_severity": EditCheckSeverity.HARD_STOP,
                "target_field_id": "FLD-002",
                "error_message": "Date of birth cannot be in the future.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Sarah Chen",
                "notes": "Critical data quality check.",
                "created_at": now - timedelta(days=148),
            },
            {
                "id": "ECR-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "rule_name": "SBP_RANGE_CHECK",
                "rule_expression": "systolic_bp >= 50 AND systolic_bp <= 300",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-004",
                "error_message": "Systolic BP must be between 50 and 300 mmHg.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Sarah Chen",
                "notes": "Range validation for vital signs.",
                "created_at": now - timedelta(days=98),
            },
            {
                "id": "ECR-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "rule_name": "DBP_LT_SBP_CHECK",
                "rule_expression": "diastolic_bp < systolic_bp",
                "edit_check_severity": EditCheckSeverity.WARNING,
                "target_field_id": "FLD-004",
                "error_message": "Diastolic BP should be less than systolic BP.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. James Wilson",
                "notes": "Soft check - allows override with reason.",
                "created_at": now - timedelta(days=96),
            },
            {
                "id": "ECR-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-003",
                "rule_name": "AE_START_AFTER_CONSENT",
                "rule_expression": "ae_start_date >= informed_consent_date",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-001",
                "error_message": "AE start date cannot precede informed consent date.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": True,
                "reference_field_id": "FLD-005",
                "authored_by": "Dr. Michael Torres",
                "notes": "Cross-form edit check referencing consent date.",
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "ECR-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "rule_name": "CONSENT_REQUIRED",
                "rule_expression": "informed_consent == true",
                "edit_check_severity": EditCheckSeverity.HARD_STOP,
                "target_field_id": "FLD-005",
                "error_message": "Informed consent must be obtained before proceeding.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Karen Liu",
                "notes": "Regulatory requirement - cannot be overridden.",
                "created_at": now - timedelta(days=138),
            },
            {
                "id": "ECR-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "rule_name": "EASI_SCORE_RANGE",
                "rule_expression": "easi_total_score >= 0 AND easi_total_score <= 72",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-007",
                "error_message": "EASI total score must be between 0 and 72.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Karen Liu",
                "notes": "Validated scoring range for EASI instrument.",
                "created_at": now - timedelta(days=128),
            },
            {
                "id": "ECR-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-007",
                "rule_name": "IGE_POSITIVE_CHECK",
                "rule_expression": "ige_level >= 0",
                "edit_check_severity": EditCheckSeverity.INFORMATIONAL,
                "target_field_id": "FLD-008",
                "error_message": "IgE level should be a positive value.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Rachel Green",
                "notes": "Informational check for data review.",
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "ECR-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-007",
                "rule_name": "LAB_DATE_WITHIN_WINDOW",
                "rule_expression": "abs(lab_date - visit_date) <= 3",
                "edit_check_severity": EditCheckSeverity.SOFT_CHECK,
                "target_field_id": "FLD-008",
                "error_message": "Lab date is more than 3 days from the scheduled visit.",
                "is_active": False,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": True,
                "reference_field_id": "FLD-002",
                "authored_by": "Dr. Karen Liu",
                "notes": "Currently disabled pending protocol clarification.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "ECR-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "rule_name": "LESION_SUM_POSITIVE",
                "rule_expression": "target_lesion_sum > 0",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-009",
                "error_message": "Sum of target lesion diameters must be greater than 0.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. David Park",
                "notes": "At least one measurable target lesion required.",
                "created_at": now - timedelta(days=123),
            },
            {
                "id": "ECR-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "rule_name": "RESPONSE_CONSISTENCY",
                "rule_expression": "if overall_response == 'CR' then target_lesion_sum == 0",
                "edit_check_severity": EditCheckSeverity.WARNING,
                "target_field_id": "FLD-010",
                "error_message": "Complete response requires sum of diameters = 0.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": "FLD-009",
                "authored_by": "Dr. David Park",
                "notes": "Consistency check per RECIST 1.1 criteria.",
                "created_at": now - timedelta(days=121),
            },
            {
                "id": "ECR-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "rule_name": "IRAE_GRADE_REQUIRED",
                "rule_expression": "irae_grade IS NOT NULL",
                "edit_check_severity": EditCheckSeverity.HARD_STOP,
                "target_field_id": "FLD-011",
                "error_message": "irAE CTCAE grade is required for all immune-related events.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. David Park",
                "notes": "Mandatory grading for safety reporting.",
                "created_at": now - timedelta(days=113),
            },
            {
                "id": "ECR-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "rule_name": "STEROID_GRADE3_CHECK",
                "rule_expression": "if irae_grade >= 3 then steroid_initiated IS NOT NULL",
                "edit_check_severity": EditCheckSeverity.SOFT_CHECK,
                "target_field_id": "FLD-012",
                "error_message": "Please confirm steroid management for Grade 3+ irAE.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": "FLD-011",
                "authored_by": "Dr. Grace Lee",
                "notes": "Clinical reminder for irAE management documentation.",
                "created_at": now - timedelta(days=110),
            },
        ]

        for ec in edit_checks_data:
            self._edit_check_rules[ec["id"]] = EditCheckRule(**ec)

        # --- 12 CRF Deployments ---
        deployments_data = [
            {
                "id": "DEP-001",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "System Admin Tom Bradley",
                "deployment_date": now - timedelta(days=120),
                "scheduled_date": now - timedelta(days=121),
                "sites_affected": 15,
                "subjects_affected": 0,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Initial deployment of demographics CRF to all sites.",
                "created_at": now - timedelta(days=122),
            },
            {
                "id": "DEP-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "System Admin Tom Bradley",
                "deployment_date": now - timedelta(days=90),
                "scheduled_date": now - timedelta(days=90),
                "sites_affected": 15,
                "subjects_affected": 45,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Vital signs v2.0 deployed. Backward compatible.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "DEP-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-003",
                "deployment_status": DeploymentStatus.SCHEDULED,
                "target_environment": "Production",
                "deployed_by": "System Admin Tom Bradley",
                "deployment_date": None,
                "scheduled_date": now + timedelta(days=7),
                "sites_affected": 15,
                "subjects_affected": 60,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "AE CRF deployment scheduled for next maintenance window.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DEP-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "deployment_status": DeploymentStatus.ROLLED_BACK,
                "target_environment": "UAT",
                "deployed_by": "System Admin Tom Bradley",
                "deployment_date": now - timedelta(days=95),
                "scheduled_date": now - timedelta(days=95),
                "sites_affected": 3,
                "subjects_affected": 10,
                "rollback_available": False,
                "validation_passed": False,
                "notes": "UAT deployment rolled back due to edit check conflict.",
                "created_at": now - timedelta(days=97),
            },
            {
                "id": "DEP-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "System Admin Alex Yun",
                "deployment_date": now - timedelta(days=110),
                "scheduled_date": now - timedelta(days=111),
                "sites_affected": 20,
                "subjects_affected": 0,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Eligibility CRF deployed to all Dupixent sites.",
                "created_at": now - timedelta(days=112),
            },
            {
                "id": "DEP-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "System Admin Alex Yun",
                "deployment_date": now - timedelta(days=100),
                "scheduled_date": now - timedelta(days=100),
                "sites_affected": 20,
                "subjects_affected": 35,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "EASI scoring CRF deployed. Auto-calculation verified.",
                "created_at": now - timedelta(days=102),
            },
            {
                "id": "DEP-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-007",
                "deployment_status": DeploymentStatus.PENDING,
                "target_environment": "Production",
                "deployed_by": "System Admin Alex Yun",
                "deployment_date": None,
                "scheduled_date": now + timedelta(days=14),
                "sites_affected": 20,
                "subjects_affected": 80,
                "rollback_available": True,
                "validation_passed": False,
                "notes": "Pending final validation in UAT before production deployment.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DEP-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "deployment_status": DeploymentStatus.FAILED,
                "target_environment": "UAT",
                "deployed_by": "System Admin Alex Yun",
                "deployment_date": now - timedelta(days=105),
                "scheduled_date": now - timedelta(days=105),
                "sites_affected": 5,
                "subjects_affected": 0,
                "rollback_available": False,
                "validation_passed": False,
                "notes": "EASI auto-calculation logic failed UAT testing. Fixed in subsequent deployment.",
                "created_at": now - timedelta(days=107),
            },
            {
                "id": "DEP-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "System Admin Kevin Owens",
                "deployment_date": now - timedelta(days=95),
                "scheduled_date": now - timedelta(days=95),
                "sites_affected": 25,
                "subjects_affected": 0,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Tumor assessment CRF deployed to all oncology sites.",
                "created_at": now - timedelta(days=97),
            },
            {
                "id": "DEP-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "System Admin Kevin Owens",
                "deployment_date": now - timedelta(days=85),
                "scheduled_date": now - timedelta(days=86),
                "sites_affected": 25,
                "subjects_affected": 50,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "irAE CRF deployed. CTCAE grading integration confirmed.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "DEP-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-012",
                "deployment_status": DeploymentStatus.IN_PROGRESS,
                "target_environment": "UAT",
                "deployed_by": "System Admin Kevin Owens",
                "deployment_date": now - timedelta(days=1),
                "scheduled_date": now - timedelta(days=1),
                "sites_affected": 5,
                "subjects_affected": 0,
                "rollback_available": True,
                "validation_passed": False,
                "notes": "Biomarker CRF v2.0 UAT deployment in progress.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DEP-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-011",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "System Admin Kevin Owens",
                "deployment_date": now - timedelta(days=40),
                "scheduled_date": now - timedelta(days=40),
                "sites_affected": 25,
                "subjects_affected": 100,
                "rollback_available": False,
                "validation_passed": True,
                "notes": "ECOG CRF retired and replaced by combined functional assessment.",
                "created_at": now - timedelta(days=42),
            },
        ]

        for d in deployments_data:
            self._crf_deployments[d["id"]] = CRFDeployment(**d)

        # --- 12 CRF Annotations ---
        annotations_data = [
            {
                "id": "ANN-001",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_id": "FLD-001",
                "annotation_type": AnnotationType.SDTM_MAPPING,
                "annotation_text": "Maps to DM.RFICDTC - Date of First Informed Consent.",
                "sdtm_dataset": "DM",
                "sdtm_variable": "RFICDTC",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Data Standards Lead Sarah Kim",
                "reviewed": True,
                "reviewed_by": "SDTM Reviewer Dr. James Wilson",
                "notes": "Verified against CDISC SDTM IG v3.4.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "ANN-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_id": "FLD-002",
                "annotation_type": AnnotationType.SDTM_MAPPING,
                "annotation_text": "Maps to DM.BRTHDTC - Date/Time of Birth.",
                "sdtm_dataset": "DM",
                "sdtm_variable": "BRTHDTC",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Data Standards Lead Sarah Kim",
                "reviewed": True,
                "reviewed_by": "SDTM Reviewer Dr. James Wilson",
                "notes": "ISO 8601 format required for SDTM submission.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "ANN-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "field_id": "FLD-004",
                "annotation_type": AnnotationType.ADAM_MAPPING,
                "annotation_text": "Feeds into ADVS.AVAL for systolic blood pressure analysis.",
                "sdtm_dataset": "VS",
                "sdtm_variable": "VSSTRESN",
                "adam_dataset": "ADVS",
                "adam_variable": "AVAL",
                "coding_dictionary": None,
                "annotated_by": "Biostatistician Dr. Mark Phillips",
                "reviewed": True,
                "reviewed_by": "Stats Lead Dr. Elena Voss",
                "notes": "Used in primary efficacy analysis population.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "ANN-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-003",
                "field_id": None,
                "annotation_type": AnnotationType.COMPLETION_INSTRUCTION,
                "annotation_text": "Record all adverse events from informed consent through 30 days post last dose.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": "MedDRA",
                "annotated_by": "Clinical Data Manager Patricia Wells",
                "reviewed": False,
                "reviewed_by": None,
                "notes": "Instruction for site data entry staff.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "ANN-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "field_id": "FLD-005",
                "annotation_type": AnnotationType.REGULATORY_NOTE,
                "annotation_text": "ICH E6(R2) Section 4.8: Informed consent must be documented prior to any study-specific procedure.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Regulatory Affairs Lead Dr. Angela Martinez",
                "reviewed": True,
                "reviewed_by": "QA Manager Dr. Mark Phillips",
                "notes": "Regulatory compliance annotation.",
                "created_at": now - timedelta(days=135),
            },
            {
                "id": "ANN-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "field_id": "FLD-007",
                "annotation_type": AnnotationType.VALIDATION_RULE,
                "annotation_text": "EASI total score calculation formula for auto-calculation validation.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": "ADQS",
                "adam_variable": "AVAL",
                "coding_dictionary": None,
                "annotated_by": "Biostatistician Dr. Rachel Green",
                "reviewed": True,
                "reviewed_by": "Clinical Scientist Dr. Karen Liu",
                "notes": "EASI scoring algorithm for auto-calculation validation.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "ANN-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-007",
                "field_id": "FLD-008",
                "annotation_type": AnnotationType.CODING_DICTIONARY,
                "annotation_text": "IgE results coded using LOINC 19113-0 (IgE, Total).",
                "sdtm_dataset": "LB",
                "sdtm_variable": "LBTESTCD",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": "LOINC",
                "annotated_by": "Data Standards Lead Sarah Kim",
                "reviewed": False,
                "reviewed_by": None,
                "notes": "LOINC mapping for laboratory data standardization.",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "ANN-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "field_id": None,
                "annotation_type": AnnotationType.COMPLETION_INSTRUCTION,
                "annotation_text": "Assess all four body regions for EASI scoring.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Clinical Data Manager Patricia Wells",
                "reviewed": True,
                "reviewed_by": "Clinical Scientist Dr. Karen Liu",
                "notes": "Data entry guidance for EASI assessment.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "ANN-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_id": "FLD-009",
                "annotation_type": AnnotationType.SDTM_MAPPING,
                "annotation_text": "Maps to TR.TRSTRESN - Tumor Results, Standard Result in Numeric Format.",
                "sdtm_dataset": "TR",
                "sdtm_variable": "TRSTRESN",
                "adam_dataset": "ADTR",
                "adam_variable": "AVAL",
                "coding_dictionary": None,
                "annotated_by": "Data Standards Lead Sarah Kim",
                "reviewed": True,
                "reviewed_by": "SDTM Reviewer Dr. Grace Lee",
                "notes": "RECIST 1.1 measurement mapping verified.",
                "created_at": now - timedelta(days=118),
            },
            {
                "id": "ANN-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_id": "FLD-010",
                "annotation_type": AnnotationType.ADAM_MAPPING,
                "annotation_text": "Feeds into ADRS.AVALC for overall response categorization.",
                "sdtm_dataset": "RS",
                "sdtm_variable": "RSSTRESC",
                "adam_dataset": "ADRS",
                "adam_variable": "AVALC",
                "coding_dictionary": None,
                "annotated_by": "Biostatistician Dr. Mark Phillips",
                "reviewed": True,
                "reviewed_by": "Stats Lead Dr. Elena Voss",
                "notes": "Primary endpoint derivation source.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "ANN-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_id": "FLD-011",
                "annotation_type": AnnotationType.CODING_DICTIONARY,
                "annotation_text": "irAE grading per CTCAE v5.0. Use NCI CTCAE preferred terms.",
                "sdtm_dataset": "AE",
                "sdtm_variable": "AETOXGR",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": "CTCAE",
                "annotated_by": "Data Standards Lead Sarah Kim",
                "reviewed": True,
                "reviewed_by": "Medical Monitor Dr. David Park",
                "notes": "CTCAE v5.0 is the required grading system for this trial.",
                "created_at": now - timedelta(days=112),
            },
            {
                "id": "ANN-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_id": None,
                "annotation_type": AnnotationType.REGULATORY_NOTE,
                "annotation_text": "FDA Guidance: Immune-mediated adverse reactions must be captured with onset, duration, severity, and management details.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Regulatory Affairs Lead Dr. Angela Martinez",
                "reviewed": False,
                "reviewed_by": None,
                "notes": "FDA submission requirement for checkpoint inhibitor BLA.",
                "created_at": now - timedelta(days=108),
            },
        ]

        for a in annotations_data:
            self._crf_annotations[a["id"]] = CRFAnnotation(**a)

    # ------------------------------------------------------------------
    # CRF Versions
    # ------------------------------------------------------------------

    def list_crf_versions(
        self,
        *,
        trial_id: str | None = None,
        crf_status: CRFStatus | None = None,
    ) -> list[CRFVersion]:
        """List CRF versions with optional filters."""
        with self._lock:
            result = list(self._crf_versions.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if crf_status is not None:
            result = [v for v in result if v.crf_status == crf_status]

        return sorted(result, key=lambda v: v.created_at, reverse=True)

    def get_crf_version(self, version_id: str) -> CRFVersion | None:
        """Get a single CRF version by ID."""
        with self._lock:
            return self._crf_versions.get(version_id)

    def create_crf_version(self, payload: CRFVersionCreate) -> CRFVersion:
        """Create a new CRF version."""
        now = datetime.now(timezone.utc)
        version_id = f"CRF-{uuid4().hex[:8].upper()}"
        record = CRFVersion(
            id=version_id,
            trial_id=payload.trial_id,
            crf_name=payload.crf_name,
            version_number=payload.version_number,
            crf_status=CRFStatus.DRAFT,
            total_fields=0,
            total_pages=payload.total_pages,
            authored_by=payload.authored_by,
            reviewed_by=None,
            approved_by=None,
            effective_date=None,
            retirement_date=None,
            change_summary=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._crf_versions[version_id] = record
        logger.info("Created CRF version %s for trial %s", version_id, payload.trial_id)
        return record

    def update_crf_version(
        self, version_id: str, payload: CRFVersionUpdate
    ) -> CRFVersion | None:
        """Update an existing CRF version."""
        with self._lock:
            existing = self._crf_versions.get(version_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CRFVersion(**data)
            self._crf_versions[version_id] = updated
        return updated

    def delete_crf_version(self, version_id: str) -> bool:
        """Delete a CRF version. Returns True if deleted."""
        with self._lock:
            if version_id in self._crf_versions:
                del self._crf_versions[version_id]
                return True
            return False

    # ------------------------------------------------------------------
    # CRF Fields
    # ------------------------------------------------------------------

    def list_crf_fields(
        self,
        *,
        trial_id: str | None = None,
        crf_version_id: str | None = None,
        field_type: FieldType | None = None,
    ) -> list[CRFField]:
        """List CRF fields with optional filters."""
        with self._lock:
            result = list(self._crf_fields.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if crf_version_id is not None:
            result = [f for f in result if f.crf_version_id == crf_version_id]
        if field_type is not None:
            result = [f for f in result if f.field_type == field_type]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_crf_field(self, field_id: str) -> CRFField | None:
        """Get a single CRF field by ID."""
        with self._lock:
            return self._crf_fields.get(field_id)

    def create_crf_field(self, payload: CRFFieldCreate) -> CRFField:
        """Create a new CRF field."""
        now = datetime.now(timezone.utc)
        field_id = f"FLD-{uuid4().hex[:8].upper()}"
        record = CRFField(
            id=field_id,
            trial_id=payload.trial_id,
            crf_version_id=payload.crf_version_id,
            field_name=payload.field_name,
            field_label=payload.field_label,
            field_type=payload.field_type,
            page_number=payload.page_number,
            display_order=payload.display_order,
            is_required=payload.is_required,
            is_key_field=False,
            sdtm_domain=None,
            sdtm_variable=None,
            codelist_name=None,
            min_value=None,
            max_value=None,
            default_value=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._crf_fields[field_id] = record
        logger.info("Created CRF field %s for version %s", field_id, payload.crf_version_id)
        return record

    def update_crf_field(
        self, field_id: str, payload: CRFFieldUpdate
    ) -> CRFField | None:
        """Update an existing CRF field."""
        with self._lock:
            existing = self._crf_fields.get(field_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CRFField(**data)
            self._crf_fields[field_id] = updated
        return updated

    def delete_crf_field(self, field_id: str) -> bool:
        """Delete a CRF field. Returns True if deleted."""
        with self._lock:
            if field_id in self._crf_fields:
                del self._crf_fields[field_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Edit Check Rules
    # ------------------------------------------------------------------

    def list_edit_check_rules(
        self,
        *,
        trial_id: str | None = None,
        crf_version_id: str | None = None,
        edit_check_severity: EditCheckSeverity | None = None,
        is_active: bool | None = None,
    ) -> list[EditCheckRule]:
        """List edit check rules with optional filters."""
        with self._lock:
            result = list(self._edit_check_rules.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if crf_version_id is not None:
            result = [r for r in result if r.crf_version_id == crf_version_id]
        if edit_check_severity is not None:
            result = [r for r in result if r.edit_check_severity == edit_check_severity]
        if is_active is not None:
            result = [r for r in result if r.is_active == is_active]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_edit_check_rule(self, rule_id: str) -> EditCheckRule | None:
        """Get a single edit check rule by ID."""
        with self._lock:
            return self._edit_check_rules.get(rule_id)

    def create_edit_check_rule(self, payload: EditCheckRuleCreate) -> EditCheckRule:
        """Create a new edit check rule."""
        now = datetime.now(timezone.utc)
        rule_id = f"ECR-{uuid4().hex[:8].upper()}"
        record = EditCheckRule(
            id=rule_id,
            trial_id=payload.trial_id,
            crf_version_id=payload.crf_version_id,
            rule_name=payload.rule_name,
            rule_expression=payload.rule_expression,
            edit_check_severity=payload.edit_check_severity,
            target_field_id=payload.target_field_id,
            error_message=payload.error_message,
            is_active=True,
            fire_on_save=True,
            fire_on_submit=True,
            cross_form_check=False,
            reference_field_id=None,
            authored_by=payload.authored_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._edit_check_rules[rule_id] = record
        logger.info("Created edit check rule %s for version %s", rule_id, payload.crf_version_id)
        return record

    def update_edit_check_rule(
        self, rule_id: str, payload: EditCheckRuleUpdate
    ) -> EditCheckRule | None:
        """Update an existing edit check rule."""
        with self._lock:
            existing = self._edit_check_rules.get(rule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EditCheckRule(**data)
            self._edit_check_rules[rule_id] = updated
        return updated

    def delete_edit_check_rule(self, rule_id: str) -> bool:
        """Delete an edit check rule. Returns True if deleted."""
        with self._lock:
            if rule_id in self._edit_check_rules:
                del self._edit_check_rules[rule_id]
                return True
            return False

    # ------------------------------------------------------------------
    # CRF Deployments
    # ------------------------------------------------------------------

    def list_crf_deployments(
        self,
        *,
        trial_id: str | None = None,
        deployment_status: DeploymentStatus | None = None,
        crf_version_id: str | None = None,
    ) -> list[CRFDeployment]:
        """List CRF deployments with optional filters."""
        with self._lock:
            result = list(self._crf_deployments.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if deployment_status is not None:
            result = [d for d in result if d.deployment_status == deployment_status]
        if crf_version_id is not None:
            result = [d for d in result if d.crf_version_id == crf_version_id]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_crf_deployment(self, deployment_id: str) -> CRFDeployment | None:
        """Get a single CRF deployment by ID."""
        with self._lock:
            return self._crf_deployments.get(deployment_id)

    def create_crf_deployment(self, payload: CRFDeploymentCreate) -> CRFDeployment:
        """Create a new CRF deployment."""
        now = datetime.now(timezone.utc)
        deployment_id = f"DEP-{uuid4().hex[:8].upper()}"
        record = CRFDeployment(
            id=deployment_id,
            trial_id=payload.trial_id,
            crf_version_id=payload.crf_version_id,
            deployment_status=DeploymentStatus.PENDING,
            target_environment=payload.target_environment,
            deployed_by=payload.deployed_by,
            deployment_date=None,
            scheduled_date=None,
            sites_affected=payload.sites_affected,
            subjects_affected=0,
            rollback_available=True,
            validation_passed=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._crf_deployments[deployment_id] = record
        logger.info("Created CRF deployment %s for version %s", deployment_id, payload.crf_version_id)
        return record

    def update_crf_deployment(
        self, deployment_id: str, payload: CRFDeploymentUpdate
    ) -> CRFDeployment | None:
        """Update an existing CRF deployment."""
        with self._lock:
            existing = self._crf_deployments.get(deployment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CRFDeployment(**data)
            self._crf_deployments[deployment_id] = updated
        return updated

    def delete_crf_deployment(self, deployment_id: str) -> bool:
        """Delete a CRF deployment. Returns True if deleted."""
        with self._lock:
            if deployment_id in self._crf_deployments:
                del self._crf_deployments[deployment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # CRF Annotations
    # ------------------------------------------------------------------

    def list_crf_annotations(
        self,
        *,
        trial_id: str | None = None,
        crf_version_id: str | None = None,
        annotation_type: AnnotationType | None = None,
    ) -> list[CRFAnnotation]:
        """List CRF annotations with optional filters."""
        with self._lock:
            result = list(self._crf_annotations.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if crf_version_id is not None:
            result = [a for a in result if a.crf_version_id == crf_version_id]
        if annotation_type is not None:
            result = [a for a in result if a.annotation_type == annotation_type]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_crf_annotation(self, annotation_id: str) -> CRFAnnotation | None:
        """Get a single CRF annotation by ID."""
        with self._lock:
            return self._crf_annotations.get(annotation_id)

    def create_crf_annotation(self, payload: CRFAnnotationCreate) -> CRFAnnotation:
        """Create a new CRF annotation."""
        now = datetime.now(timezone.utc)
        annotation_id = f"ANN-{uuid4().hex[:8].upper()}"
        record = CRFAnnotation(
            id=annotation_id,
            trial_id=payload.trial_id,
            crf_version_id=payload.crf_version_id,
            field_id=payload.field_id,
            annotation_type=payload.annotation_type,
            annotation_text=payload.annotation_text,
            sdtm_dataset=None,
            sdtm_variable=None,
            adam_dataset=None,
            adam_variable=None,
            coding_dictionary=None,
            annotated_by=payload.annotated_by,
            reviewed=False,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._crf_annotations[annotation_id] = record
        logger.info("Created CRF annotation %s for version %s", annotation_id, payload.crf_version_id)
        return record

    def update_crf_annotation(
        self, annotation_id: str, payload: CRFAnnotationUpdate
    ) -> CRFAnnotation | None:
        """Update an existing CRF annotation."""
        with self._lock:
            existing = self._crf_annotations.get(annotation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CRFAnnotation(**data)
            self._crf_annotations[annotation_id] = updated
        return updated

    def delete_crf_annotation(self, annotation_id: str) -> bool:
        """Delete a CRF annotation. Returns True if deleted."""
        with self._lock:
            if annotation_id in self._crf_annotations:
                del self._crf_annotations[annotation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> CRFManagementMetrics:
        """Compute aggregated CRF management metrics."""
        with self._lock:
            versions = list(self._crf_versions.values())
            fields = list(self._crf_fields.values())
            edit_checks = list(self._edit_check_rules.values())
            deployments = list(self._crf_deployments.values())
            annotations = list(self._crf_annotations.values())

        # Filter by trial if specified
        if trial_id is not None:
            versions = [v for v in versions if v.trial_id == trial_id]
            fields = [f for f in fields if f.trial_id == trial_id]
            edit_checks = [e for e in edit_checks if e.trial_id == trial_id]
            deployments = [d for d in deployments if d.trial_id == trial_id]
            annotations = [a for a in annotations if a.trial_id == trial_id]

        # Versions by status
        versions_by_status: dict[str, int] = {}
        for v in versions:
            key = v.crf_status.value
            versions_by_status[key] = versions_by_status.get(key, 0) + 1

        # Fields by type
        fields_by_type: dict[str, int] = {}
        for f in fields:
            key = f.field_type.value
            fields_by_type[key] = fields_by_type.get(key, 0) + 1

        # Required field percentage
        required_count = sum(1 for f in fields if f.is_required)
        required_field_pct = round(
            (required_count / max(1, len(fields))) * 100, 1
        )

        # Edit checks by severity
        edit_checks_by_severity: dict[str, int] = {}
        for e in edit_checks:
            key = e.edit_check_severity.value
            edit_checks_by_severity[key] = edit_checks_by_severity.get(key, 0) + 1

        # Active edit check percentage
        active_count = sum(1 for e in edit_checks if e.is_active)
        active_edit_check_pct = round(
            (active_count / max(1, len(edit_checks))) * 100, 1
        )

        # Deployments by status
        deployments_by_status: dict[str, int] = {}
        for d in deployments:
            key = d.deployment_status.value
            deployments_by_status[key] = deployments_by_status.get(key, 0) + 1

        # Annotations by type
        annotations_by_type: dict[str, int] = {}
        for a in annotations:
            key = a.annotation_type.value
            annotations_by_type[key] = annotations_by_type.get(key, 0) + 1

        # Annotation review rate
        reviewed_count = sum(1 for a in annotations if a.reviewed)
        annotation_review_rate = round(
            (reviewed_count / max(1, len(annotations))) * 100, 1
        )

        return CRFManagementMetrics(
            total_crf_versions=len(versions),
            versions_by_status=versions_by_status,
            total_fields=len(fields),
            fields_by_type=fields_by_type,
            required_field_pct=required_field_pct,
            total_edit_checks=len(edit_checks),
            edit_checks_by_severity=edit_checks_by_severity,
            active_edit_check_pct=active_edit_check_pct,
            total_deployments=len(deployments),
            deployments_by_status=deployments_by_status,
            total_annotations=len(annotations),
            annotations_by_type=annotations_by_type,
            annotation_review_rate=annotation_review_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CRFManagementService | None = None
_instance_lock = threading.Lock()


def get_crf_management_service() -> CRFManagementService:
    """Return the singleton CRFManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CRFManagementService()
    return _instance


def reset_crf_management_service() -> CRFManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CRFManagementService()
    return _instance
