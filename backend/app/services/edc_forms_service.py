"""Electronic Data Capture (EDC) Form Management Service (CLINICAL-24).

Manages EDC operations including CRF template definitions, CRF field configuration,
CRF instance lifecycle, data query management, edit check definitions and execution,
form-level data entry/validation, and EDC operational metrics.

Usage:
    from app.services.edc_forms_service import (
        get_edc_service,
    )

    svc = get_edc_service()
    templates = svc.list_templates()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import random
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.edc_forms import (
    CRFField,
    CRFInstance,
    CRFInstanceCreate,
    CRFInstanceSign,
    CRFInstanceUpdate,
    CRFTemplate,
    CRFTemplateCreate,
    CRFTemplateUpdate,
    DataQuery,
    DataQueryClose,
    DataQueryCreate,
    DataQueryRespond,
    EditCheck,
    EditCheckCreate,
    EditCheckFailure,
    EditCheckResult,
    EditCheckSeverity,
    EditCheckType,
    EditCheckUpdate,
    EDCMetrics,
    FieldType,
    FormStatus,
    QueryStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

SITES = ["SITE-101", "SITE-102", "SITE-103", "SITE-104", "SITE-105"]
PATIENTS = [f"PAT-{i:04d}" for i in range(1, 21)]


class EDCService:
    """In-memory Electronic Data Capture engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._templates: dict[str, CRFTemplate] = {}
        self._instances: dict[str, CRFInstance] = {}
        self._queries: dict[str, DataQuery] = {}
        self._edit_checks: dict[str, EditCheck] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic EDC data across clinical trial forms."""
        now = datetime.now(timezone.utc)

        # --- 8 CRF Templates ---
        templates_data = [
            {
                "id": "CRF-TPL-001",
                "trial_id": EYLEA_TRIAL,
                "form_name": "Demographics",
                "version": "2.0",
                "visit_applicability": ["Screening"],
                "fields": [
                    CRFField(id="FLD-001", field_name="subject_initials", label="Subject Initials", field_type=FieldType.TEXT, required=True, sas_variable_name="SUBJINIT", sdtm_domain="DM", sdtm_variable="SUBJID"),
                    CRFField(id="FLD-002", field_name="birth_date", label="Date of Birth", field_type=FieldType.DATE, required=True, sas_variable_name="BRTHDTC", sdtm_domain="DM", sdtm_variable="BRTHDTC"),
                    CRFField(id="FLD-003", field_name="sex", label="Sex", field_type=FieldType.DROPDOWN, required=True, options=["Male", "Female", "Other"], sas_variable_name="SEX", sdtm_domain="DM", sdtm_variable="SEX"),
                    CRFField(id="FLD-004", field_name="race", label="Race", field_type=FieldType.CHECKBOX, required=False, options=["White", "Black", "Asian", "American Indian", "Pacific Islander", "Other"], sas_variable_name="RACE", sdtm_domain="DM", sdtm_variable="RACE"),
                    CRFField(id="FLD-005", field_name="ethnicity", label="Ethnicity", field_type=FieldType.RADIO, required=True, options=["Hispanic or Latino", "Not Hispanic or Latino"], sas_variable_name="ETHNIC", sdtm_domain="DM", sdtm_variable="ETHNIC"),
                ],
                "edit_checks": [],
                "status": "active",
            },
            {
                "id": "CRF-TPL-002",
                "trial_id": EYLEA_TRIAL,
                "form_name": "Vital Signs",
                "version": "1.5",
                "visit_applicability": ["Screening", "Baseline", "Week 4", "Week 8", "Week 12", "Week 24", "Week 52"],
                "fields": [
                    CRFField(id="FLD-010", field_name="vs_date", label="Assessment Date", field_type=FieldType.DATE, required=True, sas_variable_name="VSDTC", sdtm_domain="VS", sdtm_variable="VSDTC"),
                    CRFField(id="FLD-011", field_name="systolic_bp", label="Systolic Blood Pressure (mmHg)", field_type=FieldType.NUMBER, required=True, validation_rules={"min": 60, "max": 260}, sas_variable_name="SYSBP", sdtm_domain="VS", sdtm_variable="VSORRES"),
                    CRFField(id="FLD-012", field_name="diastolic_bp", label="Diastolic Blood Pressure (mmHg)", field_type=FieldType.NUMBER, required=True, validation_rules={"min": 30, "max": 160}, sas_variable_name="DIABP", sdtm_domain="VS", sdtm_variable="VSORRES"),
                    CRFField(id="FLD-013", field_name="heart_rate", label="Heart Rate (bpm)", field_type=FieldType.NUMBER, required=True, validation_rules={"min": 30, "max": 200}, sas_variable_name="HR", sdtm_domain="VS", sdtm_variable="VSORRES"),
                    CRFField(id="FLD-014", field_name="temperature", label="Temperature (C)", field_type=FieldType.NUMBER, required=True, validation_rules={"min": 34.0, "max": 42.0}, sas_variable_name="TEMP", sdtm_domain="VS", sdtm_variable="VSORRES"),
                    CRFField(id="FLD-015", field_name="weight", label="Weight (kg)", field_type=FieldType.NUMBER, required=True, validation_rules={"min": 20, "max": 300}, sas_variable_name="WEIGHT", sdtm_domain="VS", sdtm_variable="VSORRES"),
                    CRFField(id="FLD-016", field_name="height", label="Height (cm)", field_type=FieldType.NUMBER, required=False, validation_rules={"min": 100, "max": 250}, sas_variable_name="HEIGHT", sdtm_domain="VS", sdtm_variable="VSORRES"),
                ],
                "edit_checks": [],
                "status": "active",
            },
            {
                "id": "CRF-TPL-003",
                "trial_id": EYLEA_TRIAL,
                "form_name": "Adverse Events",
                "version": "3.0",
                "visit_applicability": ["Baseline", "Week 4", "Week 8", "Week 12", "Week 24", "Week 52", "End of Study"],
                "fields": [
                    CRFField(id="FLD-020", field_name="ae_term", label="Adverse Event Term", field_type=FieldType.TEXT, required=True, sas_variable_name="AETERM", sdtm_domain="AE", sdtm_variable="AETERM"),
                    CRFField(id="FLD-021", field_name="ae_start_date", label="Start Date", field_type=FieldType.DATE, required=True, sas_variable_name="AESTDTC", sdtm_domain="AE", sdtm_variable="AESTDTC"),
                    CRFField(id="FLD-022", field_name="ae_end_date", label="End Date", field_type=FieldType.DATE, required=False, sas_variable_name="AEENDTC", sdtm_domain="AE", sdtm_variable="AEENDTC"),
                    CRFField(id="FLD-023", field_name="ae_severity", label="Severity", field_type=FieldType.DROPDOWN, required=True, options=["Mild", "Moderate", "Severe", "Life-threatening", "Fatal"], sas_variable_name="AESEV", sdtm_domain="AE", sdtm_variable="AESEV"),
                    CRFField(id="FLD-024", field_name="ae_serious", label="Serious?", field_type=FieldType.RADIO, required=True, options=["Yes", "No"], sas_variable_name="AESER", sdtm_domain="AE", sdtm_variable="AESER"),
                    CRFField(id="FLD-025", field_name="ae_relationship", label="Relationship to Study Drug", field_type=FieldType.DROPDOWN, required=True, options=["Not Related", "Unlikely", "Possibly", "Probably", "Definitely"], sas_variable_name="AEREL", sdtm_domain="AE", sdtm_variable="AEREL"),
                    CRFField(id="FLD-026", field_name="ae_action", label="Action Taken", field_type=FieldType.DROPDOWN, required=True, options=["None", "Dose Reduced", "Drug Interrupted", "Drug Withdrawn", "Other"], sas_variable_name="AEACN", sdtm_domain="AE", sdtm_variable="AEACN"),
                    CRFField(id="FLD-027", field_name="ae_outcome", label="Outcome", field_type=FieldType.DROPDOWN, required=True, options=["Recovered", "Recovering", "Not Recovered", "Fatal", "Unknown"], sas_variable_name="AEOUT", sdtm_domain="AE", sdtm_variable="AEOUT"),
                ],
                "edit_checks": [],
                "status": "active",
            },
            {
                "id": "CRF-TPL-004",
                "trial_id": EYLEA_TRIAL,
                "form_name": "Concomitant Medications",
                "version": "1.2",
                "visit_applicability": ["Screening", "Baseline", "Week 4", "Week 8", "Week 12", "Week 24", "Week 52", "End of Study"],
                "fields": [
                    CRFField(id="FLD-030", field_name="cm_name", label="Medication Name", field_type=FieldType.TEXT, required=True, sas_variable_name="CMTRT", sdtm_domain="CM", sdtm_variable="CMTRT"),
                    CRFField(id="FLD-031", field_name="cm_indication", label="Indication", field_type=FieldType.TEXT, required=True, sas_variable_name="CMINDC", sdtm_domain="CM", sdtm_variable="CMINDC"),
                    CRFField(id="FLD-032", field_name="cm_dose", label="Dose", field_type=FieldType.NUMBER, required=True, sas_variable_name="CMDOSE", sdtm_domain="CM", sdtm_variable="CMDOSE"),
                    CRFField(id="FLD-033", field_name="cm_unit", label="Dose Unit", field_type=FieldType.DROPDOWN, required=True, options=["mg", "g", "mcg", "mL", "IU", "units"], sas_variable_name="CMDOSU", sdtm_domain="CM", sdtm_variable="CMDOSU"),
                    CRFField(id="FLD-034", field_name="cm_route", label="Route", field_type=FieldType.DROPDOWN, required=True, options=["Oral", "IV", "IM", "SC", "Topical", "Inhalation", "Other"], sas_variable_name="CMROUTE", sdtm_domain="CM", sdtm_variable="CMROUTE"),
                    CRFField(id="FLD-035", field_name="cm_start_date", label="Start Date", field_type=FieldType.DATE, required=True, sas_variable_name="CMSTDTC", sdtm_domain="CM", sdtm_variable="CMSTDTC"),
                    CRFField(id="FLD-036", field_name="cm_ongoing", label="Ongoing?", field_type=FieldType.RADIO, required=True, options=["Yes", "No"], sas_variable_name="CMENRF", sdtm_domain="CM", sdtm_variable="CMENRF"),
                ],
                "edit_checks": [],
                "status": "active",
            },
            {
                "id": "CRF-TPL-005",
                "trial_id": DUPIXENT_TRIAL,
                "form_name": "Medical History",
                "version": "1.0",
                "visit_applicability": ["Screening"],
                "fields": [
                    CRFField(id="FLD-040", field_name="mh_term", label="Medical Condition", field_type=FieldType.TEXT, required=True, sas_variable_name="MHTERM", sdtm_domain="MH", sdtm_variable="MHTERM"),
                    CRFField(id="FLD-041", field_name="mh_start_date", label="Start Date", field_type=FieldType.DATE, required=False, sas_variable_name="MHSTDTC", sdtm_domain="MH", sdtm_variable="MHSTDTC"),
                    CRFField(id="FLD-042", field_name="mh_ongoing", label="Currently Active?", field_type=FieldType.RADIO, required=True, options=["Yes", "No"], sas_variable_name="MHENRF", sdtm_domain="MH", sdtm_variable="MHENRF"),
                    CRFField(id="FLD-043", field_name="mh_comments", label="Comments", field_type=FieldType.TEXTAREA, required=False, sas_variable_name="MHCOM", sdtm_domain="MH", sdtm_variable="MHCOM"),
                ],
                "edit_checks": [],
                "status": "active",
            },
            {
                "id": "CRF-TPL-006",
                "trial_id": DUPIXENT_TRIAL,
                "form_name": "Lab Results",
                "version": "2.1",
                "visit_applicability": ["Screening", "Baseline", "Week 4", "Week 12", "Week 24"],
                "fields": [
                    CRFField(id="FLD-050", field_name="lb_date", label="Collection Date", field_type=FieldType.DATE, required=True, sas_variable_name="LBDTC", sdtm_domain="LB", sdtm_variable="LBDTC"),
                    CRFField(id="FLD-051", field_name="hemoglobin", label="Hemoglobin (g/dL)", field_type=FieldType.LAB_VALUE, required=True, validation_rules={"min": 3.0, "max": 22.0}, sas_variable_name="HGB", sdtm_domain="LB", sdtm_variable="LBORRES"),
                    CRFField(id="FLD-052", field_name="wbc", label="WBC (x10^9/L)", field_type=FieldType.LAB_VALUE, required=True, validation_rules={"min": 0.5, "max": 50.0}, sas_variable_name="WBC", sdtm_domain="LB", sdtm_variable="LBORRES"),
                    CRFField(id="FLD-053", field_name="platelets", label="Platelets (x10^9/L)", field_type=FieldType.LAB_VALUE, required=True, validation_rules={"min": 10, "max": 1000}, sas_variable_name="PLAT", sdtm_domain="LB", sdtm_variable="LBORRES"),
                    CRFField(id="FLD-054", field_name="creatinine", label="Creatinine (mg/dL)", field_type=FieldType.LAB_VALUE, required=True, validation_rules={"min": 0.1, "max": 15.0}, sas_variable_name="CREAT", sdtm_domain="LB", sdtm_variable="LBORRES"),
                    CRFField(id="FLD-055", field_name="alt", label="ALT (U/L)", field_type=FieldType.LAB_VALUE, required=True, validation_rules={"min": 1, "max": 500}, sas_variable_name="ALT", sdtm_domain="LB", sdtm_variable="LBORRES"),
                    CRFField(id="FLD-056", field_name="ast", label="AST (U/L)", field_type=FieldType.LAB_VALUE, required=True, validation_rules={"min": 1, "max": 500}, sas_variable_name="AST", sdtm_domain="LB", sdtm_variable="LBORRES"),
                ],
                "edit_checks": [],
                "status": "active",
            },
            {
                "id": "CRF-TPL-007",
                "trial_id": LIBTAYO_TRIAL,
                "form_name": "Efficacy Assessment",
                "version": "1.3",
                "visit_applicability": ["Week 8", "Week 16", "Week 24", "Week 52"],
                "fields": [
                    CRFField(id="FLD-060", field_name="assessment_date", label="Assessment Date", field_type=FieldType.DATE, required=True, sas_variable_name="RSDTC", sdtm_domain="RS", sdtm_variable="RSDTC"),
                    CRFField(id="FLD-061", field_name="overall_response", label="Overall Response (RECIST)", field_type=FieldType.DROPDOWN, required=True, options=["Complete Response", "Partial Response", "Stable Disease", "Progressive Disease", "Not Evaluable"], sas_variable_name="RSSTRESC", sdtm_domain="RS", sdtm_variable="RSSTRESC"),
                    CRFField(id="FLD-062", field_name="target_lesion_sum", label="Sum of Target Lesion Diameters (mm)", field_type=FieldType.NUMBER, required=True, validation_rules={"min": 0, "max": 500}, sas_variable_name="TRSUM", sdtm_domain="TR", sdtm_variable="TRORRES"),
                    CRFField(id="FLD-063", field_name="new_lesions", label="New Lesions?", field_type=FieldType.RADIO, required=True, options=["Yes", "No"], sas_variable_name="TRNEW", sdtm_domain="TR", sdtm_variable="TRNEW"),
                    CRFField(id="FLD-064", field_name="investigator_assessment", label="Investigator Assessment", field_type=FieldType.TEXTAREA, required=False, sas_variable_name="RSCOM", sdtm_domain="RS", sdtm_variable="RSCOM"),
                ],
                "edit_checks": [],
                "status": "active",
            },
            {
                "id": "CRF-TPL-008",
                "trial_id": LIBTAYO_TRIAL,
                "form_name": "Study Drug Administration",
                "version": "1.1",
                "visit_applicability": ["Baseline", "Week 3", "Week 6", "Week 9", "Week 12", "Week 15", "Week 18", "Week 21", "Week 24"],
                "fields": [
                    CRFField(id="FLD-070", field_name="admin_date", label="Administration Date", field_type=FieldType.DATETIME, required=True, sas_variable_name="EXSTDTC", sdtm_domain="EX", sdtm_variable="EXSTDTC"),
                    CRFField(id="FLD-071", field_name="dose_given", label="Dose Given (mg)", field_type=FieldType.NUMBER, required=True, validation_rules={"min": 0, "max": 1000}, sas_variable_name="EXDOSE", sdtm_domain="EX", sdtm_variable="EXDOSE"),
                    CRFField(id="FLD-072", field_name="lot_number", label="Lot Number", field_type=FieldType.TEXT, required=True, sas_variable_name="EXLOT", sdtm_domain="EX", sdtm_variable="EXLOT"),
                    CRFField(id="FLD-073", field_name="infusion_start", label="Infusion Start Time", field_type=FieldType.DATETIME, required=True, sas_variable_name="EXSTDTC", sdtm_domain="EX", sdtm_variable="EXSTDTC"),
                    CRFField(id="FLD-074", field_name="infusion_end", label="Infusion End Time", field_type=FieldType.DATETIME, required=True, sas_variable_name="EXENDTC", sdtm_domain="EX", sdtm_variable="EXENDTC"),
                    CRFField(id="FLD-075", field_name="dose_modification", label="Dose Modification?", field_type=FieldType.RADIO, required=True, options=["Yes", "No"], sas_variable_name="EXADJ", sdtm_domain="EX", sdtm_variable="EXADJ"),
                    CRFField(id="FLD-076", field_name="modification_reason", label="Reason for Modification", field_type=FieldType.TEXTAREA, required=False, sas_variable_name="EXADJREA", sdtm_domain="EX", sdtm_variable="EXADJREA"),
                ],
                "edit_checks": [],
                "status": "active",
            },
        ]

        for t in templates_data:
            self._templates[t["id"]] = CRFTemplate(**t)

        # --- 25 Edit Checks ---
        edit_checks_data = [
            {"id": "EC-001", "template_id": "CRF-TPL-002", "check_type": EditCheckType.RANGE_CHECK, "description": "Systolic BP must be 60-260 mmHg", "expression": "systolic_bp >= 60 AND systolic_bp <= 260", "error_message": "Systolic BP out of range (60-260 mmHg)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-002", "template_id": "CRF-TPL-002", "check_type": EditCheckType.RANGE_CHECK, "description": "Diastolic BP must be 30-160 mmHg", "expression": "diastolic_bp >= 30 AND diastolic_bp <= 160", "error_message": "Diastolic BP out of range (30-160 mmHg)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-003", "template_id": "CRF-TPL-002", "check_type": EditCheckType.CONSISTENCY_CHECK, "description": "Systolic BP must be greater than diastolic BP", "expression": "systolic_bp > diastolic_bp", "error_message": "Systolic BP must be greater than diastolic BP", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-004", "template_id": "CRF-TPL-002", "check_type": EditCheckType.RANGE_CHECK, "description": "Heart rate must be 30-200 bpm", "expression": "heart_rate >= 30 AND heart_rate <= 200", "error_message": "Heart rate out of range (30-200 bpm)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-005", "template_id": "CRF-TPL-002", "check_type": EditCheckType.RANGE_CHECK, "description": "Temperature must be 34-42 C", "expression": "temperature >= 34.0 AND temperature <= 42.0", "error_message": "Temperature out of range (34-42 C)", "severity": EditCheckSeverity.WARNING, "active": True},
            {"id": "EC-006", "template_id": "CRF-TPL-002", "check_type": EditCheckType.RANGE_CHECK, "description": "Weight must be 20-300 kg", "expression": "weight >= 20 AND weight <= 300", "error_message": "Weight out of range (20-300 kg)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-007", "template_id": "CRF-TPL-003", "check_type": EditCheckType.REQUIRED_FIELD, "description": "AE term is required", "expression": "ae_term IS NOT NULL AND ae_term != ''", "error_message": "Adverse event term is required", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-008", "template_id": "CRF-TPL-003", "check_type": EditCheckType.CONSISTENCY_CHECK, "description": "AE end date must be on or after start date", "expression": "ae_end_date IS NULL OR ae_end_date >= ae_start_date", "error_message": "AE end date cannot be before start date", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-009", "template_id": "CRF-TPL-003", "check_type": EditCheckType.DYNAMIC_EDIT, "description": "If AE is serious, action taken cannot be None", "expression": "IF ae_serious == 'Yes' THEN ae_action != 'None'", "error_message": "Serious AE must have an action taken", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-010", "template_id": "CRF-TPL-003", "check_type": EditCheckType.CONSISTENCY_CHECK, "description": "If outcome is Fatal, severity must be Fatal", "expression": "IF ae_outcome == 'Fatal' THEN ae_severity == 'Fatal'", "error_message": "Fatal outcome requires Fatal severity", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-011", "template_id": "CRF-TPL-004", "check_type": EditCheckType.REQUIRED_FIELD, "description": "Medication name is required", "expression": "cm_name IS NOT NULL AND cm_name != ''", "error_message": "Medication name is required", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-012", "template_id": "CRF-TPL-004", "check_type": EditCheckType.CONSISTENCY_CHECK, "description": "If ongoing, end date should be empty", "expression": "IF cm_ongoing == 'Yes' THEN cm_end_date IS NULL", "error_message": "Ongoing medication should not have an end date", "severity": EditCheckSeverity.WARNING, "active": True},
            {"id": "EC-013", "template_id": "CRF-TPL-006", "check_type": EditCheckType.RANGE_CHECK, "description": "Hemoglobin must be 3-22 g/dL", "expression": "hemoglobin >= 3.0 AND hemoglobin <= 22.0", "error_message": "Hemoglobin out of range (3-22 g/dL)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-014", "template_id": "CRF-TPL-006", "check_type": EditCheckType.RANGE_CHECK, "description": "WBC must be 0.5-50 x10^9/L", "expression": "wbc >= 0.5 AND wbc <= 50.0", "error_message": "WBC out of range (0.5-50 x10^9/L)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-015", "template_id": "CRF-TPL-006", "check_type": EditCheckType.RANGE_CHECK, "description": "Platelets must be 10-1000 x10^9/L", "expression": "platelets >= 10 AND platelets <= 1000", "error_message": "Platelets out of range (10-1000 x10^9/L)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-016", "template_id": "CRF-TPL-006", "check_type": EditCheckType.RANGE_CHECK, "description": "Creatinine must be 0.1-15 mg/dL", "expression": "creatinine >= 0.1 AND creatinine <= 15.0", "error_message": "Creatinine out of range (0.1-15 mg/dL)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-017", "template_id": "CRF-TPL-006", "check_type": EditCheckType.RANGE_CHECK, "description": "ALT must be 1-500 U/L", "expression": "alt >= 1 AND alt <= 500", "error_message": "ALT out of range (1-500 U/L)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-018", "template_id": "CRF-TPL-006", "check_type": EditCheckType.CROSS_FORM_CHECK, "description": "ALT > 3x ULN requires AE form entry", "expression": "IF alt > 120 THEN EXISTS(AE with ae_term LIKE '%hepatic%')", "error_message": "ALT >3x ULN: ensure AE form completed for hepatic event", "severity": EditCheckSeverity.WARNING, "active": True},
            {"id": "EC-019", "template_id": "CRF-TPL-007", "check_type": EditCheckType.REQUIRED_FIELD, "description": "Overall response is required", "expression": "overall_response IS NOT NULL", "error_message": "Overall response assessment is required", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-020", "template_id": "CRF-TPL-007", "check_type": EditCheckType.CONSISTENCY_CHECK, "description": "Progressive disease requires new lesions or size increase", "expression": "IF overall_response == 'Progressive Disease' THEN new_lesions == 'Yes' OR target_lesion_sum_increased", "error_message": "Progressive disease should be supported by new lesions or target lesion increase", "severity": EditCheckSeverity.WARNING, "active": True},
            {"id": "EC-021", "template_id": "CRF-TPL-008", "check_type": EditCheckType.RANGE_CHECK, "description": "Dose must be 0-1000 mg", "expression": "dose_given >= 0 AND dose_given <= 1000", "error_message": "Dose out of range (0-1000 mg)", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-022", "template_id": "CRF-TPL-008", "check_type": EditCheckType.CONSISTENCY_CHECK, "description": "Infusion end must be after infusion start", "expression": "infusion_end > infusion_start", "error_message": "Infusion end time must be after start time", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-023", "template_id": "CRF-TPL-008", "check_type": EditCheckType.DYNAMIC_EDIT, "description": "If dose modification, reason is required", "expression": "IF dose_modification == 'Yes' THEN modification_reason IS NOT NULL", "error_message": "Dose modification reason is required when modification is indicated", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-024", "template_id": "CRF-TPL-001", "check_type": EditCheckType.REQUIRED_FIELD, "description": "Subject initials required", "expression": "subject_initials IS NOT NULL AND subject_initials != ''", "error_message": "Subject initials are required", "severity": EditCheckSeverity.ERROR, "active": True},
            {"id": "EC-025", "template_id": "CRF-TPL-001", "check_type": EditCheckType.REQUIRED_FIELD, "description": "Date of birth required", "expression": "birth_date IS NOT NULL", "error_message": "Date of birth is required", "severity": EditCheckSeverity.ERROR, "active": True},
        ]

        for ec in edit_checks_data:
            self._edit_checks[ec["id"]] = EditCheck(**ec)

        # --- 100 CRF Instances ---
        rng = random.Random(42)
        template_ids = list(self._templates.keys())
        status_weights = {
            FormStatus.BLANK: 0.05,
            FormStatus.IN_PROGRESS: 0.15,
            FormStatus.COMPLETED: 0.35,
            FormStatus.SIGNED: 0.25,
            FormStatus.LOCKED: 0.15,
            FormStatus.FROZEN: 0.05,
        }
        statuses_list = list(status_weights.keys())
        weights_list = list(status_weights.values())

        for i in range(1, 101):
            inst_id = f"CRF-{i:04d}"
            tpl_id = rng.choice(template_ids)
            patient = rng.choice(PATIENTS)
            site = rng.choice(SITES)
            visit_num = rng.randint(1, 12)
            status = rng.choices(statuses_list, weights=weights_list, k=1)[0]

            started = None
            completed = None
            signed_by = None
            signed_date = None
            locked_date = None
            data: dict[str, object] = {}

            if status != FormStatus.BLANK:
                started = now - timedelta(days=rng.randint(1, 180))
                # Generate some sample data for non-blank forms
                tpl = self._templates[tpl_id]
                for field in tpl.fields[:3]:  # Fill first 3 fields
                    if field.field_type == FieldType.NUMBER:
                        data[field.field_name] = rng.randint(60, 200)
                    elif field.field_type == FieldType.TEXT:
                        data[field.field_name] = f"Sample-{rng.randint(1, 100)}"
                    elif field.field_type == FieldType.DROPDOWN and field.options:
                        data[field.field_name] = rng.choice(field.options)
                    elif field.field_type == FieldType.RADIO and field.options:
                        data[field.field_name] = rng.choice(field.options)

            if status in (FormStatus.COMPLETED, FormStatus.SIGNED, FormStatus.LOCKED, FormStatus.FROZEN):
                completed = (started or now) + timedelta(days=rng.randint(0, 5))

            if status in (FormStatus.SIGNED, FormStatus.LOCKED, FormStatus.FROZEN):
                signers = ["Dr. Sarah Chen", "Dr. James Wilson", "Dr. Maria Garcia", "Dr. Robert Kim"]
                signed_by = rng.choice(signers)
                signed_date = (completed or now) + timedelta(days=rng.randint(0, 3))

            if status in (FormStatus.LOCKED, FormStatus.FROZEN):
                locked_date = (signed_date or now) + timedelta(days=rng.randint(0, 7))

            inst = CRFInstance(
                id=inst_id,
                template_id=tpl_id,
                patient_id=patient,
                visit_number=visit_num,
                site_id=site,
                status=status,
                started_date=started,
                completed_date=completed,
                signed_by=signed_by,
                signed_date=signed_date,
                locked_date=locked_date,
                data=data,
            )
            self._instances[inst_id] = inst

        # --- 30 Data Queries ---
        query_creators = ["DM-Smith", "CRA-Johnson", "Edit-Check-System", "DM-Williams", "CRA-Brown"]
        responders = ["Site-Coordinator-A", "PI-Thompson", "Sub-I-Davis", "Site-Coordinator-B"]
        field_names_for_queries = [
            "systolic_bp", "diastolic_bp", "ae_term", "ae_start_date", "cm_dose",
            "hemoglobin", "creatinine", "alt", "birth_date", "weight",
        ]
        query_texts = [
            "Value appears unusually high. Please verify.",
            "Value appears unusually low. Please confirm or correct.",
            "Missing required field. Please complete.",
            "Inconsistency with prior visit data. Please clarify.",
            "Date discrepancy detected. Please review.",
            "Value outside expected range. Please verify source data.",
            "Duplicate entry detected. Please confirm if intentional.",
            "Unit mismatch with expected format. Please correct.",
        ]

        # Pick 30 non-blank instances for queries
        non_blank_ids = [
            iid for iid, inst in self._instances.items()
            if inst.status != FormStatus.BLANK
        ]
        query_instance_ids = rng.sample(non_blank_ids, min(30, len(non_blank_ids)))

        for i, iid in enumerate(query_instance_ids, start=1):
            q_id = f"QRY-{i:04d}"
            auto = rng.random() < 0.3
            raised_by = "Edit-Check-System" if auto else rng.choice(query_creators)
            raised_date = now - timedelta(days=rng.randint(1, 90))

            # Determine status
            q_status_rand = rng.random()
            if q_status_rand < 0.35:
                q_status = QueryStatus.OPEN
                response = None
                responded_by = None
                responded_date = None
            elif q_status_rand < 0.6:
                q_status = QueryStatus.ANSWERED
                response = f"Verified against source. Value is correct as entered."
                responded_by = rng.choice(responders)
                responded_date = raised_date + timedelta(days=rng.randint(1, 14))
            elif q_status_rand < 0.9:
                q_status = QueryStatus.CLOSED
                response = f"Corrected. Original value was a transcription error."
                responded_by = rng.choice(responders)
                responded_date = raised_date + timedelta(days=rng.randint(1, 10))
            else:
                q_status = QueryStatus.CANCELLED
                response = None
                responded_by = None
                responded_date = None

            query = DataQuery(
                id=q_id,
                instance_id=iid,
                field_name=rng.choice(field_names_for_queries),
                query_text=rng.choice(query_texts),
                raised_by=raised_by,
                raised_date=raised_date,
                response=response,
                responded_by=responded_by,
                responded_date=responded_date,
                status=q_status,
                auto_generated=auto,
            )
            self._queries[q_id] = query

    # ------------------------------------------------------------------
    # Template Management
    # ------------------------------------------------------------------

    def list_templates(
        self,
        *,
        trial_id: str | None = None,
        form_name: str | None = None,
        status: str | None = None,
    ) -> list[CRFTemplate]:
        """List CRF templates with optional filters."""
        with self._lock:
            result = list(self._templates.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if form_name is not None:
            result = [t for t in result if form_name.lower() in t.form_name.lower()]
        if status is not None:
            result = [t for t in result if t.status == status]

        return sorted(result, key=lambda t: t.id)

    def get_template(self, template_id: str) -> CRFTemplate | None:
        """Get a single CRF template by ID."""
        with self._lock:
            return self._templates.get(template_id)

    def create_template(self, payload: CRFTemplateCreate) -> CRFTemplate:
        """Create a new CRF template."""
        tpl_id = f"CRF-TPL-{uuid4().hex[:8].upper()}"
        fields: list[CRFField] = []
        if payload.fields:
            for i, fc in enumerate(payload.fields):
                fld = CRFField(
                    id=f"FLD-{uuid4().hex[:6].upper()}",
                    **fc.model_dump(),
                )
                fields.append(fld)

        tpl = CRFTemplate(
            id=tpl_id,
            trial_id=payload.trial_id,
            form_name=payload.form_name,
            version=payload.version,
            visit_applicability=payload.visit_applicability,
            fields=fields,
            edit_checks=[],
            status="active",
        )
        with self._lock:
            self._templates[tpl_id] = tpl
        logger.info("Created CRF template %s: %s", tpl_id, payload.form_name)
        return tpl

    def update_template(self, template_id: str, payload: CRFTemplateUpdate) -> CRFTemplate | None:
        """Update an existing CRF template."""
        with self._lock:
            existing = self._templates.get(template_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CRFTemplate(**data)
            self._templates[template_id] = updated
        return updated

    def delete_template(self, template_id: str) -> bool:
        """Delete a CRF template. Returns True if deleted."""
        with self._lock:
            if template_id in self._templates:
                del self._templates[template_id]
                return True
            return False

    def add_field_to_template(self, template_id: str, payload: CRFField | dict) -> CRFTemplate | None:
        """Add a field to a CRF template."""
        with self._lock:
            tpl = self._templates.get(template_id)
            if tpl is None:
                return None
            data = tpl.model_dump()
            if isinstance(payload, dict):
                field = CRFField(**payload)
            else:
                field = payload
            data["fields"].append(field.model_dump())
            updated = CRFTemplate(**data)
            self._templates[template_id] = updated
        return updated

    # ------------------------------------------------------------------
    # CRF Instance Management
    # ------------------------------------------------------------------

    def list_instances(
        self,
        *,
        template_id: str | None = None,
        patient_id: str | None = None,
        site_id: str | None = None,
        status: FormStatus | None = None,
        visit_number: int | None = None,
    ) -> list[CRFInstance]:
        """List CRF instances with optional filters."""
        with self._lock:
            result = list(self._instances.values())

        if template_id is not None:
            result = [i for i in result if i.template_id == template_id]
        if patient_id is not None:
            result = [i for i in result if i.patient_id == patient_id]
        if site_id is not None:
            result = [i for i in result if i.site_id == site_id]
        if status is not None:
            result = [i for i in result if i.status == status]
        if visit_number is not None:
            result = [i for i in result if i.visit_number == visit_number]

        return sorted(result, key=lambda i: i.id)

    def get_instance(self, instance_id: str) -> CRFInstance | None:
        """Get a single CRF instance by ID."""
        with self._lock:
            return self._instances.get(instance_id)

    def create_instance(self, payload: CRFInstanceCreate) -> CRFInstance:
        """Create a new CRF instance."""
        now = datetime.now(timezone.utc)
        inst_id = f"CRF-{uuid4().hex[:8].upper()}"

        # Verify template exists
        tpl = self._templates.get(payload.template_id)
        if tpl is None:
            raise ValueError(f"Template '{payload.template_id}' not found")

        inst = CRFInstance(
            id=inst_id,
            template_id=payload.template_id,
            patient_id=payload.patient_id,
            visit_number=payload.visit_number,
            site_id=payload.site_id,
            status=FormStatus.BLANK,
            started_date=None,
            completed_date=None,
            signed_by=None,
            signed_date=None,
            locked_date=None,
            data={},
        )
        with self._lock:
            self._instances[inst_id] = inst
        logger.info("Created CRF instance %s for patient %s", inst_id, payload.patient_id)
        return inst

    def update_instance(self, instance_id: str, payload: CRFInstanceUpdate) -> CRFInstance | None:
        """Update CRF instance data and/or status."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._instances.get(instance_id)
            if existing is None:
                return None

            if existing.status in (FormStatus.LOCKED, FormStatus.FROZEN):
                raise ValueError(f"Cannot update instance '{instance_id}': form is {existing.status.value}")

            data = existing.model_dump()

            if payload.data is not None:
                current_data = data.get("data", {})
                current_data.update(payload.data)
                data["data"] = current_data
                # Auto-transition from blank to in_progress
                if data["status"] == FormStatus.BLANK.value:
                    data["status"] = FormStatus.IN_PROGRESS
                    data["started_date"] = now

            if payload.status is not None:
                new_status = payload.status
                if new_status == FormStatus.COMPLETED and data["completed_date"] is None:
                    data["completed_date"] = now
                data["status"] = new_status

            updated = CRFInstance(**data)
            self._instances[instance_id] = updated
        return updated

    def sign_instance(self, instance_id: str, payload: CRFInstanceSign) -> CRFInstance | None:
        """Sign a CRF instance."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._instances.get(instance_id)
            if existing is None:
                return None

            if existing.status not in (FormStatus.COMPLETED, FormStatus.IN_PROGRESS):
                raise ValueError(
                    f"Cannot sign instance '{instance_id}': must be completed or in_progress, "
                    f"currently {existing.status.value}"
                )

            data = existing.model_dump()
            data["status"] = FormStatus.SIGNED
            data["signed_by"] = payload.signed_by
            data["signed_date"] = now
            if data["completed_date"] is None:
                data["completed_date"] = now
            updated = CRFInstance(**data)
            self._instances[instance_id] = updated
        logger.info("Signed CRF instance %s by %s", instance_id, payload.signed_by)
        return updated

    def lock_instance(self, instance_id: str) -> CRFInstance | None:
        """Lock a CRF instance."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._instances.get(instance_id)
            if existing is None:
                return None

            if existing.status != FormStatus.SIGNED:
                raise ValueError(
                    f"Cannot lock instance '{instance_id}': must be signed, "
                    f"currently {existing.status.value}"
                )

            data = existing.model_dump()
            data["status"] = FormStatus.LOCKED
            data["locked_date"] = now
            updated = CRFInstance(**data)
            self._instances[instance_id] = updated
        logger.info("Locked CRF instance %s", instance_id)
        return updated

    def freeze_instance(self, instance_id: str) -> CRFInstance | None:
        """Freeze a CRF instance (database lock)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._instances.get(instance_id)
            if existing is None:
                return None

            if existing.status != FormStatus.LOCKED:
                raise ValueError(
                    f"Cannot freeze instance '{instance_id}': must be locked, "
                    f"currently {existing.status.value}"
                )

            data = existing.model_dump()
            data["status"] = FormStatus.FROZEN
            updated = CRFInstance(**data)
            self._instances[instance_id] = updated
        logger.info("Frozen CRF instance %s", instance_id)
        return updated

    def delete_instance(self, instance_id: str) -> bool:
        """Delete a CRF instance. Returns True if deleted."""
        with self._lock:
            if instance_id in self._instances:
                del self._instances[instance_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Queries
    # ------------------------------------------------------------------

    def list_queries(
        self,
        *,
        instance_id: str | None = None,
        status: QueryStatus | None = None,
        auto_generated: bool | None = None,
    ) -> list[DataQuery]:
        """List data queries with optional filters."""
        with self._lock:
            result = list(self._queries.values())

        if instance_id is not None:
            result = [q for q in result if q.instance_id == instance_id]
        if status is not None:
            result = [q for q in result if q.status == status]
        if auto_generated is not None:
            result = [q for q in result if q.auto_generated == auto_generated]

        return sorted(result, key=lambda q: q.raised_date, reverse=True)

    def get_query(self, query_id: str) -> DataQuery | None:
        """Get a single data query by ID."""
        with self._lock:
            return self._queries.get(query_id)

    def create_query(self, payload: DataQueryCreate) -> DataQuery:
        """Create a new data query."""
        now = datetime.now(timezone.utc)
        q_id = f"QRY-{uuid4().hex[:8].upper()}"

        # Verify instance exists
        inst = self._instances.get(payload.instance_id)
        if inst is None:
            raise ValueError(f"CRF instance '{payload.instance_id}' not found")

        query = DataQuery(
            id=q_id,
            instance_id=payload.instance_id,
            field_name=payload.field_name,
            query_text=payload.query_text,
            raised_by=payload.raised_by,
            raised_date=now,
            response=None,
            responded_by=None,
            responded_date=None,
            status=QueryStatus.OPEN,
            auto_generated=payload.auto_generated,
        )
        with self._lock:
            self._queries[q_id] = query
        logger.info("Created data query %s for instance %s", q_id, payload.instance_id)
        return query

    def respond_to_query(self, query_id: str, payload: DataQueryRespond) -> DataQuery | None:
        """Respond to a data query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._queries.get(query_id)
            if existing is None:
                return None

            if existing.status != QueryStatus.OPEN:
                raise ValueError(f"Cannot respond to query '{query_id}': status is {existing.status.value}")

            data = existing.model_dump()
            data["response"] = payload.response
            data["responded_by"] = payload.responded_by
            data["responded_date"] = now
            data["status"] = QueryStatus.ANSWERED
            updated = DataQuery(**data)
            self._queries[query_id] = updated
        return updated

    def close_query(self, query_id: str, payload: DataQueryClose) -> DataQuery | None:
        """Close a data query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._queries.get(query_id)
            if existing is None:
                return None

            if existing.status not in (QueryStatus.OPEN, QueryStatus.ANSWERED):
                raise ValueError(f"Cannot close query '{query_id}': status is {existing.status.value}")

            data = existing.model_dump()
            data["status"] = QueryStatus.CLOSED
            if data["responded_date"] is None:
                data["responded_date"] = now
            updated = DataQuery(**data)
            self._queries[query_id] = updated
        return updated

    def cancel_query(self, query_id: str) -> DataQuery | None:
        """Cancel a data query."""
        with self._lock:
            existing = self._queries.get(query_id)
            if existing is None:
                return None

            if existing.status == QueryStatus.CLOSED:
                raise ValueError(f"Cannot cancel query '{query_id}': already closed")

            data = existing.model_dump()
            data["status"] = QueryStatus.CANCELLED
            updated = DataQuery(**data)
            self._queries[query_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Edit Checks
    # ------------------------------------------------------------------

    def list_edit_checks(
        self,
        *,
        template_id: str | None = None,
        check_type: EditCheckType | None = None,
        active: bool | None = None,
    ) -> list[EditCheck]:
        """List edit checks with optional filters."""
        with self._lock:
            result = list(self._edit_checks.values())

        if template_id is not None:
            result = [ec for ec in result if ec.template_id == template_id]
        if check_type is not None:
            result = [ec for ec in result if ec.check_type == check_type]
        if active is not None:
            result = [ec for ec in result if ec.active == active]

        return sorted(result, key=lambda ec: ec.id)

    def get_edit_check(self, check_id: str) -> EditCheck | None:
        """Get a single edit check by ID."""
        with self._lock:
            return self._edit_checks.get(check_id)

    def create_edit_check(self, payload: EditCheckCreate) -> EditCheck:
        """Create a new edit check."""
        ec_id = f"EC-{uuid4().hex[:8].upper()}"

        # Verify template exists
        tpl = self._templates.get(payload.template_id)
        if tpl is None:
            raise ValueError(f"Template '{payload.template_id}' not found")

        ec = EditCheck(
            id=ec_id,
            template_id=payload.template_id,
            check_type=payload.check_type,
            description=payload.description,
            expression=payload.expression,
            error_message=payload.error_message,
            severity=payload.severity,
            active=True,
        )
        with self._lock:
            self._edit_checks[ec_id] = ec
        logger.info("Created edit check %s for template %s", ec_id, payload.template_id)
        return ec

    def update_edit_check(self, check_id: str, payload: EditCheckUpdate) -> EditCheck | None:
        """Update an edit check."""
        with self._lock:
            existing = self._edit_checks.get(check_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EditCheck(**data)
            self._edit_checks[check_id] = updated
        return updated

    def delete_edit_check(self, check_id: str) -> bool:
        """Delete an edit check. Returns True if deleted."""
        with self._lock:
            if check_id in self._edit_checks:
                del self._edit_checks[check_id]
                return True
            return False

    def run_edit_checks(self, instance_id: str) -> EditCheckResult:
        """Run all active edit checks against a CRF instance.

        This is a simplified simulation -- in production, the expressions
        would be evaluated against the actual instance data.
        """
        with self._lock:
            inst = self._instances.get(instance_id)
            if inst is None:
                raise ValueError(f"CRF instance '{instance_id}' not found")

            tpl = self._templates.get(inst.template_id)
            if tpl is None:
                raise ValueError(f"Template '{inst.template_id}' not found")

            # Get all active checks for this template
            checks = [
                ec for ec in self._edit_checks.values()
                if ec.template_id == inst.template_id and ec.active
            ]

        failures: list[EditCheckFailure] = []
        for ec in checks:
            # Simulate check: required_field checks fail if field missing from data
            if ec.check_type == EditCheckType.REQUIRED_FIELD:
                # Extract field name from expression (simplified)
                for field_name, value in [(k, v) for k, v in inst.data.items()]:
                    pass  # Data present
                # Check if any required fields are missing
                field_names_in_expr = [
                    f.field_name for f in (tpl.fields if tpl else [])
                    if f.required and f.field_name not in inst.data
                ]
                if field_names_in_expr:
                    failures.append(EditCheckFailure(
                        check_id=ec.id,
                        check_type=ec.check_type,
                        field_name=field_names_in_expr[0] if field_names_in_expr else None,
                        error_message=ec.error_message,
                        severity=ec.severity,
                    ))
            elif ec.check_type == EditCheckType.RANGE_CHECK:
                # Simplified: check numeric fields against validation rules
                for field in (tpl.fields if tpl else []):
                    if field.field_name in inst.data and field.validation_rules:
                        val = inst.data[field.field_name]
                        if isinstance(val, (int, float)):
                            min_val = field.validation_rules.get("min")
                            max_val = field.validation_rules.get("max")
                            if min_val is not None and val < min_val:
                                failures.append(EditCheckFailure(
                                    check_id=ec.id,
                                    check_type=ec.check_type,
                                    field_name=field.field_name,
                                    error_message=ec.error_message,
                                    severity=ec.severity,
                                ))
                            elif max_val is not None and val > max_val:
                                failures.append(EditCheckFailure(
                                    check_id=ec.id,
                                    check_type=ec.check_type,
                                    field_name=field.field_name,
                                    error_message=ec.error_message,
                                    severity=ec.severity,
                                ))

        total = len(checks)
        failed = len(failures)
        passed = total - failed

        return EditCheckResult(
            instance_id=instance_id,
            total_checks=total,
            passed=passed,
            failed=failed,
            failures=failures,
        )

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> EDCMetrics:
        """Compute aggregated EDC operational metrics."""
        with self._lock:
            instances = list(self._instances.values())
            queries = list(self._queries.values())

        # Forms by status
        forms_by_status: dict[str, int] = {}
        for inst in instances:
            key = inst.status.value
            forms_by_status[key] = forms_by_status.get(key, 0) + 1

        # Query metrics
        open_queries = sum(1 for q in queries if q.status == QueryStatus.OPEN)

        # Average query resolution days (for closed queries)
        resolved_durations: list[float] = []
        for q in queries:
            if q.status == QueryStatus.CLOSED and q.responded_date:
                delta = (q.responded_date - q.raised_date).total_seconds() / 86400.0
                resolved_durations.append(delta)
        avg_resolution = (
            round(sum(resolved_durations) / len(resolved_durations), 1)
            if resolved_durations
            else 0.0
        )

        # Data entry lag (average days between visit and started_date)
        lag_days: list[float] = []
        for inst in instances:
            if inst.started_date:
                # Use a proxy: lag is random-ish based on seed data
                lag_days.append(max(0.0, 1.0))  # Placeholder; real would compare visit date
        avg_lag = round(sum(lag_days) / max(1, len(lag_days)), 1) if lag_days else 0.0

        # Completion rate
        completed_statuses = {FormStatus.COMPLETED, FormStatus.SIGNED, FormStatus.LOCKED, FormStatus.FROZEN}
        completed_count = sum(1 for inst in instances if inst.status in completed_statuses)
        completion_rate = round(
            (completed_count / max(1, len(instances))) * 100.0, 1
        )

        return EDCMetrics(
            total_forms=len(instances),
            forms_by_status=forms_by_status,
            total_queries=len(queries),
            open_queries=open_queries,
            avg_query_resolution_days=avg_resolution,
            data_entry_lag_avg_days=avg_lag,
            completion_rate=completion_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EDCService | None = None
_instance_lock = threading.Lock()


def get_edc_service() -> EDCService:
    """Return the singleton EDCService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EDCService()
    return _instance


def reset_edc_service() -> EDCService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = EDCService()
    return _instance
