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
        self._deployments: dict[str, CRFDeployment] = {}
        self._annotations: dict[str, CRFAnnotation] = {}
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
                "total_fields": 18,
                "total_pages": 2,
                "authored_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wilson",
                "approved_by": "Dr. Maria Lopez",
                "effective_date": now - timedelta(days=120),
                "retirement_date": None,
                "change_summary": "Initial version of demographics CRF.",
                "notes": "Standard demographics form per FDA guidance.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CRF-002",
                "trial_id": EYLEA_TRIAL,
                "crf_name": "Adverse Events",
                "version_number": "2.1",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 24,
                "total_pages": 3,
                "authored_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wilson",
                "approved_by": "Dr. Maria Lopez",
                "effective_date": now - timedelta(days=90),
                "retirement_date": None,
                "change_summary": "Added severity grading per CTCAE v5.0.",
                "notes": "Aligned with MedDRA coding requirements.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CRF-003",
                "trial_id": EYLEA_TRIAL,
                "crf_name": "Vital Signs",
                "version_number": "1.2",
                "crf_status": CRFStatus.APPROVED,
                "total_fields": 12,
                "total_pages": 1,
                "authored_by": "Dr. Kevin Park",
                "reviewed_by": "Dr. James Wilson",
                "approved_by": "Dr. Maria Lopez",
                "effective_date": now - timedelta(days=30),
                "retirement_date": None,
                "change_summary": "Added orthostatic blood pressure fields.",
                "notes": "Pending deployment to production.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "CRF-004",
                "trial_id": EYLEA_TRIAL,
                "crf_name": "Concomitant Medications",
                "version_number": "1.0",
                "crf_status": CRFStatus.IN_REVIEW,
                "total_fields": 15,
                "total_pages": 2,
                "authored_by": "Dr. Kevin Park",
                "reviewed_by": None,
                "approved_by": None,
                "effective_date": None,
                "retirement_date": None,
                "change_summary": "Initial draft for concomitant medication logging.",
                "notes": "Awaiting clinical review.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CRF-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Dermatology Assessment",
                "version_number": "3.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 30,
                "total_pages": 4,
                "authored_by": "Dr. Emily Watson",
                "reviewed_by": "Dr. Robert Kim",
                "approved_by": "Dr. Lisa Chang",
                "effective_date": now - timedelta(days=80),
                "retirement_date": None,
                "change_summary": "Major revision with EASI scoring integration.",
                "notes": "Includes photographic documentation fields.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "CRF-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Patient Reported Outcomes",
                "version_number": "1.1",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 20,
                "total_pages": 3,
                "authored_by": "Dr. Emily Watson",
                "reviewed_by": "Dr. Robert Kim",
                "approved_by": "Dr. Lisa Chang",
                "effective_date": now - timedelta(days=75),
                "retirement_date": None,
                "change_summary": "Added DLQI and NRS pruritus scales.",
                "notes": "Validated PRO instruments included.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "CRF-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Lab Results",
                "version_number": "2.0",
                "crf_status": CRFStatus.SUPERSEDED,
                "total_fields": 22,
                "total_pages": 2,
                "authored_by": "Dr. Emily Watson",
                "reviewed_by": "Dr. Robert Kim",
                "approved_by": "Dr. Lisa Chang",
                "effective_date": now - timedelta(days=200),
                "retirement_date": now - timedelta(days=80),
                "change_summary": "Replaced by v3.0 with expanded biomarker panel.",
                "notes": "Historical version. Do not use for new data entry.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "CRF-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_name": "Eligibility Criteria",
                "version_number": "1.0",
                "crf_status": CRFStatus.DRAFT,
                "total_fields": 16,
                "total_pages": 2,
                "authored_by": "Dr. Michael Torres",
                "reviewed_by": None,
                "approved_by": None,
                "effective_date": None,
                "retirement_date": None,
                "change_summary": "Draft eligibility CRF for protocol amendment.",
                "notes": "Needs alignment with amended inclusion/exclusion criteria.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CRF-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "Tumor Assessment",
                "version_number": "2.0",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 28,
                "total_pages": 4,
                "authored_by": "Dr. Angela Martinez",
                "reviewed_by": "Dr. David Park",
                "approved_by": "Dr. Grace Lee",
                "effective_date": now - timedelta(days=70),
                "retirement_date": None,
                "change_summary": "RECIST 1.1 compliant with iRECIST extension.",
                "notes": "Includes target and non-target lesion tracking.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CRF-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "Immune-Related AE",
                "version_number": "1.3",
                "crf_status": CRFStatus.DEPLOYED,
                "total_fields": 20,
                "total_pages": 3,
                "authored_by": "Dr. Angela Martinez",
                "reviewed_by": "Dr. David Park",
                "approved_by": "Dr. Grace Lee",
                "effective_date": now - timedelta(days=60),
                "retirement_date": None,
                "change_summary": "Added irAE management algorithm fields.",
                "notes": "Specific to checkpoint inhibitor safety monitoring.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "CRF-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "Pharmacokinetics",
                "version_number": "1.0",
                "crf_status": CRFStatus.RETIRED,
                "total_fields": 10,
                "total_pages": 1,
                "authored_by": "Dr. Angela Martinez",
                "reviewed_by": "Dr. David Park",
                "approved_by": "Dr. Grace Lee",
                "effective_date": now - timedelta(days=300),
                "retirement_date": now - timedelta(days=60),
                "change_summary": "Original PK CRF, now retired.",
                "notes": "Replaced by updated PK CRF v2.0 with sparse sampling.",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "CRF-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_name": "End of Treatment",
                "version_number": "1.0",
                "crf_status": CRFStatus.IN_REVIEW,
                "total_fields": 14,
                "total_pages": 2,
                "authored_by": "Dr. Kevin Owens",
                "reviewed_by": None,
                "approved_by": None,
                "effective_date": None,
                "retirement_date": None,
                "change_summary": "Initial draft for end-of-treatment visit.",
                "notes": "Includes reason for discontinuation and final assessments.",
                "created_at": now - timedelta(days=20),
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
                "field_name": "SUBJID",
                "field_label": "Subject Identifier",
                "field_type": FieldType.TEXT,
                "page_number": 1,
                "display_order": 1,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "DM",
                "sdtm_variable": "SUBJID",
                "codelist_name": None,
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "Unique subject identifier per protocol.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "FLD-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_name": "BRTHDTC",
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
                "notes": "ISO 8601 date format.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "FLD-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_name": "SEX",
                "field_label": "Sex",
                "field_type": FieldType.DROPDOWN,
                "page_number": 1,
                "display_order": 3,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "DM",
                "sdtm_variable": "SEX",
                "codelist_name": "CL.SEX",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "CDISC controlled terminology for sex.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "FLD-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "field_name": "AESEV",
                "field_label": "Adverse Event Severity",
                "field_type": FieldType.RADIO,
                "page_number": 1,
                "display_order": 5,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "AE",
                "sdtm_variable": "AESEV",
                "codelist_name": "CL.AESEV",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "CTCAE v5.0 severity grading.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "FLD-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "field_name": "EASI_SCORE",
                "field_label": "EASI Total Score",
                "field_type": FieldType.NUMERIC,
                "page_number": 2,
                "display_order": 1,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "QS",
                "sdtm_variable": "QSSTRESN",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 72.0,
                "default_value": None,
                "notes": "EASI score range 0-72.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "FLD-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "field_name": "BSA_PCT",
                "field_label": "Body Surface Area Affected (%)",
                "field_type": FieldType.NUMERIC,
                "page_number": 2,
                "display_order": 2,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "QS",
                "sdtm_variable": "QSSTRESN",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 100.0,
                "default_value": None,
                "notes": "Percentage of body surface area affected.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "FLD-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "field_name": "NRS_PRURITUS",
                "field_label": "Pruritus NRS Score",
                "field_type": FieldType.NUMERIC,
                "page_number": 1,
                "display_order": 1,
                "is_required": False,
                "is_key_field": False,
                "sdtm_domain": "QS",
                "sdtm_variable": "QSSTRESN",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 10.0,
                "default_value": None,
                "notes": "Numerical rating scale 0-10 for pruritus.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "FLD-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "field_name": "DLQI_TOTAL",
                "field_label": "DLQI Total Score",
                "field_type": FieldType.NUMERIC,
                "page_number": 1,
                "display_order": 2,
                "is_required": False,
                "is_key_field": False,
                "sdtm_domain": "QS",
                "sdtm_variable": "QSSTRESN",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 30.0,
                "default_value": None,
                "notes": "Dermatology Life Quality Index, range 0-30.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "FLD-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_name": "TARGET_LESION_SLD",
                "field_label": "Sum of Longest Diameters (mm)",
                "field_type": FieldType.NUMERIC,
                "page_number": 1,
                "display_order": 1,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "TU",
                "sdtm_variable": "TUSTRESC",
                "codelist_name": None,
                "min_value": 0.0,
                "max_value": 999.0,
                "default_value": None,
                "notes": "RECIST 1.1 sum of longest diameters.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "FLD-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_name": "OVERALL_RESPONSE",
                "field_label": "Overall Tumor Response",
                "field_type": FieldType.DROPDOWN,
                "page_number": 3,
                "display_order": 1,
                "is_required": True,
                "is_key_field": True,
                "sdtm_domain": "RS",
                "sdtm_variable": "RSSTRESC",
                "codelist_name": "CL.RECIST_RESPONSE",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "CR, PR, SD, PD per RECIST 1.1.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "FLD-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_name": "IRAE_GRADE",
                "field_label": "irAE Grade",
                "field_type": FieldType.RADIO,
                "page_number": 1,
                "display_order": 3,
                "is_required": True,
                "is_key_field": False,
                "sdtm_domain": "AE",
                "sdtm_variable": "AETOXGR",
                "codelist_name": "CL.CTCAE_GRADE",
                "min_value": None,
                "max_value": None,
                "default_value": None,
                "notes": "CTCAE grading for immune-related adverse events.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "FLD-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_name": "STEROID_USE",
                "field_label": "Systemic Steroid Use",
                "field_type": FieldType.CHECKBOX,
                "page_number": 2,
                "display_order": 1,
                "is_required": False,
                "is_key_field": False,
                "sdtm_domain": "CM",
                "sdtm_variable": "CMTRT",
                "codelist_name": None,
                "min_value": None,
                "max_value": None,
                "default_value": "false",
                "notes": "Indicates systemic corticosteroid use for irAE management.",
                "created_at": now - timedelta(days=85),
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
                "rule_name": "DM_SUBJID_REQUIRED",
                "rule_expression": "SUBJID IS NOT NULL AND SUBJID != ''",
                "edit_check_severity": EditCheckSeverity.HARD_STOP,
                "target_field_id": "FLD-001",
                "error_message": "Subject Identifier is required.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Sarah Chen",
                "notes": "Critical field - cannot be blank.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "ECR-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "rule_name": "DM_BRTHDTC_RANGE",
                "rule_expression": "BRTHDTC <= TODAY() AND AGE(BRTHDTC) >= 18",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-002",
                "error_message": "Date of birth must be in the past and subject must be >= 18 years.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Sarah Chen",
                "notes": "Age verification per protocol eligibility.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "ECR-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "rule_name": "AE_SEVERITY_REQUIRED",
                "rule_expression": "AESEV IN ('MILD', 'MODERATE', 'SEVERE')",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-004",
                "error_message": "Adverse event severity must be specified.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Sarah Chen",
                "notes": "Mandatory for regulatory reporting.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "ECR-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "rule_name": "AE_ONSET_BEFORE_RESOLUTION",
                "rule_expression": "AESTDTC <= AEENDTC OR AEENDTC IS NULL",
                "edit_check_severity": EditCheckSeverity.WARNING,
                "target_field_id": "FLD-004",
                "error_message": "AE onset date should not be after resolution date.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Kevin Park",
                "notes": "Temporal consistency check.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "ECR-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "rule_name": "EASI_SCORE_RANGE",
                "rule_expression": "EASI_SCORE >= 0 AND EASI_SCORE <= 72",
                "edit_check_severity": EditCheckSeverity.HARD_STOP,
                "target_field_id": "FLD-005",
                "error_message": "EASI score must be between 0 and 72.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Emily Watson",
                "notes": "Valid EASI score range per instrument specification.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "ECR-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "rule_name": "BSA_PCT_RANGE",
                "rule_expression": "BSA_PCT >= 0 AND BSA_PCT <= 100",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-006",
                "error_message": "Body surface area percentage must be 0-100.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Emily Watson",
                "notes": "Logical range check.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "ECR-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "rule_name": "NRS_PRURITUS_RANGE",
                "rule_expression": "NRS_PRURITUS >= 0 AND NRS_PRURITUS <= 10",
                "edit_check_severity": EditCheckSeverity.SOFT_CHECK,
                "target_field_id": "FLD-007",
                "error_message": "Pruritus NRS score should be between 0 and 10.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Emily Watson",
                "notes": "NRS instrument valid range.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "ECR-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "rule_name": "DLQI_SCORE_RANGE",
                "rule_expression": "DLQI_TOTAL >= 0 AND DLQI_TOTAL <= 30",
                "edit_check_severity": EditCheckSeverity.INFORMATIONAL,
                "target_field_id": "FLD-008",
                "error_message": "DLQI score outside expected range 0-30.",
                "is_active": False,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Michael Torres",
                "notes": "Informational only, currently disabled for testing.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "ECR-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "rule_name": "SLD_POSITIVE",
                "rule_expression": "TARGET_LESION_SLD > 0",
                "edit_check_severity": EditCheckSeverity.ERROR,
                "target_field_id": "FLD-009",
                "error_message": "Sum of longest diameters must be positive.",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Angela Martinez",
                "notes": "RECIST 1.1 requirement.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "ECR-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "rule_name": "RESPONSE_CONSISTENCY",
                "rule_expression": "RESPONSE_VS_BASELINE(TARGET_LESION_SLD, OVERALL_RESPONSE)",
                "edit_check_severity": EditCheckSeverity.WARNING,
                "target_field_id": "FLD-010",
                "error_message": "Overall response does not match calculated change from baseline.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": True,
                "reference_field_id": "FLD-009",
                "authored_by": "Dr. Angela Martinez",
                "notes": "Cross-field validation for RECIST response consistency.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "ECR-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "rule_name": "IRAE_GRADE_REQUIRED",
                "rule_expression": "IRAE_GRADE IN ('1', '2', '3', '4', '5')",
                "edit_check_severity": EditCheckSeverity.HARD_STOP,
                "target_field_id": "FLD-011",
                "error_message": "irAE grade must be specified (1-5).",
                "is_active": True,
                "fire_on_save": True,
                "fire_on_submit": True,
                "cross_form_check": False,
                "reference_field_id": None,
                "authored_by": "Dr. Angela Martinez",
                "notes": "Critical for safety monitoring in immunotherapy trials.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "ECR-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "rule_name": "STEROID_IF_GRADE_3_PLUS",
                "rule_expression": "IF IRAE_GRADE >= 3 THEN STEROID_USE = TRUE",
                "edit_check_severity": EditCheckSeverity.SOFT_CHECK,
                "target_field_id": "FLD-012",
                "error_message": "Grade 3+ irAE typically requires systemic steroid use. Please confirm.",
                "is_active": True,
                "fire_on_save": False,
                "fire_on_submit": True,
                "cross_form_check": True,
                "reference_field_id": "FLD-011",
                "authored_by": "Dr. David Park",
                "notes": "Clinical consistency check per management guidelines.",
                "created_at": now - timedelta(days=85),
            },
        ]

        for e in edit_checks_data:
            self._edit_check_rules[e["id"]] = EditCheckRule(**e)

        # --- 12 CRF Deployments ---
        deployments_data = [
            {
                "id": "DEP-001",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "EDC Admin Team",
                "deployment_date": now - timedelta(days=120),
                "scheduled_date": now - timedelta(days=121),
                "sites_affected": 15,
                "subjects_affected": 120,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Smooth deployment to all EYLEA sites.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "DEP-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "EDC Admin Team",
                "deployment_date": now - timedelta(days=90),
                "scheduled_date": now - timedelta(days=91),
                "sites_affected": 15,
                "subjects_affected": 145,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "AE CRF v2.1 deployed successfully.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "DEP-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-003",
                "deployment_status": DeploymentStatus.SCHEDULED,
                "target_environment": "Production",
                "deployed_by": "EDC Admin Team",
                "deployment_date": None,
                "scheduled_date": now + timedelta(days=7),
                "sites_affected": 15,
                "subjects_affected": 0,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Scheduled for next maintenance window.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DEP-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-003",
                "deployment_status": DeploymentStatus.FAILED,
                "target_environment": "UAT",
                "deployed_by": "EDC Admin Team",
                "deployment_date": now - timedelta(days=15),
                "scheduled_date": now - timedelta(days=15),
                "sites_affected": 0,
                "subjects_affected": 0,
                "rollback_available": False,
                "validation_passed": False,
                "notes": "UAT deployment failed due to edit check conflict. Resolved.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "DEP-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "Clinical Data Systems",
                "deployment_date": now - timedelta(days=80),
                "scheduled_date": now - timedelta(days=81),
                "sites_affected": 22,
                "subjects_affected": 200,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Dermatology CRF v3.0 deployed to all sites.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DEP-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "Clinical Data Systems",
                "deployment_date": now - timedelta(days=75),
                "scheduled_date": now - timedelta(days=75),
                "sites_affected": 22,
                "subjects_affected": 195,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "PRO CRF v1.1 deployed with ePRO integration.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DEP-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-008",
                "deployment_status": DeploymentStatus.PENDING,
                "target_environment": "UAT",
                "deployed_by": "Clinical Data Systems",
                "deployment_date": None,
                "scheduled_date": now + timedelta(days=14),
                "sites_affected": 0,
                "subjects_affected": 0,
                "rollback_available": True,
                "validation_passed": False,
                "notes": "Pending UAT testing for eligibility CRF.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DEP-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-007",
                "deployment_status": DeploymentStatus.ROLLED_BACK,
                "target_environment": "Production",
                "deployed_by": "Clinical Data Systems",
                "deployment_date": now - timedelta(days=85),
                "scheduled_date": now - timedelta(days=85),
                "sites_affected": 22,
                "subjects_affected": 180,
                "rollback_available": False,
                "validation_passed": True,
                "notes": "Rolled back due to data migration issues. Superseded by v3.0.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DEP-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "Oncology Data Team",
                "deployment_date": now - timedelta(days=70),
                "scheduled_date": now - timedelta(days=71),
                "sites_affected": 18,
                "subjects_affected": 90,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "Tumor assessment CRF v2.0 deployed to all oncology sites.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DEP-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "deployment_status": DeploymentStatus.COMPLETED,
                "target_environment": "Production",
                "deployed_by": "Oncology Data Team",
                "deployment_date": now - timedelta(days=60),
                "scheduled_date": now - timedelta(days=60),
                "sites_affected": 18,
                "subjects_affected": 88,
                "rollback_available": True,
                "validation_passed": True,
                "notes": "irAE CRF v1.3 deployed with safety alert integration.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "DEP-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-012",
                "deployment_status": DeploymentStatus.IN_PROGRESS,
                "target_environment": "UAT",
                "deployed_by": "Oncology Data Team",
                "deployment_date": now,
                "scheduled_date": now,
                "sites_affected": 3,
                "subjects_affected": 0,
                "rollback_available": True,
                "validation_passed": False,
                "notes": "UAT deployment in progress for EoT CRF.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DEP-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-011",
                "deployment_status": DeploymentStatus.ROLLED_BACK,
                "target_environment": "Production",
                "deployed_by": "Oncology Data Team",
                "deployment_date": now - timedelta(days=65),
                "scheduled_date": now - timedelta(days=65),
                "sites_affected": 18,
                "subjects_affected": 85,
                "rollback_available": False,
                "validation_passed": True,
                "notes": "PK CRF v1.0 rolled back. Replaced by v2.0.",
                "created_at": now - timedelta(days=70),
            },
        ]

        for d in deployments_data:
            self._deployments[d["id"]] = CRFDeployment(**d)

        # --- 12 CRF Annotations ---
        annotations_data = [
            {
                "id": "ANN-001",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_id": "FLD-001",
                "annotation_type": AnnotationType.SDTM_MAPPING,
                "annotation_text": "Maps to DM.SUBJID. Direct mapping, no transformation required.",
                "sdtm_dataset": "DM",
                "sdtm_variable": "SUBJID",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "SDTM Programmer Sarah Chen",
                "reviewed": True,
                "reviewed_by": "Lead SDTM Programmer Dr. James Wilson",
                "notes": "Standard CDASH to SDTM mapping.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "ANN-002",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-001",
                "field_id": "FLD-003",
                "annotation_type": AnnotationType.CODING_DICTIONARY,
                "annotation_text": "Sex field uses CDISC CT codelist C66731.",
                "sdtm_dataset": "DM",
                "sdtm_variable": "SEX",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": "CDISC CT C66731",
                "annotated_by": "SDTM Programmer Sarah Chen",
                "reviewed": True,
                "reviewed_by": "Lead SDTM Programmer Dr. James Wilson",
                "notes": "M=Male, F=Female, U=Unknown.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "ANN-003",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "field_id": "FLD-004",
                "annotation_type": AnnotationType.COMPLETION_INSTRUCTION,
                "annotation_text": "Select severity based on CTCAE v5.0 grading criteria. Refer to investigator guide appendix B.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Clinical Lead Dr. Kevin Park",
                "reviewed": True,
                "reviewed_by": "Medical Monitor Dr. Maria Lopez",
                "notes": "Updated to CTCAE v5.0 from v4.03.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "ANN-004",
                "trial_id": EYLEA_TRIAL,
                "crf_version_id": "CRF-002",
                "field_id": None,
                "annotation_type": AnnotationType.REGULATORY_NOTE,
                "annotation_text": "AE CRF aligned with ICH E2B(R3) requirements for expedited safety reporting.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Regulatory Affairs Team",
                "reviewed": True,
                "reviewed_by": "VP Regulatory Dr. Maria Lopez",
                "notes": "Compliance with global safety reporting standards.",
                "created_at": now - timedelta(days=98),
            },
            {
                "id": "ANN-005",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "field_id": "FLD-005",
                "annotation_type": AnnotationType.SDTM_MAPPING,
                "annotation_text": "EASI score maps to QS domain. QSCAT=EASI, QSTESTCD=EASITOT.",
                "sdtm_dataset": "QS",
                "sdtm_variable": "QSSTRESN",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "SDTM Programmer Emily Watson",
                "reviewed": True,
                "reviewed_by": "Lead Programmer Dr. Robert Kim",
                "notes": "Questionnaire domain mapping per CDISC QS IG.",
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "ANN-006",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-005",
                "field_id": "FLD-005",
                "annotation_type": AnnotationType.ADAM_MAPPING,
                "annotation_text": "EASI total score feeds into ADEFF efficacy dataset. PARAMCD=EASITOT.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": "ADEFF",
                "adam_variable": "AVAL",
                "coding_dictionary": None,
                "annotated_by": "ADaM Programmer Dr. Robert Kim",
                "reviewed": False,
                "reviewed_by": None,
                "notes": "Pending review for ADaM dataset specification alignment.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "ANN-007",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "field_id": "FLD-007",
                "annotation_type": AnnotationType.VALIDATION_RULE,
                "annotation_text": "Peak pruritus NRS requires 7-day recall period. Verify collection timepoint aligns with visit schedule.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Data Quality Manager",
                "reviewed": True,
                "reviewed_by": "Clinical Lead Dr. Emily Watson",
                "notes": "NRS pruritus recall period validation.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "ANN-008",
                "trial_id": DUPIXENT_TRIAL,
                "crf_version_id": "CRF-006",
                "field_id": "FLD-008",
                "annotation_type": AnnotationType.COMPLETION_INSTRUCTION,
                "annotation_text": "DLQI should be self-administered by patient. Do not assist with answers. Record total score only.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Clinical Lead Dr. Emily Watson",
                "reviewed": False,
                "reviewed_by": None,
                "notes": "Self-administered PRO instrument.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "ANN-009",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_id": "FLD-009",
                "annotation_type": AnnotationType.SDTM_MAPPING,
                "annotation_text": "Target lesion SLD maps to TU domain. TUTEST=DIAMETER, TUSTRESC=sum of longest diameters.",
                "sdtm_dataset": "TU",
                "sdtm_variable": "TUSTRESC",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "SDTM Programmer Angela Martinez",
                "reviewed": True,
                "reviewed_by": "Lead Oncology Programmer Dr. Grace Lee",
                "notes": "RECIST 1.1 tumor results mapping.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "ANN-010",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-009",
                "field_id": "FLD-010",
                "annotation_type": AnnotationType.ADAM_MAPPING,
                "annotation_text": "Overall response maps to ADRS dataset. PARAMCD=OVRLRESP, derived from RECIST criteria.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": "ADRS",
                "adam_variable": "AVALC",
                "coding_dictionary": None,
                "annotated_by": "ADaM Programmer Dr. Grace Lee",
                "reviewed": True,
                "reviewed_by": "Biostatistics Lead",
                "notes": "Key efficacy endpoint derivation.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "ANN-011",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_id": "FLD-011",
                "annotation_type": AnnotationType.REGULATORY_NOTE,
                "annotation_text": "irAE grading must follow ASCO/NCCN immunotherapy toxicity management guidelines. Expedited reporting for Grade 3+.",
                "sdtm_dataset": None,
                "sdtm_variable": None,
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": None,
                "annotated_by": "Safety Physician Dr. David Park",
                "reviewed": True,
                "reviewed_by": "Chief Medical Officer",
                "notes": "Regulatory compliance for immunotherapy safety.",
                "created_at": now - timedelta(days=82),
            },
            {
                "id": "ANN-012",
                "trial_id": LIBTAYO_TRIAL,
                "crf_version_id": "CRF-010",
                "field_id": "FLD-012",
                "annotation_type": AnnotationType.CODING_DICTIONARY,
                "annotation_text": "Steroid medications should be coded using WHO-DD. Map to CM domain.",
                "sdtm_dataset": "CM",
                "sdtm_variable": "CMTRT",
                "adam_dataset": None,
                "adam_variable": None,
                "coding_dictionary": "WHO-DD",
                "annotated_by": "Medical Coding Team",
                "reviewed": False,
                "reviewed_by": None,
                "notes": "WHO Drug Dictionary coding requirement.",
                "created_at": now - timedelta(days=80),
            },
        ]

        for a in annotations_data:
            self._annotations[a["id"]] = CRFAnnotation(**a)

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
        logger.info("Created CRF field %s for trial %s", field_id, payload.trial_id)
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
        logger.info("Created edit check rule %s for trial %s", rule_id, payload.trial_id)
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

    def list_deployments(
        self,
        *,
        trial_id: str | None = None,
        deployment_status: DeploymentStatus | None = None,
        crf_version_id: str | None = None,
    ) -> list[CRFDeployment]:
        """List CRF deployments with optional filters."""
        with self._lock:
            result = list(self._deployments.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if deployment_status is not None:
            result = [d for d in result if d.deployment_status == deployment_status]
        if crf_version_id is not None:
            result = [d for d in result if d.crf_version_id == crf_version_id]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_deployment(self, deployment_id: str) -> CRFDeployment | None:
        """Get a single CRF deployment by ID."""
        with self._lock:
            return self._deployments.get(deployment_id)

    def create_deployment(self, payload: CRFDeploymentCreate) -> CRFDeployment:
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
            self._deployments[deployment_id] = record
        logger.info("Created CRF deployment %s for trial %s", deployment_id, payload.trial_id)
        return record

    def update_deployment(
        self, deployment_id: str, payload: CRFDeploymentUpdate
    ) -> CRFDeployment | None:
        """Update an existing CRF deployment."""
        with self._lock:
            existing = self._deployments.get(deployment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CRFDeployment(**data)
            self._deployments[deployment_id] = updated
        return updated

    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a CRF deployment. Returns True if deleted."""
        with self._lock:
            if deployment_id in self._deployments:
                del self._deployments[deployment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # CRF Annotations
    # ------------------------------------------------------------------

    def list_annotations(
        self,
        *,
        trial_id: str | None = None,
        crf_version_id: str | None = None,
        annotation_type: AnnotationType | None = None,
    ) -> list[CRFAnnotation]:
        """List CRF annotations with optional filters."""
        with self._lock:
            result = list(self._annotations.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if crf_version_id is not None:
            result = [a for a in result if a.crf_version_id == crf_version_id]
        if annotation_type is not None:
            result = [a for a in result if a.annotation_type == annotation_type]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_annotation(self, annotation_id: str) -> CRFAnnotation | None:
        """Get a single CRF annotation by ID."""
        with self._lock:
            return self._annotations.get(annotation_id)

    def create_annotation(self, payload: CRFAnnotationCreate) -> CRFAnnotation:
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
            self._annotations[annotation_id] = record
        logger.info("Created CRF annotation %s for trial %s", annotation_id, payload.trial_id)
        return record

    def update_annotation(
        self, annotation_id: str, payload: CRFAnnotationUpdate
    ) -> CRFAnnotation | None:
        """Update an existing CRF annotation."""
        with self._lock:
            existing = self._annotations.get(annotation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CRFAnnotation(**data)
            self._annotations[annotation_id] = updated
        return updated

    def delete_annotation(self, annotation_id: str) -> bool:
        """Delete a CRF annotation. Returns True if deleted."""
        with self._lock:
            if annotation_id in self._annotations:
                del self._annotations[annotation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> CRFManagementMetrics:
        """Compute aggregated CRF management metrics."""
        with self._lock:
            versions = list(self._crf_versions.values())
            fields = list(self._crf_fields.values())
            edit_checks = list(self._edit_check_rules.values())
            deployments = list(self._deployments.values())
            annotations = list(self._annotations.values())

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
