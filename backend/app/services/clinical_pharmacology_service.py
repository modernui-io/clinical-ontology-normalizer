"""Clinical Pharmacology Operations Service (CLIN-PHARM).

Manages PK/PD study definitions, pharmacokinetic sampling schedules,
bioanalytical sample tracking, dose escalation decisions, exposure-response
analyses, drug-drug interaction assessments, and pharmacology metrics.

Usage:
    from app.services.clinical_pharmacology_service import (
        get_clinical_pharmacology_service,
    )

    svc = get_clinical_pharmacology_service()
    studies = svc.list_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_pharmacology import (
    AnalysisStatus,
    ClinicalPharmacologyMetrics,
    DDIAssessment,
    DDIAssessmentCreate,
    DDIAssessmentUpdate,
    DDIRisk,
    DoseEscalation,
    DoseEscalationCreate,
    DoseEscalationUpdate,
    EscalationDecision,
    ExposureResponse,
    ExposureResponseCreate,
    ExposureResponseUpdate,
    PKSample,
    PKSampleCreate,
    PKSampleUpdate,
    PKStudy,
    PKStudyCreate,
    PKStudyUpdate,
    SampleMatrix,
    SampleStatus,
    StudyType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalPharmacologyService:
    """In-memory Clinical Pharmacology Operations engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._studies: dict[str, PKStudy] = {}
        self._samples: dict[str, PKSample] = {}
        self._escalations: dict[str, DoseEscalation] = {}
        self._exposure_analyses: dict[str, ExposureResponse] = {}
        self._ddi_assessments: dict[str, DDIAssessment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic clinical pharmacology data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 PK Studies ---
        studies_data = [
            {
                "id": "PKS-001",
                "trial_id": EYLEA_TRIAL,
                "study_type": StudyType.PK_SINGLE_DOSE,
                "title": "Aflibercept Single-Dose PK in Healthy Volunteers",
                "description": "Phase I single-dose PK study evaluating aflibercept 2mg IVT",
                "target_analyte": "aflibercept",
                "matrix": SampleMatrix.PLASMA,
                "dose_levels": ["2mg IVT"],
                "total_subjects": 24,
                "sampling_timepoints": ["0h", "1h", "2h", "4h", "8h", "12h", "24h", "48h", "72h", "168h"],
                "bioanalytical_method": "ELISA (validated)",
                "lloq": 0.05,
                "uloq": 500.0,
                "status": AnalysisStatus.COMPLETED,
                "principal_investigator": "Dr. Sarah Chen",
                "start_date": now - timedelta(days=365),
                "completion_date": now - timedelta(days=270),
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "PKS-002",
                "trial_id": EYLEA_TRIAL,
                "study_type": StudyType.PK_MULTIPLE_DOSE,
                "title": "Aflibercept Multiple-Dose PK with Q8W Regimen",
                "description": "Steady-state PK evaluation of aflibercept 2mg IVT every 8 weeks",
                "target_analyte": "aflibercept",
                "matrix": SampleMatrix.SERUM,
                "dose_levels": ["2mg IVT Q8W"],
                "total_subjects": 48,
                "sampling_timepoints": ["pre-dose", "1h", "4h", "24h", "day7", "day14", "day28", "day56"],
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.01,
                "uloq": 1000.0,
                "status": AnalysisStatus.IN_PROGRESS,
                "principal_investigator": "Dr. James Wilson",
                "start_date": now - timedelta(days=180),
                "completion_date": None,
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "PKS-003",
                "trial_id": DUPIXENT_TRIAL,
                "study_type": StudyType.PK_PD,
                "title": "Dupilumab PK/PD Relationship in Atopic Dermatitis",
                "description": "PK/PD modeling of dupilumab 300mg SC Q2W with EASI response",
                "target_analyte": "dupilumab",
                "matrix": SampleMatrix.SERUM,
                "dose_levels": ["200mg SC", "300mg SC"],
                "total_subjects": 96,
                "sampling_timepoints": ["pre-dose", "day1", "day3", "day7", "day14"],
                "bioanalytical_method": "ELISA (validated)",
                "lloq": 0.078,
                "uloq": 256.0,
                "status": AnalysisStatus.COMPLETED,
                "principal_investigator": "Dr. Maria Rodriguez",
                "start_date": now - timedelta(days=540),
                "completion_date": now - timedelta(days=360),
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "PKS-004",
                "trial_id": DUPIXENT_TRIAL,
                "study_type": StudyType.DOSE_ESCALATION,
                "title": "Dupilumab Dose Escalation in Pediatric Asthma",
                "description": "3+3 dose escalation study of dupilumab in pediatric patients",
                "target_analyte": "dupilumab",
                "matrix": SampleMatrix.PLASMA,
                "dose_levels": ["100mg SC", "200mg SC", "300mg SC", "400mg SC"],
                "total_subjects": 36,
                "sampling_timepoints": ["pre-dose", "2h", "8h", "24h", "day7", "day14"],
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.05,
                "uloq": 500.0,
                "status": AnalysisStatus.IN_PROGRESS,
                "principal_investigator": "Dr. Emily Park",
                "start_date": now - timedelta(days=120),
                "completion_date": None,
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "PKS-005",
                "trial_id": LIBTAYO_TRIAL,
                "study_type": StudyType.PK_SINGLE_DOSE,
                "title": "Cemiplimab Single-Dose PK in Advanced CSCC",
                "description": "First-in-human PK evaluation of cemiplimab 350mg IV Q3W",
                "target_analyte": "cemiplimab",
                "matrix": SampleMatrix.SERUM,
                "dose_levels": ["1mg/kg IV", "3mg/kg IV", "350mg IV"],
                "total_subjects": 30,
                "sampling_timepoints": ["0h", "EOI", "2h", "6h", "24h", "72h", "day7", "day14", "day21"],
                "bioanalytical_method": "ELISA (validated)",
                "lloq": 0.1,
                "uloq": 800.0,
                "status": AnalysisStatus.FINALIZED,
                "principal_investigator": "Dr. Michael Brooks",
                "start_date": now - timedelta(days=730),
                "completion_date": now - timedelta(days=600),
                "created_at": now - timedelta(days=750),
            },
            {
                "id": "PKS-006",
                "trial_id": LIBTAYO_TRIAL,
                "study_type": StudyType.DDI,
                "title": "Cemiplimab Drug-Drug Interaction with CYP3A4 Substrates",
                "description": "Evaluation of cemiplimab effect on midazolam PK",
                "target_analyte": "midazolam",
                "matrix": SampleMatrix.PLASMA,
                "dose_levels": ["350mg IV cemiplimab + 2mg midazolam PO"],
                "total_subjects": 20,
                "sampling_timepoints": ["0h", "0.5h", "1h", "2h", "4h", "6h", "8h", "12h", "24h"],
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.02,
                "uloq": 200.0,
                "status": AnalysisStatus.COMPLETED,
                "principal_investigator": "Dr. Robert Kim",
                "start_date": now - timedelta(days=300),
                "completion_date": now - timedelta(days=220),
                "created_at": now - timedelta(days=320),
            },
            {
                "id": "PKS-007",
                "trial_id": EYLEA_TRIAL,
                "study_type": StudyType.BIOEQUIVALENCE,
                "title": "Aflibercept Prefilled Syringe vs Vial Bioequivalence",
                "description": "2-period crossover BE study comparing PFS and vial presentations",
                "target_analyte": "aflibercept",
                "matrix": SampleMatrix.PLASMA,
                "dose_levels": ["2mg IVT (PFS)", "2mg IVT (Vial)"],
                "total_subjects": 60,
                "sampling_timepoints": ["0h", "1h", "2h", "4h", "8h", "24h", "48h", "168h"],
                "bioanalytical_method": "ELISA (validated)",
                "lloq": 0.05,
                "uloq": 500.0,
                "status": AnalysisStatus.UNDER_REVIEW,
                "principal_investigator": "Dr. Sarah Chen",
                "start_date": now - timedelta(days=90),
                "completion_date": now - timedelta(days=30),
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PKS-008",
                "trial_id": DUPIXENT_TRIAL,
                "study_type": StudyType.FOOD_EFFECT,
                "title": "Dupilumab SC Absorption with Food Effect Evaluation",
                "description": "Crossover study evaluating food effect on dupilumab SC bioavailability",
                "target_analyte": "dupilumab",
                "matrix": SampleMatrix.SERUM,
                "dose_levels": ["300mg SC (fasted)", "300mg SC (fed)"],
                "total_subjects": 32,
                "sampling_timepoints": ["0h", "2h", "4h", "8h", "12h", "24h", "48h", "72h", "168h"],
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.05,
                "uloq": 500.0,
                "status": AnalysisStatus.PLANNED,
                "principal_investigator": "Dr. Lisa Chang",
                "start_date": None,
                "completion_date": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "PKS-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_type": StudyType.SPECIAL_POPULATION,
                "title": "Cemiplimab PK in Hepatic Impairment",
                "description": "PK evaluation of cemiplimab in patients with mild/moderate hepatic impairment",
                "target_analyte": "cemiplimab",
                "matrix": SampleMatrix.SERUM,
                "dose_levels": ["350mg IV"],
                "total_subjects": 24,
                "sampling_timepoints": ["0h", "EOI", "4h", "24h", "day7", "day14", "day21"],
                "bioanalytical_method": "ELISA (validated)",
                "lloq": 0.1,
                "uloq": 800.0,
                "status": AnalysisStatus.IN_PROGRESS,
                "principal_investigator": "Dr. Michael Brooks",
                "start_date": now - timedelta(days=60),
                "completion_date": None,
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "PKS-010",
                "trial_id": EYLEA_TRIAL,
                "study_type": StudyType.DOSE_FINDING,
                "title": "Aflibercept HD Dose Finding in DME",
                "description": "Phase II dose-finding study for high-dose aflibercept in diabetic macular edema",
                "target_analyte": "aflibercept",
                "matrix": SampleMatrix.PLASMA,
                "dose_levels": ["2mg IVT", "4mg IVT", "8mg IVT"],
                "total_subjects": 72,
                "sampling_timepoints": ["pre-dose", "day1", "day7", "day14", "day28"],
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.01,
                "uloq": 1000.0,
                "status": AnalysisStatus.COMPLETED,
                "principal_investigator": "Dr. James Wilson",
                "start_date": now - timedelta(days=450),
                "completion_date": now - timedelta(days=300),
                "created_at": now - timedelta(days=480),
            },
            {
                "id": "PKS-011",
                "trial_id": DUPIXENT_TRIAL,
                "study_type": StudyType.PK_SINGLE_DOSE,
                "title": "Dupilumab Single-Dose PK in Japanese Subjects",
                "description": "Bridging PK study of dupilumab 300mg SC in Japanese healthy volunteers",
                "target_analyte": "dupilumab",
                "matrix": SampleMatrix.SERUM,
                "dose_levels": ["300mg SC"],
                "total_subjects": 20,
                "sampling_timepoints": ["0h", "6h", "24h", "day3", "day7", "day14", "day21", "day28"],
                "bioanalytical_method": "ELISA (validated)",
                "lloq": 0.078,
                "uloq": 256.0,
                "status": AnalysisStatus.FINALIZED,
                "principal_investigator": "Dr. Kenji Tanaka",
                "start_date": now - timedelta(days=500),
                "completion_date": now - timedelta(days=400),
                "created_at": now - timedelta(days=520),
            },
            {
                "id": "PKS-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_type": StudyType.PK_MULTIPLE_DOSE,
                "title": "Cemiplimab Multiple-Dose PK in NSCLC First-Line",
                "description": "Population PK analysis of cemiplimab 350mg IV Q3W in advanced NSCLC",
                "target_analyte": "cemiplimab",
                "matrix": SampleMatrix.SERUM,
                "dose_levels": ["350mg IV Q3W"],
                "total_subjects": 150,
                "sampling_timepoints": ["pre-dose C1", "EOI C1", "pre-dose C2", "pre-dose C4", "pre-dose C8"],
                "bioanalytical_method": "ELISA (validated)",
                "lloq": 0.1,
                "uloq": 800.0,
                "status": AnalysisStatus.IN_PROGRESS,
                "principal_investigator": "Dr. Anna Martinez",
                "start_date": now - timedelta(days=210),
                "completion_date": None,
                "created_at": now - timedelta(days=240),
            },
        ]

        for s in studies_data:
            self._studies[s["id"]] = PKStudy(**s)

        # --- 15 PK Samples ---
        samples_data = [
            {"id": "PKSMP-001", "study_id": "PKS-001", "subject_id": "SUBJ-001", "timepoint": "0h", "nominal_time_hours": 0.0, "actual_time_hours": 0.0, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.REPORTED, "concentration": 0.0, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=350), "analysis_date": now - timedelta(days=340), "qc_passed": True, "notes": None},
            {"id": "PKSMP-002", "study_id": "PKS-001", "subject_id": "SUBJ-001", "timepoint": "1h", "nominal_time_hours": 1.0, "actual_time_hours": 1.05, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.REPORTED, "concentration": 45.2, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=350), "analysis_date": now - timedelta(days=340), "qc_passed": True, "notes": None},
            {"id": "PKSMP-003", "study_id": "PKS-001", "subject_id": "SUBJ-001", "timepoint": "4h", "nominal_time_hours": 4.0, "actual_time_hours": 4.1, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.ANALYZED, "concentration": 128.5, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=350), "analysis_date": now - timedelta(days=340), "qc_passed": True, "notes": None},
            {"id": "PKSMP-004", "study_id": "PKS-001", "subject_id": "SUBJ-002", "timepoint": "0h", "nominal_time_hours": 0.0, "actual_time_hours": 0.0, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.ANALYZED, "concentration": 0.0, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=349), "analysis_date": now - timedelta(days=339), "qc_passed": True, "notes": None},
            {"id": "PKSMP-005", "study_id": "PKS-002", "subject_id": "SUBJ-010", "timepoint": "pre-dose", "nominal_time_hours": 0.0, "actual_time_hours": 0.0, "matrix": SampleMatrix.SERUM, "status": SampleStatus.COLLECTED, "concentration": None, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=30), "analysis_date": None, "qc_passed": None, "notes": None},
            {"id": "PKSMP-006", "study_id": "PKS-002", "subject_id": "SUBJ-010", "timepoint": "1h", "nominal_time_hours": 1.0, "actual_time_hours": 0.95, "matrix": SampleMatrix.SERUM, "status": SampleStatus.IN_TRANSIT, "concentration": None, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=30), "analysis_date": None, "qc_passed": None, "notes": "Shipped via cold chain"},
            {"id": "PKSMP-007", "study_id": "PKS-003", "subject_id": "SUBJ-020", "timepoint": "pre-dose", "nominal_time_hours": 0.0, "actual_time_hours": 0.0, "matrix": SampleMatrix.SERUM, "status": SampleStatus.REPORTED, "concentration": 0.0, "concentration_unit": "ug/mL", "collection_date": now - timedelta(days=500), "analysis_date": now - timedelta(days=480), "qc_passed": True, "notes": None},
            {"id": "PKSMP-008", "study_id": "PKS-003", "subject_id": "SUBJ-020", "timepoint": "day7", "nominal_time_hours": 168.0, "actual_time_hours": 170.0, "matrix": SampleMatrix.SERUM, "status": SampleStatus.REPORTED, "concentration": 85.3, "concentration_unit": "ug/mL", "collection_date": now - timedelta(days=493), "analysis_date": now - timedelta(days=475), "qc_passed": True, "notes": None},
            {"id": "PKSMP-009", "study_id": "PKS-005", "subject_id": "SUBJ-030", "timepoint": "EOI", "nominal_time_hours": 1.5, "actual_time_hours": 1.6, "matrix": SampleMatrix.SERUM, "status": SampleStatus.REPORTED, "concentration": 320.4, "concentration_unit": "ug/mL", "collection_date": now - timedelta(days=700), "analysis_date": now - timedelta(days=680), "qc_passed": True, "notes": None},
            {"id": "PKSMP-010", "study_id": "PKS-005", "subject_id": "SUBJ-031", "timepoint": "day14", "nominal_time_hours": 336.0, "actual_time_hours": 338.0, "matrix": SampleMatrix.SERUM, "status": SampleStatus.FAILED_QC, "concentration": None, "concentration_unit": "ug/mL", "collection_date": now - timedelta(days=686), "analysis_date": now - timedelta(days=670), "qc_passed": False, "notes": "Sample hemolyzed; reanalysis required"},
            {"id": "PKSMP-011", "study_id": "PKS-006", "subject_id": "SUBJ-040", "timepoint": "2h", "nominal_time_hours": 2.0, "actual_time_hours": 2.1, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.ANALYZED, "concentration": 15.7, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=280), "analysis_date": now - timedelta(days=260), "qc_passed": True, "notes": None},
            {"id": "PKSMP-012", "study_id": "PKS-007", "subject_id": "SUBJ-050", "timepoint": "0h", "nominal_time_hours": 0.0, "actual_time_hours": 0.0, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.RECEIVED_AT_LAB, "concentration": None, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=60), "analysis_date": None, "qc_passed": None, "notes": None},
            {"id": "PKSMP-013", "study_id": "PKS-004", "subject_id": "SUBJ-060", "timepoint": "pre-dose", "nominal_time_hours": 0.0, "actual_time_hours": 0.0, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.SCHEDULED, "concentration": None, "concentration_unit": "ng/mL", "collection_date": None, "analysis_date": None, "qc_passed": None, "notes": "Scheduled for next visit"},
            {"id": "PKSMP-014", "study_id": "PKS-010", "subject_id": "SUBJ-070", "timepoint": "day28", "nominal_time_hours": 672.0, "actual_time_hours": 675.0, "matrix": SampleMatrix.PLASMA, "status": SampleStatus.REPORTED, "concentration": 2.1, "concentration_unit": "ng/mL", "collection_date": now - timedelta(days=330), "analysis_date": now - timedelta(days=310), "qc_passed": True, "notes": None},
            {"id": "PKSMP-015", "study_id": "PKS-012", "subject_id": "SUBJ-080", "timepoint": "pre-dose C1", "nominal_time_hours": 0.0, "actual_time_hours": 0.0, "matrix": SampleMatrix.SERUM, "status": SampleStatus.ANALYZED, "concentration": 0.0, "concentration_unit": "ug/mL", "collection_date": now - timedelta(days=200), "analysis_date": now - timedelta(days=185), "qc_passed": True, "notes": None},
        ]

        for s in samples_data:
            self._samples[s["id"]] = PKSample(**s)

        # --- 12 Dose Escalations ---
        escalations_data = [
            {"id": "ESC-001", "study_id": "PKS-004", "cohort_number": 1, "dose_level": "100mg SC", "subjects_enrolled": 6, "subjects_evaluable": 6, "dlts_observed": 0, "dlt_descriptions": [], "decision": EscalationDecision.ESCALATE, "decision_date": now - timedelta(days=105), "decision_rationale": "No DLTs in cohort 1. Safe to escalate per 3+3 design.", "pk_summary": "Cmax 12.3 ug/mL, AUC 450 ug*h/mL", "safety_summary": "No SAEs. 2 mild injection site reactions.", "decided_by": "Dr. Emily Park"},
            {"id": "ESC-002", "study_id": "PKS-004", "cohort_number": 2, "dose_level": "200mg SC", "subjects_enrolled": 6, "subjects_evaluable": 6, "dlts_observed": 0, "dlt_descriptions": [], "decision": EscalationDecision.ESCALATE, "decision_date": now - timedelta(days=75), "decision_rationale": "No DLTs in cohort 2. PK exposure proportional.", "pk_summary": "Cmax 24.8 ug/mL, AUC 920 ug*h/mL", "safety_summary": "No SAEs. 1 grade 2 injection site reaction.", "decided_by": "Dr. Emily Park"},
            {"id": "ESC-003", "study_id": "PKS-004", "cohort_number": 3, "dose_level": "300mg SC", "subjects_enrolled": 6, "subjects_evaluable": 5, "dlts_observed": 1, "dlt_descriptions": ["Grade 3 transaminase elevation"], "decision": EscalationDecision.EXPAND_COHORT, "decision_date": now - timedelta(days=45), "decision_rationale": "1/6 DLT observed. Expanding cohort to 6 additional subjects per protocol.", "pk_summary": "Cmax 35.1 ug/mL, AUC 1380 ug*h/mL", "safety_summary": "1 DLT (grade 3 ALT elevation). Resolved with dose hold.", "decided_by": "Dr. Emily Park"},
            {"id": "ESC-004", "study_id": "PKS-004", "cohort_number": 3, "dose_level": "300mg SC (expansion)", "subjects_enrolled": 6, "subjects_evaluable": 4, "dlts_observed": 0, "dlt_descriptions": [], "decision": None, "decision_date": None, "decision_rationale": None, "pk_summary": None, "safety_summary": None, "decided_by": None},
            {"id": "ESC-005", "study_id": "PKS-005", "cohort_number": 1, "dose_level": "1mg/kg IV", "subjects_enrolled": 3, "subjects_evaluable": 3, "dlts_observed": 0, "dlt_descriptions": [], "decision": EscalationDecision.ESCALATE, "decision_date": now - timedelta(days=700), "decision_rationale": "No DLTs. Accelerated titration.", "pk_summary": "Cmax 25 ug/mL, t1/2 14 days", "safety_summary": "No treatment-related AEs.", "decided_by": "Dr. Michael Brooks"},
            {"id": "ESC-006", "study_id": "PKS-005", "cohort_number": 2, "dose_level": "3mg/kg IV", "subjects_enrolled": 6, "subjects_evaluable": 6, "dlts_observed": 0, "dlt_descriptions": [], "decision": EscalationDecision.ESCALATE, "decision_date": now - timedelta(days=660), "decision_rationale": "No DLTs. Target exposure achieved.", "pk_summary": "Cmax 78 ug/mL, t1/2 16 days", "safety_summary": "1 grade 2 infusion reaction. No SAEs.", "decided_by": "Dr. Michael Brooks"},
            {"id": "ESC-007", "study_id": "PKS-005", "cohort_number": 3, "dose_level": "350mg IV (flat dose)", "subjects_enrolled": 10, "subjects_evaluable": 10, "dlts_observed": 1, "dlt_descriptions": ["Grade 3 pneumonitis"], "decision": EscalationDecision.MAINTAIN, "decision_date": now - timedelta(days=620), "decision_rationale": "350mg flat dose selected as recommended phase 2 dose (RP2D).", "pk_summary": "Cmax 95 ug/mL, AUC 15000 ug*h/mL, t1/2 19 days", "safety_summary": "1 DLT pneumonitis (resolved). Favorable benefit-risk.", "decided_by": "Dr. Michael Brooks"},
            {"id": "ESC-008", "study_id": "PKS-010", "cohort_number": 1, "dose_level": "2mg IVT", "subjects_enrolled": 24, "subjects_evaluable": 24, "dlts_observed": 0, "dlt_descriptions": [], "decision": EscalationDecision.ESCALATE, "decision_date": now - timedelta(days=420), "decision_rationale": "Current approved dose. Safe to evaluate higher doses.", "pk_summary": "Systemic Cmax 0.8 ng/mL", "safety_summary": "No unexpected safety findings.", "decided_by": "Dr. James Wilson"},
            {"id": "ESC-009", "study_id": "PKS-010", "cohort_number": 2, "dose_level": "4mg IVT", "subjects_enrolled": 24, "subjects_evaluable": 23, "dlts_observed": 0, "dlt_descriptions": [], "decision": EscalationDecision.ESCALATE, "decision_date": now - timedelta(days=380), "decision_rationale": "Good tolerability. Dose-proportional systemic exposure.", "pk_summary": "Systemic Cmax 1.5 ng/mL", "safety_summary": "No dose-limiting ocular events.", "decided_by": "Dr. James Wilson"},
            {"id": "ESC-010", "study_id": "PKS-010", "cohort_number": 3, "dose_level": "8mg IVT", "subjects_enrolled": 24, "subjects_evaluable": 22, "dlts_observed": 2, "dlt_descriptions": ["Transient IOP elevation >30mmHg", "Grade 3 vitreal hemorrhage"], "decision": EscalationDecision.DE_ESCALATE, "decision_date": now - timedelta(days=340), "decision_rationale": "2 DLTs at 8mg. MTD exceeded. Recommended dose: 4mg IVT.", "pk_summary": "Systemic Cmax 3.2 ng/mL", "safety_summary": "2 DLTs. 8mg IVT exceeds MTD.", "decided_by": "Dr. James Wilson"},
            {"id": "ESC-011", "study_id": "PKS-012", "cohort_number": 1, "dose_level": "350mg IV Q3W", "subjects_enrolled": 50, "subjects_evaluable": 48, "dlts_observed": 2, "dlt_descriptions": ["Grade 3 immune-related hepatitis", "Grade 4 colitis"], "decision": EscalationDecision.MAINTAIN, "decision_date": now - timedelta(days=180), "decision_rationale": "Known immune-related toxicities consistent with anti-PD-1 class.", "pk_summary": "Steady-state trough 55 ug/mL", "safety_summary": "2 irAEs managed per protocol. Acceptable safety profile.", "decided_by": "Dr. Anna Martinez"},
            {"id": "ESC-012", "study_id": "PKS-009", "cohort_number": 1, "dose_level": "350mg IV", "subjects_enrolled": 8, "subjects_evaluable": 6, "dlts_observed": 0, "dlt_descriptions": [], "decision": None, "decision_date": None, "decision_rationale": None, "pk_summary": None, "safety_summary": None, "decided_by": None},
        ]

        for e in escalations_data:
            self._escalations[e["id"]] = DoseEscalation(**e)

        # --- 10 Exposure-Response Analyses ---
        er_data = [
            {"id": "ER-001", "study_id": "PKS-003", "analysis_type": "exposure-efficacy", "endpoint": "EASI-75 response at Week 16", "model_type": "logistic_regression", "pk_parameter": "AUCtau_ss", "correlation_coefficient": 0.72, "p_value": 0.001, "ec50": 45.0, "emax": 0.85, "therapeutic_window_low": 30.0, "therapeutic_window_high": 120.0, "status": AnalysisStatus.FINALIZED, "analyst": "Dr. Jennifer Liu", "analysis_date": now - timedelta(days=350), "report_reference": "RPT-ER-003-FINAL"},
            {"id": "ER-002", "study_id": "PKS-003", "analysis_type": "exposure-safety", "endpoint": "Injection site reaction incidence", "model_type": "logistic_regression", "pk_parameter": "Cmax", "correlation_coefficient": 0.45, "p_value": 0.023, "ec50": None, "emax": None, "therapeutic_window_low": None, "therapeutic_window_high": None, "status": AnalysisStatus.FINALIZED, "analyst": "Dr. Jennifer Liu", "analysis_date": now - timedelta(days=345), "report_reference": "RPT-ER-003-SAFETY"},
            {"id": "ER-003", "study_id": "PKS-001", "analysis_type": "exposure-efficacy", "endpoint": "BCVA change from baseline at Month 12", "model_type": "emax_model", "pk_parameter": "AUC0-inf", "correlation_coefficient": 0.68, "p_value": 0.003, "ec50": 2500.0, "emax": 15.2, "therapeutic_window_low": 1500.0, "therapeutic_window_high": 8000.0, "status": AnalysisStatus.COMPLETED, "analyst": "Dr. David Park", "analysis_date": now - timedelta(days=260), "report_reference": "RPT-ER-001-V2"},
            {"id": "ER-004", "study_id": "PKS-005", "analysis_type": "exposure-efficacy", "endpoint": "Objective response rate (ORR)", "model_type": "logistic_regression", "pk_parameter": "Ctrough_ss", "correlation_coefficient": 0.58, "p_value": 0.008, "ec50": 40.0, "emax": 0.65, "therapeutic_window_low": 25.0, "therapeutic_window_high": 200.0, "status": AnalysisStatus.FINALIZED, "analyst": "Dr. Rachel Greene", "analysis_date": now - timedelta(days=580), "report_reference": "RPT-ER-005-FINAL"},
            {"id": "ER-005", "study_id": "PKS-005", "analysis_type": "exposure-safety", "endpoint": "Grade 3+ irAE incidence", "model_type": "cox_proportional_hazards", "pk_parameter": "AUCtau_ss", "correlation_coefficient": 0.35, "p_value": 0.045, "ec50": None, "emax": None, "therapeutic_window_low": None, "therapeutic_window_high": None, "status": AnalysisStatus.COMPLETED, "analyst": "Dr. Rachel Greene", "analysis_date": now - timedelta(days=570), "report_reference": "RPT-ER-005-SAFETY"},
            {"id": "ER-006", "study_id": "PKS-010", "analysis_type": "exposure-efficacy", "endpoint": "Central retinal thickness reduction at Week 48", "model_type": "linear_regression", "pk_parameter": "Cavg", "correlation_coefficient": 0.61, "p_value": 0.005, "ec50": None, "emax": None, "therapeutic_window_low": 0.5, "therapeutic_window_high": 3.0, "status": AnalysisStatus.COMPLETED, "analyst": "Dr. David Park", "analysis_date": now - timedelta(days=290), "report_reference": "RPT-ER-010-V1"},
            {"id": "ER-007", "study_id": "PKS-012", "analysis_type": "exposure-efficacy", "endpoint": "Progression-free survival", "model_type": "cox_proportional_hazards", "pk_parameter": "Ctrough_ss", "correlation_coefficient": 0.52, "p_value": 0.012, "ec50": 35.0, "emax": None, "therapeutic_window_low": 20.0, "therapeutic_window_high": 150.0, "status": AnalysisStatus.IN_PROGRESS, "analyst": "Dr. Rachel Greene", "analysis_date": None, "report_reference": None},
            {"id": "ER-008", "study_id": "PKS-002", "analysis_type": "exposure-efficacy", "endpoint": "BCVA improvement >= 15 letters", "model_type": "emax_model", "pk_parameter": "AUCtau_ss", "correlation_coefficient": None, "p_value": None, "ec50": None, "emax": None, "therapeutic_window_low": None, "therapeutic_window_high": None, "status": AnalysisStatus.PLANNED, "analyst": "Dr. David Park", "analysis_date": None, "report_reference": None},
            {"id": "ER-009", "study_id": "PKS-004", "analysis_type": "exposure-safety", "endpoint": "Hepatotoxicity risk", "model_type": "logistic_regression", "pk_parameter": "Cmax", "correlation_coefficient": None, "p_value": None, "ec50": None, "emax": None, "therapeutic_window_low": None, "therapeutic_window_high": None, "status": AnalysisStatus.IN_PROGRESS, "analyst": "Dr. Jennifer Liu", "analysis_date": None, "report_reference": None},
            {"id": "ER-010", "study_id": "PKS-011", "analysis_type": "exposure-efficacy", "endpoint": "AUC comparison Japanese vs Western subjects", "model_type": "linear_regression", "pk_parameter": "AUC0-inf", "correlation_coefficient": 0.91, "p_value": 0.0001, "ec50": None, "emax": None, "therapeutic_window_low": None, "therapeutic_window_high": None, "status": AnalysisStatus.FINALIZED, "analyst": "Dr. Kenji Tanaka", "analysis_date": now - timedelta(days=390), "report_reference": "RPT-ER-011-BRIDGE"},
        ]

        for e in er_data:
            self._exposure_analyses[e["id"]] = ExposureResponse(**e)

        # --- 12 DDI Assessments ---
        ddi_data = [
            {"id": "DDI-001", "trial_id": LIBTAYO_TRIAL, "perpetrator_drug": "Cemiplimab", "victim_drug": "Midazolam (CYP3A4 substrate)", "interaction_mechanism": "CYP3A4 inhibition via IL-6 suppression", "in_vitro_result": "No direct CYP3A4 inhibition in vitro", "clinical_result": "Midazolam AUC ratio 1.08 (90% CI: 0.92-1.27)", "auc_ratio": 1.08, "cmax_ratio": 1.05, "risk_classification": DDIRisk.NONE, "recommendation": "No dose adjustment required for CYP3A4 substrates.", "assessed_by": "Dr. Robert Kim", "assessment_date": now - timedelta(days=200), "references": ["FDA DDI Guidance 2020", "Study PKS-006 CSR"]},
            {"id": "DDI-002", "trial_id": LIBTAYO_TRIAL, "perpetrator_drug": "Cemiplimab", "victim_drug": "Warfarin (CYP2C9 substrate)", "interaction_mechanism": "CYP2C9 modulation via immune checkpoint inhibition", "in_vitro_result": "No direct CYP2C9 inhibition", "clinical_result": "Theoretical risk; no clinical data", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.LOW, "recommendation": "Monitor INR closely when co-administered with warfarin.", "assessed_by": "Dr. Robert Kim", "assessment_date": now - timedelta(days=195), "references": ["FDA DDI Guidance 2020", "Anti-PD-1 Class Label Review"]},
            {"id": "DDI-003", "trial_id": DUPIXENT_TRIAL, "perpetrator_drug": "Dupilumab", "victim_drug": "CYP substrates (general)", "interaction_mechanism": "IL-4/IL-13 pathway modulation affecting CYP expression", "in_vitro_result": "IL-4 suppresses CYP1A2, CYP3A4 in hepatocytes", "clinical_result": "No clinically significant changes in CYP substrate levels", "auc_ratio": 1.02, "cmax_ratio": 1.01, "risk_classification": DDIRisk.NONE, "recommendation": "No dose adjustments required for CYP substrates.", "assessed_by": "Dr. Lisa Chang", "assessment_date": now - timedelta(days=400), "references": ["Dupixent USPI", "Phase 1 DDI Study Report"]},
            {"id": "DDI-004", "trial_id": DUPIXENT_TRIAL, "perpetrator_drug": "Cyclosporine", "victim_drug": "Dupilumab", "interaction_mechanism": "Immunosuppressant co-administration", "in_vitro_result": "N/A - biologic interaction", "clinical_result": "No PK interaction observed", "auc_ratio": 0.98, "cmax_ratio": 0.97, "risk_classification": DDIRisk.LOW, "recommendation": "Can be co-administered. Monitor for additive immunosuppression.", "assessed_by": "Dr. Lisa Chang", "assessment_date": now - timedelta(days=390), "references": ["Dupixent USPI Section 7"]},
            {"id": "DDI-005", "trial_id": EYLEA_TRIAL, "perpetrator_drug": "Aflibercept (systemic)", "victim_drug": "CYP substrates", "interaction_mechanism": "VEGF trap - minimal systemic exposure after IVT", "in_vitro_result": "N/A - negligible systemic levels", "clinical_result": "No systemic DDI expected due to route of administration", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.NONE, "recommendation": "No systemic DDI concerns for IVT aflibercept.", "assessed_by": "Dr. Sarah Chen", "assessment_date": now - timedelta(days=350), "references": ["EYLEA USPI", "Population PK Analysis"]},
            {"id": "DDI-006", "trial_id": LIBTAYO_TRIAL, "perpetrator_drug": "Cemiplimab", "victim_drug": "Corticosteroids (high-dose)", "interaction_mechanism": "Immunosuppressive effect may reduce anti-tumor efficacy", "in_vitro_result": "N/A - pharmacodynamic interaction", "clinical_result": "Prednisone >10mg/day associated with reduced ORR", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.HIGH, "recommendation": "Avoid systemic corticosteroids >10mg prednisone equivalent at baseline. Permitted for irAE management.", "assessed_by": "Dr. Michael Brooks", "assessment_date": now - timedelta(days=580), "references": ["LIBTAYO USPI", "Arbour et al. Ann Oncol 2018"]},
            {"id": "DDI-007", "trial_id": LIBTAYO_TRIAL, "perpetrator_drug": "Cemiplimab", "victim_drug": "Live vaccines", "interaction_mechanism": "Immune checkpoint inhibition may enhance vaccine response unpredictably", "in_vitro_result": "N/A", "clinical_result": "Theoretical risk of uncontrolled immune activation", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.CONTRAINDICATED, "recommendation": "Live vaccines are contraindicated during cemiplimab treatment.", "assessed_by": "Dr. Michael Brooks", "assessment_date": now - timedelta(days=575), "references": ["LIBTAYO USPI Section 5.7", "NCCN Guidelines"]},
            {"id": "DDI-008", "trial_id": DUPIXENT_TRIAL, "perpetrator_drug": "Dupilumab", "victim_drug": "Live vaccines", "interaction_mechanism": "IL-4/IL-13 blockade may affect vaccine immunogenicity", "in_vitro_result": "N/A", "clinical_result": "Inactivated vaccines safe; live vaccine data limited", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.MODERATE, "recommendation": "Avoid live vaccines during treatment. Inactivated vaccines are acceptable.", "assessed_by": "Dr. Maria Rodriguez", "assessment_date": now - timedelta(days=380), "references": ["Dupixent USPI", "ACIP Immunocompromised Guidelines"]},
            {"id": "DDI-009", "trial_id": EYLEA_TRIAL, "perpetrator_drug": "Ranibizumab (prior therapy)", "victim_drug": "Aflibercept", "interaction_mechanism": "Sequential anti-VEGF therapy; potential for residual VEGF binding", "in_vitro_result": "N/A", "clinical_result": "4-week washout sufficient to avoid interaction", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.LOW, "recommendation": "Minimum 4-week washout from prior anti-VEGF before switching to aflibercept.", "assessed_by": "Dr. Sarah Chen", "assessment_date": now - timedelta(days=340), "references": ["EYLEA USPI", "CATT Trial Substudy"]},
            {"id": "DDI-010", "trial_id": LIBTAYO_TRIAL, "perpetrator_drug": "Platinum chemotherapy", "victim_drug": "Cemiplimab", "interaction_mechanism": "Chemotherapy-induced lymphodepletion may enhance checkpoint blockade", "in_vitro_result": "N/A - PD interaction", "clinical_result": "Combination well-tolerated in NSCLC; enhanced efficacy observed", "auc_ratio": 1.0, "cmax_ratio": 1.0, "risk_classification": DDIRisk.LOW, "recommendation": "Combination permitted per protocol. Monitor for enhanced immune toxicity.", "assessed_by": "Dr. Anna Martinez", "assessment_date": now - timedelta(days=190), "references": ["EMPOWER-Lung 3 Protocol", "KEYNOTE-189 Reference"]},
            {"id": "DDI-011", "trial_id": DUPIXENT_TRIAL, "perpetrator_drug": "Topical corticosteroids", "victim_drug": "Dupilumab", "interaction_mechanism": "No pharmacokinetic interaction expected (topical vs systemic)", "in_vitro_result": "N/A", "clinical_result": "Combination is standard of care; no PK interaction", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.NONE, "recommendation": "Topical corticosteroids can be used concomitantly as rescue therapy.", "assessed_by": "Dr. Maria Rodriguez", "assessment_date": now - timedelta(days=370), "references": ["Dupixent USPI", "SOLO 1 & 2 Study Protocols"]},
            {"id": "DDI-012", "trial_id": EYLEA_TRIAL, "perpetrator_drug": "Aflibercept (IVT)", "victim_drug": "Systemic anti-coagulants", "interaction_mechanism": "IVT injection procedure risk with anticoagulation", "in_vitro_result": "N/A - procedural interaction", "clinical_result": "Slight increase in vitreous hemorrhage risk with concurrent anticoagulants", "auc_ratio": None, "cmax_ratio": None, "risk_classification": DDIRisk.MODERATE, "recommendation": "Caution with IVT injection in anticoagulated patients. Consider holding anticoagulants per ophthalmology guidelines.", "assessed_by": "Dr. James Wilson", "assessment_date": now - timedelta(days=330), "references": ["EYLEA USPI", "AAO IVT Injection Guidelines"]},
        ]

        for d in ddi_data:
            self._ddi_assessments[d["id"]] = DDIAssessment(**d)

    # ------------------------------------------------------------------
    # PK Studies CRUD
    # ------------------------------------------------------------------

    def list_studies(
        self,
        *,
        trial_id: str | None = None,
        study_type: StudyType | None = None,
        status: AnalysisStatus | None = None,
    ) -> list[PKStudy]:
        """List PK studies with optional filters."""
        with self._lock:
            result = list(self._studies.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if study_type is not None:
            result = [s for s in result if s.study_type == study_type]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.id)

    def get_study(self, study_id: str) -> PKStudy | None:
        """Get a single PK study by ID."""
        with self._lock:
            return self._studies.get(study_id)

    def create_study(self, payload: PKStudyCreate) -> PKStudy:
        """Create a new PK study."""
        now = datetime.now(timezone.utc)
        study_id = f"PKS-{uuid4().hex[:8].upper()}"
        study = PKStudy(
            id=study_id,
            **payload.model_dump(),
            status=AnalysisStatus.PLANNED,
            start_date=None,
            completion_date=None,
            created_at=now,
        )
        with self._lock:
            self._studies[study_id] = study
        logger.info("Created PK study %s: %s", study_id, payload.title)
        return study

    def update_study(self, study_id: str, payload: PKStudyUpdate) -> PKStudy | None:
        """Update an existing PK study."""
        with self._lock:
            existing = self._studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PKStudy(**data)
            self._studies[study_id] = updated
        return updated

    def delete_study(self, study_id: str) -> bool:
        """Delete a PK study. Returns True if deleted, False if not found."""
        with self._lock:
            if study_id in self._studies:
                del self._studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # PK Samples CRUD
    # ------------------------------------------------------------------

    def list_samples(
        self,
        *,
        study_id: str | None = None,
        matrix: SampleMatrix | None = None,
        sample_status: SampleStatus | None = None,
    ) -> list[PKSample]:
        """List PK samples with optional filters."""
        with self._lock:
            result = list(self._samples.values())

        if study_id is not None:
            result = [s for s in result if s.study_id == study_id]
        if matrix is not None:
            result = [s for s in result if s.matrix == matrix]
        if sample_status is not None:
            result = [s for s in result if s.status == sample_status]

        return sorted(result, key=lambda s: s.id)

    def get_sample(self, sample_id: str) -> PKSample | None:
        """Get a single PK sample by ID."""
        with self._lock:
            return self._samples.get(sample_id)

    def create_sample(self, payload: PKSampleCreate) -> PKSample:
        """Create a new PK sample. Validates that the study_id exists."""
        with self._lock:
            if payload.study_id not in self._studies:
                raise ValueError(f"Study '{payload.study_id}' not found")

        sample_id = f"PKSMP-{uuid4().hex[:8].upper()}"
        sample = PKSample(
            id=sample_id,
            **payload.model_dump(),
            status=SampleStatus.SCHEDULED,
            actual_time_hours=None,
            concentration=None,
            concentration_unit="ng/mL",
            collection_date=None,
            analysis_date=None,
            qc_passed=None,
            notes=None,
        )
        with self._lock:
            self._samples[sample_id] = sample
        logger.info("Created PK sample %s for study %s", sample_id, payload.study_id)
        return sample

    def update_sample(self, sample_id: str, payload: PKSampleUpdate) -> PKSample | None:
        """Update an existing PK sample."""
        with self._lock:
            existing = self._samples.get(sample_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set dates based on status transitions
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = SampleStatus(new_status)
                if new_status == SampleStatus.COLLECTED and existing.status == SampleStatus.SCHEDULED:
                    data["collection_date"] = datetime.now(timezone.utc)
                elif new_status == SampleStatus.ANALYZED and existing.status != SampleStatus.ANALYZED:
                    data["analysis_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = PKSample(**data)
            self._samples[sample_id] = updated
        return updated

    def delete_sample(self, sample_id: str) -> bool:
        """Delete a PK sample. Returns True if deleted, False if not found."""
        with self._lock:
            if sample_id in self._samples:
                del self._samples[sample_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Dose Escalations CRUD
    # ------------------------------------------------------------------

    def list_escalations(
        self,
        *,
        study_id: str | None = None,
        decision: EscalationDecision | None = None,
    ) -> list[DoseEscalation]:
        """List dose escalations with optional filters."""
        with self._lock:
            result = list(self._escalations.values())

        if study_id is not None:
            result = [e for e in result if e.study_id == study_id]
        if decision is not None:
            result = [e for e in result if e.decision == decision]

        return sorted(result, key=lambda e: e.id)

    def get_escalation(self, escalation_id: str) -> DoseEscalation | None:
        """Get a single dose escalation by ID."""
        with self._lock:
            return self._escalations.get(escalation_id)

    def create_escalation(self, payload: DoseEscalationCreate) -> DoseEscalation:
        """Create a new dose escalation. Validates that the study_id exists."""
        with self._lock:
            if payload.study_id not in self._studies:
                raise ValueError(f"Study '{payload.study_id}' not found")

        escalation_id = f"ESC-{uuid4().hex[:8].upper()}"
        escalation = DoseEscalation(
            id=escalation_id,
            **payload.model_dump(),
            subjects_evaluable=0,
            dlts_observed=0,
            dlt_descriptions=[],
            decision=None,
            decision_date=None,
            decision_rationale=None,
            pk_summary=None,
            safety_summary=None,
            decided_by=None,
        )
        with self._lock:
            self._escalations[escalation_id] = escalation
        logger.info("Created dose escalation %s for study %s", escalation_id, payload.study_id)
        return escalation

    def update_escalation(self, escalation_id: str, payload: DoseEscalationUpdate) -> DoseEscalation | None:
        """Update an existing dose escalation."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._escalations.get(escalation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set decision_date when decision is made
            if "decision" in updates and existing.decision is None:
                data["decision_date"] = now
            data.update(updates)
            updated = DoseEscalation(**data)
            self._escalations[escalation_id] = updated
        return updated

    def delete_escalation(self, escalation_id: str) -> bool:
        """Delete a dose escalation. Returns True if deleted, False if not found."""
        with self._lock:
            if escalation_id in self._escalations:
                del self._escalations[escalation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Exposure-Response Analyses CRUD
    # ------------------------------------------------------------------

    def list_exposure_analyses(
        self,
        *,
        study_id: str | None = None,
        status: AnalysisStatus | None = None,
    ) -> list[ExposureResponse]:
        """List exposure-response analyses with optional filters."""
        with self._lock:
            result = list(self._exposure_analyses.values())

        if study_id is not None:
            result = [e for e in result if e.study_id == study_id]
        if status is not None:
            result = [e for e in result if e.status == status]

        return sorted(result, key=lambda e: e.id)

    def get_exposure_analysis(self, analysis_id: str) -> ExposureResponse | None:
        """Get a single exposure-response analysis by ID."""
        with self._lock:
            return self._exposure_analyses.get(analysis_id)

    def create_exposure_analysis(self, payload: ExposureResponseCreate) -> ExposureResponse:
        """Create a new exposure-response analysis."""
        analysis_id = f"ER-{uuid4().hex[:8].upper()}"
        analysis = ExposureResponse(
            id=analysis_id,
            **payload.model_dump(),
            correlation_coefficient=None,
            p_value=None,
            ec50=None,
            emax=None,
            therapeutic_window_low=None,
            therapeutic_window_high=None,
            status=AnalysisStatus.PLANNED,
            analysis_date=None,
            report_reference=None,
        )
        with self._lock:
            self._exposure_analyses[analysis_id] = analysis
        logger.info("Created exposure-response analysis %s", analysis_id)
        return analysis

    def update_exposure_analysis(self, analysis_id: str, payload: ExposureResponseUpdate) -> ExposureResponse | None:
        """Update an existing exposure-response analysis."""
        with self._lock:
            existing = self._exposure_analyses.get(analysis_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set analysis_date when status moves to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = AnalysisStatus(new_status)
                if new_status == AnalysisStatus.COMPLETED and existing.status in (AnalysisStatus.PLANNED, AnalysisStatus.IN_PROGRESS):
                    data["analysis_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = ExposureResponse(**data)
            self._exposure_analyses[analysis_id] = updated
        return updated

    def delete_exposure_analysis(self, analysis_id: str) -> bool:
        """Delete an exposure-response analysis. Returns True if deleted."""
        with self._lock:
            if analysis_id in self._exposure_analyses:
                del self._exposure_analyses[analysis_id]
                return True
            return False

    # ------------------------------------------------------------------
    # DDI Assessments CRUD
    # ------------------------------------------------------------------

    def list_ddi_assessments(
        self,
        *,
        trial_id: str | None = None,
        risk_classification: DDIRisk | None = None,
    ) -> list[DDIAssessment]:
        """List DDI assessments with optional filters."""
        with self._lock:
            result = list(self._ddi_assessments.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if risk_classification is not None:
            result = [d for d in result if d.risk_classification == risk_classification]

        return sorted(result, key=lambda d: d.id)

    def get_ddi_assessment(self, assessment_id: str) -> DDIAssessment | None:
        """Get a single DDI assessment by ID."""
        with self._lock:
            return self._ddi_assessments.get(assessment_id)

    def create_ddi_assessment(self, payload: DDIAssessmentCreate) -> DDIAssessment:
        """Create a new DDI assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"DDI-{uuid4().hex[:8].upper()}"
        assessment = DDIAssessment(
            id=assessment_id,
            **payload.model_dump(),
            in_vitro_result=None,
            clinical_result=None,
            auc_ratio=None,
            cmax_ratio=None,
            assessment_date=now,
        )
        with self._lock:
            self._ddi_assessments[assessment_id] = assessment
        logger.info("Created DDI assessment %s", assessment_id)
        return assessment

    def update_ddi_assessment(self, assessment_id: str, payload: DDIAssessmentUpdate) -> DDIAssessment | None:
        """Update an existing DDI assessment."""
        with self._lock:
            existing = self._ddi_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DDIAssessment(**data)
            self._ddi_assessments[assessment_id] = updated
        return updated

    def delete_ddi_assessment(self, assessment_id: str) -> bool:
        """Delete a DDI assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._ddi_assessments:
                del self._ddi_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ClinicalPharmacologyMetrics:
        """Compute aggregated clinical pharmacology operational metrics."""
        with self._lock:
            studies = list(self._studies.values())
            samples = list(self._samples.values())
            escalations = list(self._escalations.values())
            exposure_analyses = list(self._exposure_analyses.values())
            ddi_assessments = list(self._ddi_assessments.values())

        # Studies by type
        studies_by_type: dict[str, int] = {}
        for s in studies:
            key = s.study_type.value
            studies_by_type[key] = studies_by_type.get(key, 0) + 1

        # Studies by status
        studies_by_status: dict[str, int] = {}
        for s in studies:
            key = s.status.value
            studies_by_status[key] = studies_by_status.get(key, 0) + 1

        # Samples by status
        samples_by_status: dict[str, int] = {}
        for s in samples:
            key = s.status.value
            samples_by_status[key] = samples_by_status.get(key, 0) + 1

        samples_analyzed = sum(
            1 for s in samples if s.status in (SampleStatus.ANALYZED, SampleStatus.REPORTED)
        )
        samples_failed_qc = sum(
            1 for s in samples if s.status == SampleStatus.FAILED_QC
        )

        # Escalations by decision
        escalations_by_decision: dict[str, int] = {}
        for e in escalations:
            if e.decision is not None:
                key = e.decision.value
                escalations_by_decision[key] = escalations_by_decision.get(key, 0) + 1

        # DDI by risk
        ddi_by_risk: dict[str, int] = {}
        for d in ddi_assessments:
            key = d.risk_classification.value
            ddi_by_risk[key] = ddi_by_risk.get(key, 0) + 1

        # Average sample analysis rate
        total_samples = len(samples)
        if total_samples > 0:
            avg_sample_analysis_rate = round((samples_analyzed / total_samples) * 100, 1)
        else:
            avg_sample_analysis_rate = 0.0

        return ClinicalPharmacologyMetrics(
            total_studies=len(studies),
            studies_by_type=studies_by_type,
            studies_by_status=studies_by_status,
            total_samples=total_samples,
            samples_by_status=samples_by_status,
            samples_analyzed=samples_analyzed,
            samples_failed_qc=samples_failed_qc,
            total_escalations=len(escalations),
            escalations_by_decision=escalations_by_decision,
            total_exposure_analyses=len(exposure_analyses),
            total_ddi_assessments=len(ddi_assessments),
            ddi_by_risk=ddi_by_risk,
            avg_sample_analysis_rate=avg_sample_analysis_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalPharmacologyService | None = None
_instance_lock = threading.Lock()


def get_clinical_pharmacology_service() -> ClinicalPharmacologyService:
    """Return the singleton ClinicalPharmacologyService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalPharmacologyService()
    return _instance


def reset_clinical_pharmacology_service() -> ClinicalPharmacologyService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalPharmacologyService()
    return _instance
