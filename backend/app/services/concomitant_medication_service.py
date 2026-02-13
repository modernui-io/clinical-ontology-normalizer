"""Concomitant Medication Tracking Service (CMT-TRK).

Manages concomitant medication operations: medication records, drug interaction
checks, prohibited medication alerts, medication reconciliation tasks, and
concomitant medication metrics.

Usage:
    from app.services.concomitant_medication_service import (
        get_concomitant_medication_service,
    )

    svc = get_concomitant_medication_service()
    records = svc.list_medication_records()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.concomitant_medication import (
    AlertPriority,
    AlertStatus,
    ConcomitantMedicationMetrics,
    DrugInteractionCheck,
    DrugInteractionCheckCreate,
    DrugInteractionCheckUpdate,
    InteractionSeverity,
    MedicationRecord,
    MedicationRecordCreate,
    MedicationRecordUpdate,
    MedicationReconciliation,
    MedicationReconciliationCreate,
    MedicationReconciliationUpdate,
    MedicationStatus,
    ProhibitedMedicationAlert,
    ProhibitedMedicationAlertCreate,
    ProhibitedMedicationAlertUpdate,
    ReconciliationOutcome,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ConcomitantMedicationService:
    """In-memory Concomitant Medication Tracking engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._medication_records: dict[str, MedicationRecord] = {}
        self._drug_interaction_checks: dict[str, DrugInteractionCheck] = {}
        self._prohibited_medication_alerts: dict[str, ProhibitedMedicationAlert] = {}
        self._medication_reconciliations: dict[str, MedicationReconciliation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic concomitant medication data."""
        now = datetime.now(timezone.utc)

        # --- 12 Medication Records ---
        medication_records_data = [
            {
                "id": "MED-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "medication_name": "Metformin",
                "generic_name": "Metformin Hydrochloride",
                "rxnorm_code": "860975",
                "atc_code": "A10BA02",
                "medication_status": MedicationStatus.ONGOING,
                "indication": "Type 2 Diabetes Mellitus",
                "dose": "500",
                "dose_unit": "mg",
                "frequency": "Twice daily",
                "route": "Oral",
                "start_date": now - timedelta(days=365),
                "end_date": None,
                "prescriber_name": "Dr. Sarah Johnson",
                "recorded_by": "CRC Maria Lopez",
                "notes": "Stable dose for 12 months. No dose adjustments needed.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "MED-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "medication_name": "Lisinopril",
                "generic_name": "Lisinopril",
                "rxnorm_code": "104377",
                "atc_code": "C09AA03",
                "medication_status": MedicationStatus.ONGOING,
                "indication": "Hypertension",
                "dose": "10",
                "dose_unit": "mg",
                "frequency": "Once daily",
                "route": "Oral",
                "start_date": now - timedelta(days=730),
                "end_date": None,
                "prescriber_name": "Dr. Sarah Johnson",
                "recorded_by": "CRC Maria Lopez",
                "notes": "Well-controlled blood pressure on current dose.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "MED-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "medication_name": "Atorvastatin",
                "generic_name": "Atorvastatin Calcium",
                "rxnorm_code": "259255",
                "atc_code": "C10AA05",
                "medication_status": MedicationStatus.ONGOING,
                "indication": "Hypercholesterolemia",
                "dose": "20",
                "dose_unit": "mg",
                "frequency": "Once daily at bedtime",
                "route": "Oral",
                "start_date": now - timedelta(days=200),
                "end_date": None,
                "prescriber_name": "Dr. James Rodriguez",
                "recorded_by": "CRC Maria Lopez",
                "notes": "LDL within target range. Continue current dose.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "MED-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "medication_name": "Ibuprofen",
                "generic_name": "Ibuprofen",
                "rxnorm_code": "5640",
                "atc_code": "M01AE01",
                "medication_status": MedicationStatus.COMPLETED,
                "indication": "Headache",
                "dose": "400",
                "dose_unit": "mg",
                "frequency": "As needed",
                "route": "Oral",
                "start_date": now - timedelta(days=60),
                "end_date": now - timedelta(days=55),
                "prescriber_name": None,
                "recorded_by": "CRC Tom Bradley",
                "notes": "OTC use for intermittent headaches. Completed short course.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "MED-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "medication_name": "Cetirizine",
                "generic_name": "Cetirizine Hydrochloride",
                "rxnorm_code": "20610",
                "atc_code": "R06AE07",
                "medication_status": MedicationStatus.ONGOING,
                "indication": "Allergic rhinitis",
                "dose": "10",
                "dose_unit": "mg",
                "frequency": "Once daily",
                "route": "Oral",
                "start_date": now - timedelta(days=180),
                "end_date": None,
                "prescriber_name": "Dr. Karen Liu",
                "recorded_by": "CRC Rachel Green",
                "notes": "Seasonal allergy management. Permitted per protocol.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "MED-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "medication_name": "Triamcinolone Acetonide Cream",
                "generic_name": "Triamcinolone Acetonide",
                "rxnorm_code": "10759",
                "atc_code": "D07AB09",
                "medication_status": MedicationStatus.DISCONTINUED,
                "indication": "Atopic dermatitis flare",
                "dose": "0.1%",
                "dose_unit": "topical",
                "frequency": "Twice daily",
                "route": "Topical",
                "start_date": now - timedelta(days=100),
                "end_date": now - timedelta(days=70),
                "prescriber_name": "Dr. Michael Torres",
                "recorded_by": "CRC Rachel Green",
                "notes": "Discontinued per protocol. Topical corticosteroids prohibited during active treatment.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "MED-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "medication_name": "Omeprazole",
                "generic_name": "Omeprazole",
                "rxnorm_code": "7646",
                "atc_code": "A02BC01",
                "medication_status": MedicationStatus.ONGOING,
                "indication": "Gastroesophageal reflux disease",
                "dose": "20",
                "dose_unit": "mg",
                "frequency": "Once daily before breakfast",
                "route": "Oral",
                "start_date": now - timedelta(days=300),
                "end_date": None,
                "prescriber_name": "Dr. Karen Liu",
                "recorded_by": "CRC Rachel Green",
                "notes": "Chronic GERD management. No protocol restrictions.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "MED-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "medication_name": "Amoxicillin",
                "generic_name": "Amoxicillin Trihydrate",
                "rxnorm_code": "723",
                "atc_code": "J01CA04",
                "medication_status": MedicationStatus.COMPLETED,
                "indication": "Upper respiratory tract infection",
                "dose": "500",
                "dose_unit": "mg",
                "frequency": "Three times daily",
                "route": "Oral",
                "start_date": now - timedelta(days=45),
                "end_date": now - timedelta(days=35),
                "prescriber_name": "Dr. Alex Yun",
                "recorded_by": "CRC Alex Yun",
                "notes": "10-day course completed. Infection resolved.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "MED-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "medication_name": "Ondansetron",
                "generic_name": "Ondansetron Hydrochloride",
                "rxnorm_code": "26225",
                "atc_code": "A04AA01",
                "medication_status": MedicationStatus.PRN,
                "indication": "Chemotherapy-induced nausea",
                "dose": "8",
                "dose_unit": "mg",
                "frequency": "Every 8 hours as needed",
                "route": "Oral",
                "start_date": now - timedelta(days=70),
                "end_date": None,
                "prescriber_name": "Dr. Angela Martinez",
                "recorded_by": "CRC Kevin Owens",
                "notes": "PRN anti-emetic for treatment-related nausea. Used intermittently.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "MED-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "medication_name": "Dexamethasone",
                "generic_name": "Dexamethasone",
                "rxnorm_code": "3264",
                "atc_code": "H02AB02",
                "medication_status": MedicationStatus.ON_HOLD,
                "indication": "Pre-medication for infusion reactions",
                "dose": "4",
                "dose_unit": "mg",
                "frequency": "Before each infusion",
                "route": "Intravenous",
                "start_date": now - timedelta(days=70),
                "end_date": None,
                "prescriber_name": "Dr. Angela Martinez",
                "recorded_by": "CRC Kevin Owens",
                "notes": "On hold pending medical monitor review of cumulative steroid exposure.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "MED-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "medication_name": "Levothyroxine",
                "generic_name": "Levothyroxine Sodium",
                "rxnorm_code": "10582",
                "atc_code": "H03AA01",
                "medication_status": MedicationStatus.ONGOING,
                "indication": "Hypothyroidism (immune-related AE)",
                "dose": "75",
                "dose_unit": "mcg",
                "frequency": "Once daily in the morning",
                "route": "Oral",
                "start_date": now - timedelta(days=30),
                "end_date": None,
                "prescriber_name": "Dr. David Park",
                "recorded_by": "CRC Kevin Owens",
                "notes": "Started for treatment-emergent hypothyroidism. TSH monitoring every 6 weeks.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MED-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "medication_name": "Acetaminophen",
                "generic_name": "Acetaminophen",
                "rxnorm_code": "161",
                "atc_code": "N02BE01",
                "medication_status": MedicationStatus.NOT_STARTED,
                "indication": "Fever and pain management",
                "dose": "500",
                "dose_unit": "mg",
                "frequency": "Every 6 hours as needed",
                "route": "Oral",
                "start_date": now - timedelta(days=10),
                "end_date": None,
                "prescriber_name": "Dr. Sarah Kim",
                "recorded_by": "CRC Amy Chen",
                "notes": "Prescribed prophylactically. Subject has not yet required use.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for m in medication_records_data:
            self._medication_records[m["id"]] = MedicationRecord(**m)

        # --- 12 Drug Interaction Checks ---
        interaction_checks_data = [
            {
                "id": "DIC-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "medication_record_id": "MED-001",
                "study_drug_name": "Aflibercept (Eylea)",
                "interaction_severity": InteractionSeverity.NONE_KNOWN,
                "interaction_description": "No known interaction between intravitreal aflibercept and oral metformin.",
                "clinical_significance": "No clinical concern",
                "recommendation": "Continue both medications without adjustment.",
                "checked_date": now - timedelta(days=89),
                "checked_by": "Clinical Pharmacist Dr. Emily White",
                "source_database": "Lexicomp Drug Interactions",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Routine screening. No systemic interaction expected with intravitreal administration.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "DIC-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "medication_record_id": "MED-002",
                "study_drug_name": "Aflibercept (Eylea)",
                "interaction_severity": InteractionSeverity.MILD,
                "interaction_description": "Theoretical risk of additive hypotension with anti-VEGF therapy and ACE inhibitors.",
                "clinical_significance": "Low clinical significance for intravitreal route",
                "recommendation": "Monitor blood pressure at study visits. No dose adjustment needed.",
                "checked_date": now - timedelta(days=89),
                "checked_by": "Clinical Pharmacist Dr. Emily White",
                "source_database": "Lexicomp Drug Interactions",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Minimal systemic exposure from intravitreal injection limits interaction risk.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "DIC-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "medication_record_id": "MED-003",
                "study_drug_name": "Aflibercept (Eylea)",
                "interaction_severity": InteractionSeverity.NONE_KNOWN,
                "interaction_description": "No known interaction between aflibercept and atorvastatin.",
                "clinical_significance": "No clinical concern",
                "recommendation": "Continue without modification.",
                "checked_date": now - timedelta(days=84),
                "checked_by": "Clinical Pharmacist Dr. Emily White",
                "source_database": "Micromedex",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Standard screening completed.",
                "created_at": now - timedelta(days=84),
            },
            {
                "id": "DIC-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "medication_record_id": "MED-004",
                "study_drug_name": "Aflibercept (Eylea)",
                "interaction_severity": InteractionSeverity.MODERATE,
                "interaction_description": "NSAIDs may increase bleeding risk with anti-VEGF therapies.",
                "clinical_significance": "Potential for increased ocular hemorrhage risk",
                "recommendation": "Avoid NSAIDs within 7 days of intravitreal injection if possible.",
                "checked_date": now - timedelta(days=59),
                "checked_by": "Clinical Pharmacist Dr. Emily White",
                "source_database": "Lexicomp Drug Interactions",
                "override_approved": True,
                "override_by": "PI Dr. Sarah Johnson",
                "override_rationale": "Short-term use only. Timing does not overlap with injection schedule.",
                "notes": "Override approved due to non-overlapping administration windows.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "DIC-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "medication_record_id": "MED-005",
                "study_drug_name": "Dupilumab (Dupixent)",
                "interaction_severity": InteractionSeverity.NONE_KNOWN,
                "interaction_description": "No known interaction between dupilumab and cetirizine.",
                "clinical_significance": "No clinical concern",
                "recommendation": "Continue both medications.",
                "checked_date": now - timedelta(days=74),
                "checked_by": "Clinical Pharmacist Dr. Mark Phillips",
                "source_database": "Lexicomp Drug Interactions",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Antihistamines are commonly used alongside dupilumab.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "DIC-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "medication_record_id": "MED-006",
                "study_drug_name": "Dupilumab (Dupixent)",
                "interaction_severity": InteractionSeverity.SEVERE,
                "interaction_description": "Topical corticosteroids may confound efficacy assessment of dupilumab in atopic dermatitis trials.",
                "clinical_significance": "High - may compromise study endpoint integrity",
                "recommendation": "Discontinue topical corticosteroids per protocol washout requirements.",
                "checked_date": now - timedelta(days=99),
                "checked_by": "Clinical Pharmacist Dr. Mark Phillips",
                "source_database": "Protocol Section 6.5 Prohibited Medications",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Prohibited medication identified. Alert generated. Medication subsequently discontinued.",
                "created_at": now - timedelta(days=99),
            },
            {
                "id": "DIC-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "medication_record_id": "MED-007",
                "study_drug_name": "Dupilumab (Dupixent)",
                "interaction_severity": InteractionSeverity.NONE_KNOWN,
                "interaction_description": "No known interaction between dupilumab and omeprazole.",
                "clinical_significance": "No clinical concern",
                "recommendation": "Continue without modification.",
                "checked_date": now - timedelta(days=49),
                "checked_by": "Clinical Pharmacist Dr. Mark Phillips",
                "source_database": "Micromedex",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "PPI use does not affect subcutaneous drug absorption.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "DIC-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "medication_record_id": "MED-008",
                "study_drug_name": "Dupilumab (Dupixent)",
                "interaction_severity": InteractionSeverity.UNKNOWN,
                "interaction_description": "Limited data on concurrent antibiotic use with dupilumab.",
                "clinical_significance": "Unknown - monitor for any changes in efficacy",
                "recommendation": "Continue antibiotic course. Monitor for changes in AD severity.",
                "checked_date": now - timedelta(days=44),
                "checked_by": "Clinical Pharmacist Dr. Mark Phillips",
                "source_database": "Lexicomp Drug Interactions",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Short-term antibiotic use unlikely to affect biologic therapy.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "DIC-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "medication_record_id": "MED-009",
                "study_drug_name": "Cemiplimab (Libtayo)",
                "interaction_severity": InteractionSeverity.NONE_KNOWN,
                "interaction_description": "No known interaction between cemiplimab and ondansetron.",
                "clinical_significance": "No clinical concern",
                "recommendation": "Continue anti-emetic as needed.",
                "checked_date": now - timedelta(days=69),
                "checked_by": "Clinical Pharmacist Dr. Grace Lee",
                "source_database": "Lexicomp Drug Interactions",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Standard supportive care medication. No interaction expected.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "DIC-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "medication_record_id": "MED-010",
                "study_drug_name": "Cemiplimab (Libtayo)",
                "interaction_severity": InteractionSeverity.SEVERE,
                "interaction_description": "Systemic corticosteroids may reduce efficacy of checkpoint inhibitor immunotherapy.",
                "clinical_significance": "High - corticosteroids are immunosuppressive and may antagonize cemiplimab mechanism",
                "recommendation": "Limit corticosteroid use to prednisone equivalent <=10mg/day or use for irAE management only.",
                "checked_date": now - timedelta(days=69),
                "checked_by": "Clinical Pharmacist Dr. Grace Lee",
                "source_database": "Protocol Section 5.3 and Lexicomp",
                "override_approved": True,
                "override_by": "Medical Monitor Dr. Angela Martinez",
                "override_rationale": "Low-dose pre-medication only. Single IV dose before infusion does not constitute chronic corticosteroid use.",
                "notes": "Override approved with stipulation to reassess cumulative exposure at each visit.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "DIC-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "medication_record_id": "MED-011",
                "study_drug_name": "Cemiplimab (Libtayo)",
                "interaction_severity": InteractionSeverity.MILD,
                "interaction_description": "Levothyroxine initiated for treatment-emergent hypothyroidism. Expected irAE management.",
                "clinical_significance": "Low - thyroid replacement is standard irAE management",
                "recommendation": "Continue levothyroxine and monitor TSH levels per protocol.",
                "checked_date": now - timedelta(days=29),
                "checked_by": "Clinical Pharmacist Dr. Grace Lee",
                "source_database": "Lexicomp Drug Interactions",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Thyroid hormone replacement does not interact with checkpoint inhibitor therapy.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "DIC-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "medication_record_id": "MED-012",
                "study_drug_name": "Cemiplimab (Libtayo)",
                "interaction_severity": InteractionSeverity.NONE_KNOWN,
                "interaction_description": "No known interaction between cemiplimab and acetaminophen.",
                "clinical_significance": "No clinical concern",
                "recommendation": "Continue acetaminophen as needed for symptom management.",
                "checked_date": now - timedelta(days=9),
                "checked_by": "Clinical Pharmacist Dr. Grace Lee",
                "source_database": "Micromedex",
                "override_approved": False,
                "override_by": None,
                "override_rationale": None,
                "notes": "Preferred analgesic/antipyretic in oncology setting.",
                "created_at": now - timedelta(days=9),
            },
        ]

        for dic in interaction_checks_data:
            self._drug_interaction_checks[dic["id"]] = DrugInteractionCheck(**dic)

        # --- 12 Prohibited Medication Alerts ---
        prohibited_alerts_data = [
            {
                "id": "PMA-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.HIGH,
                "alert_status": AlertStatus.RESOLVED,
                "medication_name": "Bevacizumab (Avastin)",
                "prohibition_reason": "Concurrent anti-VEGF therapy prohibited per protocol Section 4.2",
                "protocol_section": "Section 4.2 - Prohibited Medications",
                "detected_date": now - timedelta(days=88),
                "acknowledged_by": "PI Dr. Sarah Johnson",
                "acknowledged_date": now - timedelta(days=88),
                "resolution_action": "Confirmed not prescribed. Alert was triggered by prior medication history review.",
                "resolution_date": now - timedelta(days=87),
                "deviation_filed": False,
                "notes": "False positive. Bevacizumab was listed in historical medications, not current.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "PMA-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.CRITICAL,
                "alert_status": AlertStatus.RESOLVED,
                "medication_name": "Ranibizumab (Lucentis)",
                "prohibition_reason": "Concurrent anti-VEGF therapy prohibited. Only study drug (aflibercept) permitted.",
                "protocol_section": "Section 4.2 - Prohibited Medications",
                "detected_date": now - timedelta(days=60),
                "acknowledged_by": "PI Dr. Sarah Johnson",
                "acknowledged_date": now - timedelta(days=60),
                "resolution_action": "External ophthalmologist contacted. Confirmed ranibizumab will not be administered.",
                "resolution_date": now - timedelta(days=58),
                "deviation_filed": False,
                "notes": "Subject's outside ophthalmologist was unaware of study enrollment. Educated on restrictions.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PMA-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "medication_record_id": "MED-004",
                "alert_priority": AlertPriority.MEDIUM,
                "alert_status": AlertStatus.ACKNOWLEDGED,
                "medication_name": "Ibuprofen",
                "prohibition_reason": "NSAIDs should be avoided within 7 days of intravitreal injection per protocol.",
                "protocol_section": "Section 4.3 - Restricted Medications",
                "detected_date": now - timedelta(days=59),
                "acknowledged_by": "CRC Tom Bradley",
                "acknowledged_date": now - timedelta(days=59),
                "resolution_action": None,
                "resolution_date": None,
                "deviation_filed": True,
                "notes": "Subject used OTC ibuprofen within restricted window. Protocol deviation filed.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "PMA-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.LOW,
                "alert_status": AlertStatus.DISMISSED,
                "medication_name": "Artificial Tears",
                "prohibition_reason": "Some formulations contain vasoconstrictors. Review required.",
                "protocol_section": "Section 4.3 - Restricted Medications",
                "detected_date": now - timedelta(days=30),
                "acknowledged_by": "CRC Maria Lopez",
                "acknowledged_date": now - timedelta(days=30),
                "resolution_action": "Preservative-free formulation confirmed. No vasoconstrictor present.",
                "resolution_date": now - timedelta(days=30),
                "deviation_filed": False,
                "notes": "Dismissed. Product confirmed as preservative-free artificial tears only.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "PMA-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "medication_record_id": "MED-006",
                "alert_priority": AlertPriority.CRITICAL,
                "alert_status": AlertStatus.RESOLVED,
                "medication_name": "Triamcinolone Acetonide Cream",
                "prohibition_reason": "Topical corticosteroids prohibited during active treatment phase per protocol Section 6.5",
                "protocol_section": "Section 6.5 - Prohibited Medications",
                "detected_date": now - timedelta(days=99),
                "acknowledged_by": "PI Dr. Michael Torres",
                "acknowledged_date": now - timedelta(days=99),
                "resolution_action": "Medication discontinued immediately. Subject educated on protocol restrictions.",
                "resolution_date": now - timedelta(days=98),
                "deviation_filed": True,
                "notes": "Protocol deviation filed. Subject used TCS for 30 days before detection. Washout initiated.",
                "created_at": now - timedelta(days=99),
            },
            {
                "id": "PMA-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.HIGH,
                "alert_status": AlertStatus.ACTIVE,
                "medication_name": "Cyclosporine",
                "prohibition_reason": "Systemic immunosuppressants prohibited during dupilumab treatment per protocol Section 6.5",
                "protocol_section": "Section 6.5 - Prohibited Medications",
                "detected_date": now - timedelta(days=15),
                "acknowledged_by": None,
                "acknowledged_date": None,
                "resolution_action": None,
                "resolution_date": None,
                "deviation_filed": False,
                "notes": "Alert triggered by external pharmacy notification. Pending PI review.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "PMA-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.INFORMATIONAL,
                "alert_status": AlertStatus.EXPIRED,
                "medication_name": "Tacrolimus Ointment",
                "prohibition_reason": "Topical calcineurin inhibitors restricted during screening period.",
                "protocol_section": "Section 6.4 - Screening Restrictions",
                "detected_date": now - timedelta(days=50),
                "acknowledged_by": "CRC Alex Yun",
                "acknowledged_date": now - timedelta(days=50),
                "resolution_action": "Screening period ended. Restriction no longer applicable.",
                "resolution_date": now - timedelta(days=40),
                "deviation_filed": False,
                "notes": "Historical alert. Subject completed screening washout successfully.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "PMA-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.MEDIUM,
                "alert_status": AlertStatus.OVERRIDDEN,
                "medication_name": "Hydrocortisone Cream 1%",
                "prohibition_reason": "Low-potency topical corticosteroid use requires PI approval per protocol amendment.",
                "protocol_section": "Section 6.5.1 - Protocol Amendment 3",
                "detected_date": now - timedelta(days=20),
                "acknowledged_by": "PI Dr. Michael Torres",
                "acknowledged_date": now - timedelta(days=20),
                "resolution_action": "PI approved limited use for face/intertriginous areas only per protocol amendment.",
                "resolution_date": now - timedelta(days=19),
                "deviation_filed": False,
                "notes": "Override approved per protocol amendment 3. Limited to specified body areas.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "PMA-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "medication_record_id": "MED-010",
                "alert_priority": AlertPriority.HIGH,
                "alert_status": AlertStatus.RESOLVED,
                "medication_name": "Dexamethasone",
                "prohibition_reason": "Systemic corticosteroids >10mg prednisone equivalent/day may reduce immunotherapy efficacy.",
                "protocol_section": "Section 5.3 - Corticosteroid Restrictions",
                "detected_date": now - timedelta(days=68),
                "acknowledged_by": "Medical Monitor Dr. Angela Martinez",
                "acknowledged_date": now - timedelta(days=68),
                "resolution_action": "Pre-medication protocol adjusted to use minimum effective dose.",
                "resolution_date": now - timedelta(days=67),
                "deviation_filed": False,
                "notes": "Resolved with dose reduction. Cumulative exposure within acceptable limits.",
                "created_at": now - timedelta(days=68),
            },
            {
                "id": "PMA-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.CRITICAL,
                "alert_status": AlertStatus.ACTIVE,
                "medication_name": "Infliximab",
                "prohibition_reason": "TNF-alpha inhibitors and other immunomodulators are contraindicated with PD-1 inhibitors.",
                "protocol_section": "Section 5.2 - Contraindicated Medications",
                "detected_date": now - timedelta(days=5),
                "acknowledged_by": None,
                "acknowledged_date": None,
                "resolution_action": None,
                "resolution_date": None,
                "deviation_filed": False,
                "notes": "Urgent: External rheumatologist prescribed infliximab. Immediate PI notification required.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "PMA-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.MEDIUM,
                "alert_status": AlertStatus.ACKNOWLEDGED,
                "medication_name": "Prednisone",
                "prohibition_reason": "Chronic corticosteroid use (>10mg/day prednisone equivalent) prohibited.",
                "protocol_section": "Section 5.3 - Corticosteroid Restrictions",
                "detected_date": now - timedelta(days=8),
                "acknowledged_by": "CRC Amy Chen",
                "acknowledged_date": now - timedelta(days=7),
                "resolution_action": None,
                "resolution_date": None,
                "deviation_filed": False,
                "notes": "Subject reported intermittent use. Dose and frequency under investigation.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "PMA-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "medication_record_id": None,
                "alert_priority": AlertPriority.LOW,
                "alert_status": AlertStatus.RESOLVED,
                "medication_name": "Live Influenza Vaccine",
                "prohibition_reason": "Live vaccines prohibited during immunotherapy treatment.",
                "protocol_section": "Section 5.4 - Vaccination Restrictions",
                "detected_date": now - timedelta(days=40),
                "acknowledged_by": "CRC Kevin Owens",
                "acknowledged_date": now - timedelta(days=40),
                "resolution_action": "Subject advised to receive inactivated flu vaccine instead. Vaccination rescheduled.",
                "resolution_date": now - timedelta(days=38),
                "deviation_filed": False,
                "notes": "Prevented administration of live vaccine. Inactivated alternative arranged.",
                "created_at": now - timedelta(days=40),
            },
        ]

        for pma in prohibited_alerts_data:
            self._prohibited_medication_alerts[pma["id"]] = ProhibitedMedicationAlert(**pma)

        # --- 12 Medication Reconciliation Records ---
        reconciliation_data = [
            {
                "id": "MRC-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "reconciliation_outcome": ReconciliationOutcome.RECONCILED,
                "visit_number": 1,
                "reconciliation_date": now - timedelta(days=89),
                "medications_reviewed": 3,
                "discrepancies_found": 0,
                "new_medications_added": 2,
                "medications_discontinued": 0,
                "performed_by": "CRC Maria Lopez",
                "verified_by": "PI Dr. Sarah Johnson",
                "notes": "Screening visit reconciliation. All concomitant medications documented and verified.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "MRC-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "reconciliation_outcome": ReconciliationOutcome.RECONCILED,
                "visit_number": 2,
                "reconciliation_date": now - timedelta(days=60),
                "medications_reviewed": 3,
                "discrepancies_found": 0,
                "new_medications_added": 0,
                "medications_discontinued": 0,
                "performed_by": "CRC Maria Lopez",
                "verified_by": "PI Dr. Sarah Johnson",
                "notes": "Week 4 visit. No changes to concomitant medications.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "MRC-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "reconciliation_outcome": ReconciliationOutcome.DISCREPANCY_FOUND,
                "visit_number": 1,
                "reconciliation_date": now - timedelta(days=84),
                "medications_reviewed": 5,
                "discrepancies_found": 2,
                "new_medications_added": 1,
                "medications_discontinued": 0,
                "performed_by": "CRC Maria Lopez",
                "verified_by": None,
                "notes": "Two discrepancies: dose of atorvastatin differs from pharmacy record. Aspirin not reported by subject.",
                "created_at": now - timedelta(days=84),
            },
            {
                "id": "MRC-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "reconciliation_outcome": ReconciliationOutcome.ESCALATED,
                "visit_number": 3,
                "reconciliation_date": now - timedelta(days=30),
                "medications_reviewed": 4,
                "discrepancies_found": 1,
                "new_medications_added": 1,
                "medications_discontinued": 0,
                "performed_by": "CRC Tom Bradley",
                "verified_by": None,
                "notes": "Escalated: Subject started ibuprofen within restricted window. PI review required.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MRC-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "reconciliation_outcome": ReconciliationOutcome.RECONCILED,
                "visit_number": 1,
                "reconciliation_date": now - timedelta(days=74),
                "medications_reviewed": 4,
                "discrepancies_found": 0,
                "new_medications_added": 2,
                "medications_discontinued": 0,
                "performed_by": "CRC Rachel Green",
                "verified_by": "PI Dr. Michael Torres",
                "notes": "Baseline visit. All medications verified against pharmacy records.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "MRC-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "reconciliation_outcome": ReconciliationOutcome.DISCREPANCY_FOUND,
                "visit_number": 2,
                "reconciliation_date": now - timedelta(days=50),
                "medications_reviewed": 3,
                "discrepancies_found": 1,
                "new_medications_added": 0,
                "medications_discontinued": 1,
                "performed_by": "CRC Rachel Green",
                "verified_by": "PI Dr. Michael Torres",
                "notes": "Triamcinolone not reported by subject but found in pharmacy records. Medication discontinued.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "MRC-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "reconciliation_outcome": ReconciliationOutcome.RECONCILED,
                "visit_number": 1,
                "reconciliation_date": now - timedelta(days=49),
                "medications_reviewed": 2,
                "discrepancies_found": 0,
                "new_medications_added": 1,
                "medications_discontinued": 0,
                "performed_by": "CRC Rachel Green",
                "verified_by": "PI Dr. Michael Torres",
                "notes": "Screening visit. Omeprazole documented and verified.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "MRC-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "reconciliation_outcome": ReconciliationOutcome.PENDING,
                "visit_number": 2,
                "reconciliation_date": now - timedelta(days=5),
                "medications_reviewed": 0,
                "discrepancies_found": 0,
                "new_medications_added": 0,
                "medications_discontinued": 0,
                "performed_by": "CRC Alex Yun",
                "verified_by": None,
                "notes": "Pending completion. Subject pharmacy records not yet received.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "MRC-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "reconciliation_outcome": ReconciliationOutcome.RECONCILED,
                "visit_number": 1,
                "reconciliation_date": now - timedelta(days=69),
                "medications_reviewed": 3,
                "discrepancies_found": 0,
                "new_medications_added": 2,
                "medications_discontinued": 0,
                "performed_by": "CRC Kevin Owens",
                "verified_by": "PI Dr. Angela Martinez",
                "notes": "Baseline reconciliation complete. Ondansetron and dexamethasone documented.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "MRC-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "reconciliation_outcome": ReconciliationOutcome.RECONCILED,
                "visit_number": 3,
                "reconciliation_date": now - timedelta(days=20),
                "medications_reviewed": 3,
                "discrepancies_found": 0,
                "new_medications_added": 0,
                "medications_discontinued": 0,
                "performed_by": "CRC Kevin Owens",
                "verified_by": "PI Dr. Angela Martinez",
                "notes": "Week 6 visit. No medication changes. Dexamethasone on hold documented.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "MRC-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "reconciliation_outcome": ReconciliationOutcome.DISCREPANCY_FOUND,
                "visit_number": 2,
                "reconciliation_date": now - timedelta(days=28),
                "medications_reviewed": 4,
                "discrepancies_found": 1,
                "new_medications_added": 1,
                "medications_discontinued": 0,
                "performed_by": "CRC Kevin Owens",
                "verified_by": None,
                "notes": "Levothyroxine added for irAE. Discrepancy: subject did not report herbal supplement.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "MRC-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "reconciliation_outcome": ReconciliationOutcome.DEFERRED,
                "visit_number": 1,
                "reconciliation_date": now - timedelta(days=10),
                "medications_reviewed": 1,
                "discrepancies_found": 0,
                "new_medications_added": 1,
                "medications_discontinued": 0,
                "performed_by": "CRC Amy Chen",
                "verified_by": None,
                "notes": "Deferred: Subject unable to provide complete medication list. Follow-up scheduled.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for mrc in reconciliation_data:
            self._medication_reconciliations[mrc["id"]] = MedicationReconciliation(**mrc)

    # ------------------------------------------------------------------
    # Medication Records
    # ------------------------------------------------------------------

    def list_medication_records(
        self,
        *,
        trial_id: str | None = None,
        medication_status: MedicationStatus | None = None,
        subject_id: str | None = None,
    ) -> list[MedicationRecord]:
        """List medication records with optional filters."""
        with self._lock:
            result = list(self._medication_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if medication_status is not None:
            result = [r for r in result if r.medication_status == medication_status]
        if subject_id is not None:
            result = [r for r in result if r.subject_id == subject_id]

        return sorted(result, key=lambda r: r.start_date, reverse=True)

    def get_medication_record(self, record_id: str) -> MedicationRecord | None:
        """Get a single medication record by ID."""
        with self._lock:
            return self._medication_records.get(record_id)

    def create_medication_record(self, payload: MedicationRecordCreate) -> MedicationRecord:
        """Create a new medication record."""
        now = datetime.now(timezone.utc)
        record_id = f"MED-{uuid4().hex[:8].upper()}"
        record = MedicationRecord(
            id=record_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            medication_name=payload.medication_name,
            generic_name=None,
            rxnorm_code=None,
            atc_code=None,
            medication_status=MedicationStatus.ONGOING,
            indication=payload.indication,
            dose=payload.dose,
            dose_unit=payload.dose_unit,
            frequency=payload.frequency,
            route=payload.route,
            start_date=payload.start_date,
            end_date=None,
            prescriber_name=None,
            recorded_by=payload.recorded_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._medication_records[record_id] = record
        logger.info("Created medication record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_medication_record(
        self, record_id: str, payload: MedicationRecordUpdate
    ) -> MedicationRecord | None:
        """Update an existing medication record."""
        with self._lock:
            existing = self._medication_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MedicationRecord(**data)
            self._medication_records[record_id] = updated
        return updated

    def delete_medication_record(self, record_id: str) -> bool:
        """Delete a medication record. Returns True if deleted."""
        with self._lock:
            if record_id in self._medication_records:
                del self._medication_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Drug Interaction Checks
    # ------------------------------------------------------------------

    def list_drug_interaction_checks(
        self,
        *,
        trial_id: str | None = None,
        interaction_severity: InteractionSeverity | None = None,
        subject_id: str | None = None,
    ) -> list[DrugInteractionCheck]:
        """List drug interaction checks with optional filters."""
        with self._lock:
            result = list(self._drug_interaction_checks.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if interaction_severity is not None:
            result = [r for r in result if r.interaction_severity == interaction_severity]
        if subject_id is not None:
            result = [r for r in result if r.subject_id == subject_id]

        return sorted(result, key=lambda r: r.checked_date, reverse=True)

    def get_drug_interaction_check(self, check_id: str) -> DrugInteractionCheck | None:
        """Get a single drug interaction check by ID."""
        with self._lock:
            return self._drug_interaction_checks.get(check_id)

    def create_drug_interaction_check(
        self, payload: DrugInteractionCheckCreate
    ) -> DrugInteractionCheck:
        """Create a new drug interaction check."""
        now = datetime.now(timezone.utc)
        check_id = f"DIC-{uuid4().hex[:8].upper()}"
        record = DrugInteractionCheck(
            id=check_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            medication_record_id=payload.medication_record_id,
            study_drug_name=payload.study_drug_name,
            interaction_severity=payload.interaction_severity,
            interaction_description=payload.interaction_description,
            clinical_significance=None,
            recommendation=None,
            checked_date=payload.checked_date,
            checked_by=payload.checked_by,
            source_database=None,
            override_approved=False,
            override_by=None,
            override_rationale=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._drug_interaction_checks[check_id] = record
        logger.info(
            "Created drug interaction check %s for trial %s", check_id, payload.trial_id
        )
        return record

    def update_drug_interaction_check(
        self, check_id: str, payload: DrugInteractionCheckUpdate
    ) -> DrugInteractionCheck | None:
        """Update an existing drug interaction check."""
        with self._lock:
            existing = self._drug_interaction_checks.get(check_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DrugInteractionCheck(**data)
            self._drug_interaction_checks[check_id] = updated
        return updated

    def delete_drug_interaction_check(self, check_id: str) -> bool:
        """Delete a drug interaction check. Returns True if deleted."""
        with self._lock:
            if check_id in self._drug_interaction_checks:
                del self._drug_interaction_checks[check_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Prohibited Medication Alerts
    # ------------------------------------------------------------------

    def list_prohibited_medication_alerts(
        self,
        *,
        trial_id: str | None = None,
        alert_priority: AlertPriority | None = None,
        alert_status: AlertStatus | None = None,
    ) -> list[ProhibitedMedicationAlert]:
        """List prohibited medication alerts with optional filters."""
        with self._lock:
            result = list(self._prohibited_medication_alerts.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if alert_priority is not None:
            result = [r for r in result if r.alert_priority == alert_priority]
        if alert_status is not None:
            result = [r for r in result if r.alert_status == alert_status]

        return sorted(result, key=lambda r: r.detected_date, reverse=True)

    def get_prohibited_medication_alert(
        self, alert_id: str
    ) -> ProhibitedMedicationAlert | None:
        """Get a single prohibited medication alert by ID."""
        with self._lock:
            return self._prohibited_medication_alerts.get(alert_id)

    def create_prohibited_medication_alert(
        self, payload: ProhibitedMedicationAlertCreate
    ) -> ProhibitedMedicationAlert:
        """Create a new prohibited medication alert."""
        now = datetime.now(timezone.utc)
        alert_id = f"PMA-{uuid4().hex[:8].upper()}"
        record = ProhibitedMedicationAlert(
            id=alert_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            medication_record_id=payload.medication_record_id,
            alert_priority=payload.alert_priority,
            alert_status=AlertStatus.ACTIVE,
            medication_name=payload.medication_name,
            prohibition_reason=payload.prohibition_reason,
            protocol_section=None,
            detected_date=payload.detected_date,
            acknowledged_by=None,
            acknowledged_date=None,
            resolution_action=None,
            resolution_date=None,
            deviation_filed=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._prohibited_medication_alerts[alert_id] = record
        logger.info(
            "Created prohibited medication alert %s for trial %s", alert_id, payload.trial_id
        )
        return record

    def update_prohibited_medication_alert(
        self, alert_id: str, payload: ProhibitedMedicationAlertUpdate
    ) -> ProhibitedMedicationAlert | None:
        """Update an existing prohibited medication alert."""
        with self._lock:
            existing = self._prohibited_medication_alerts.get(alert_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProhibitedMedicationAlert(**data)
            self._prohibited_medication_alerts[alert_id] = updated
        return updated

    def delete_prohibited_medication_alert(self, alert_id: str) -> bool:
        """Delete a prohibited medication alert. Returns True if deleted."""
        with self._lock:
            if alert_id in self._prohibited_medication_alerts:
                del self._prohibited_medication_alerts[alert_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Medication Reconciliations
    # ------------------------------------------------------------------

    def list_medication_reconciliations(
        self,
        *,
        trial_id: str | None = None,
        reconciliation_outcome: ReconciliationOutcome | None = None,
        subject_id: str | None = None,
    ) -> list[MedicationReconciliation]:
        """List medication reconciliations with optional filters."""
        with self._lock:
            result = list(self._medication_reconciliations.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if reconciliation_outcome is not None:
            result = [r for r in result if r.reconciliation_outcome == reconciliation_outcome]
        if subject_id is not None:
            result = [r for r in result if r.subject_id == subject_id]

        return sorted(result, key=lambda r: r.reconciliation_date, reverse=True)

    def get_medication_reconciliation(
        self, reconciliation_id: str
    ) -> MedicationReconciliation | None:
        """Get a single medication reconciliation by ID."""
        with self._lock:
            return self._medication_reconciliations.get(reconciliation_id)

    def create_medication_reconciliation(
        self, payload: MedicationReconciliationCreate
    ) -> MedicationReconciliation:
        """Create a new medication reconciliation."""
        now = datetime.now(timezone.utc)
        reconciliation_id = f"MRC-{uuid4().hex[:8].upper()}"
        record = MedicationReconciliation(
            id=reconciliation_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            reconciliation_outcome=ReconciliationOutcome.PENDING,
            visit_number=payload.visit_number,
            reconciliation_date=payload.reconciliation_date,
            medications_reviewed=0,
            discrepancies_found=0,
            new_medications_added=0,
            medications_discontinued=0,
            performed_by=payload.performed_by,
            verified_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._medication_reconciliations[reconciliation_id] = record
        logger.info(
            "Created medication reconciliation %s for trial %s",
            reconciliation_id,
            payload.trial_id,
        )
        return record

    def update_medication_reconciliation(
        self, reconciliation_id: str, payload: MedicationReconciliationUpdate
    ) -> MedicationReconciliation | None:
        """Update an existing medication reconciliation."""
        with self._lock:
            existing = self._medication_reconciliations.get(reconciliation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MedicationReconciliation(**data)
            self._medication_reconciliations[reconciliation_id] = updated
        return updated

    def delete_medication_reconciliation(self, reconciliation_id: str) -> bool:
        """Delete a medication reconciliation. Returns True if deleted."""
        with self._lock:
            if reconciliation_id in self._medication_reconciliations:
                del self._medication_reconciliations[reconciliation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ConcomitantMedicationMetrics:
        """Compute aggregated concomitant medication metrics."""
        with self._lock:
            records = list(self._medication_records.values())
            interactions = list(self._drug_interaction_checks.values())
            alerts = list(self._prohibited_medication_alerts.values())
            reconciliations = list(self._medication_reconciliations.values())

        # Records by status
        records_by_status: dict[str, int] = {}
        for r in records:
            key = r.medication_status.value
            records_by_status[key] = records_by_status.get(key, 0) + 1

        # Interactions by severity
        interactions_by_severity: dict[str, int] = {}
        for i in interactions:
            key = i.interaction_severity.value
            interactions_by_severity[key] = interactions_by_severity.get(key, 0) + 1

        # Override rate
        override_count = sum(1 for i in interactions if i.override_approved)
        override_rate = round(
            (override_count / max(1, len(interactions))) * 100, 1
        )

        # Alerts by priority
        alerts_by_priority: dict[str, int] = {}
        for a in alerts:
            key = a.alert_priority.value
            alerts_by_priority[key] = alerts_by_priority.get(key, 0) + 1

        # Alerts by status
        alerts_by_status: dict[str, int] = {}
        for a in alerts:
            key = a.alert_status.value
            alerts_by_status[key] = alerts_by_status.get(key, 0) + 1

        # Reconciliations by outcome
        reconciliations_by_outcome: dict[str, int] = {}
        for rc in reconciliations:
            key = rc.reconciliation_outcome.value
            reconciliations_by_outcome[key] = reconciliations_by_outcome.get(key, 0) + 1

        # Reconciliation rate (completed / total)
        reconciled_count = sum(
            1
            for rc in reconciliations
            if rc.reconciliation_outcome == ReconciliationOutcome.RECONCILED
        )
        reconciliation_rate = round(
            (reconciled_count / max(1, len(reconciliations))) * 100, 1
        )

        return ConcomitantMedicationMetrics(
            total_medication_records=len(records),
            records_by_status=records_by_status,
            total_interaction_checks=len(interactions),
            interactions_by_severity=interactions_by_severity,
            override_rate=override_rate,
            total_prohibited_alerts=len(alerts),
            alerts_by_priority=alerts_by_priority,
            alerts_by_status=alerts_by_status,
            total_reconciliations=len(reconciliations),
            reconciliations_by_outcome=reconciliations_by_outcome,
            reconciliation_rate=reconciliation_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ConcomitantMedicationService | None = None
_instance_lock = threading.Lock()


def get_concomitant_medication_service() -> ConcomitantMedicationService:
    """Return the singleton ConcomitantMedicationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ConcomitantMedicationService()
    return _instance


def reset_concomitant_medication_service() -> ConcomitantMedicationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ConcomitantMedicationService()
    return _instance
