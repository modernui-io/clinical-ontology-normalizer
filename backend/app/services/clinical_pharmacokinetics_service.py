"""Clinical Pharmacokinetics Service (CLIN-PK).

Manages clinical PK operations: PK study management, concentration
data tracking, compartmental modeling, drug interaction analysis,
and exposure-response assessment with PK metrics.

Usage:
    from app.services.clinical_pharmacokinetics_service import (
        get_clinical_pharmacokinetics_service,
    )

    svc = get_clinical_pharmacokinetics_service()
    studies = svc.list_pk_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_pharmacokinetics import (
    ClinicalPharmacokineticsMetrics,
    CompartmentalModel,
    CompartmentalModelCreate,
    CompartmentalModelUpdate,
    ConcentrationData,
    ConcentrationDataCreate,
    ConcentrationDataUpdate,
    DrugInteraction,
    DrugInteractionCreate,
    DrugInteractionUpdate,
    ExposureResponse,
    ExposureResponseCreate,
    ExposureResponseUpdate,
    InteractionSeverity,
    InteractionType,
    ModelType,
    PKStudy,
    PKStudyCreate,
    PKStudyStatus,
    PKStudyType,
    PKStudyUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalPharmacokineticsService:
    """In-memory Clinical Pharmacokinetics engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._pk_studies: dict[str, PKStudy] = {}
        self._concentration_data: dict[str, ConcentrationData] = {}
        self._compartmental_models: dict[str, CompartmentalModel] = {}
        self._drug_interactions: dict[str, DrugInteraction] = {}
        self._exposure_responses: dict[str, ExposureResponse] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic clinical pharmacokinetics data."""
        now = datetime.now(timezone.utc)

        # --- 12 PK Studies ---
        studies_data = [
            {
                "id": "PKS-001",
                "trial_id": EYLEA_TRIAL,
                "study_name": "Aflibercept Single-Dose PK in Healthy Volunteers",
                "study_type": PKStudyType.SINGLE_DOSE,
                "status": PKStudyStatus.COMPLETED,
                "drug_name": "Aflibercept",
                "dose": "2 mg intravitreal",
                "route": "intravitreal",
                "subjects_planned": 24,
                "subjects_enrolled": 24,
                "sampling_timepoints": ["0", "0.5", "1", "2", "4", "8", "12", "24", "48", "72", "168", "336"],
                "total_samples_planned": 288,
                "total_samples_collected": 288,
                "bioanalytical_method": "ELISA",
                "lloq": 0.05,
                "uloq": 500.0,
                "start_date": now - timedelta(days=365),
                "completion_date": now - timedelta(days=300),
                "principal_investigator": "Dr. Sarah Chen",
                "notes": "Pivotal single-dose PK study. All subjects completed.",
                "created_at": now - timedelta(days=370),
            },
            {
                "id": "PKS-002",
                "trial_id": EYLEA_TRIAL,
                "study_name": "Aflibercept Multiple-Dose PK in nAMD Patients",
                "study_type": PKStudyType.MULTIPLE_DOSE,
                "status": PKStudyStatus.DATA_ANALYSIS,
                "drug_name": "Aflibercept",
                "dose": "2 mg Q8W intravitreal",
                "route": "intravitreal",
                "subjects_planned": 48,
                "subjects_enrolled": 45,
                "sampling_timepoints": ["0", "1", "4", "8", "24", "168", "336", "672", "1344"],
                "total_samples_planned": 432,
                "total_samples_collected": 405,
                "bioanalytical_method": "ELISA",
                "lloq": 0.05,
                "uloq": 500.0,
                "start_date": now - timedelta(days=300),
                "completion_date": None,
                "principal_investigator": "Dr. Sarah Chen",
                "notes": "Multi-dose study in target population. Data analysis in progress.",
                "created_at": now - timedelta(days=305),
            },
            {
                "id": "PKS-003",
                "trial_id": EYLEA_TRIAL,
                "study_name": "Aflibercept Population PK Analysis",
                "study_type": PKStudyType.POPULATION_PK,
                "status": PKStudyStatus.REPORT_WRITING,
                "drug_name": "Aflibercept",
                "dose": "2 mg intravitreal",
                "route": "intravitreal",
                "subjects_planned": 200,
                "subjects_enrolled": 195,
                "sampling_timepoints": ["sparse"],
                "total_samples_planned": 600,
                "total_samples_collected": 585,
                "bioanalytical_method": "ELISA",
                "lloq": 0.05,
                "uloq": 500.0,
                "start_date": now - timedelta(days=250),
                "completion_date": None,
                "principal_investigator": "Dr. James Wright",
                "notes": "Integrated population PK analysis across studies.",
                "created_at": now - timedelta(days=255),
            },
            {
                "id": "PKS-004",
                "trial_id": EYLEA_TRIAL,
                "study_name": "Aflibercept Special Population PK - Renal Impairment",
                "study_type": PKStudyType.SPECIAL_POPULATION,
                "status": PKStudyStatus.SAMPLE_COLLECTION,
                "drug_name": "Aflibercept",
                "dose": "2 mg intravitreal",
                "route": "intravitreal",
                "subjects_planned": 32,
                "subjects_enrolled": 18,
                "sampling_timepoints": ["0", "0.5", "1", "2", "4", "8", "24", "48", "168"],
                "total_samples_planned": 288,
                "total_samples_collected": 162,
                "bioanalytical_method": "ELISA",
                "lloq": 0.05,
                "uloq": 500.0,
                "start_date": now - timedelta(days=120),
                "completion_date": None,
                "principal_investigator": "Dr. James Wright",
                "notes": "Evaluating PK in patients with mild/moderate/severe renal impairment.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "PKS-005",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "Dupilumab Single-Dose PK Characterization",
                "study_type": PKStudyType.SINGLE_DOSE,
                "status": PKStudyStatus.COMPLETED,
                "drug_name": "Dupilumab",
                "dose": "300 mg SC",
                "route": "subcutaneous",
                "subjects_planned": 36,
                "subjects_enrolled": 36,
                "sampling_timepoints": ["0", "1", "2", "4", "8", "12", "24", "48", "72", "168", "336", "504", "672"],
                "total_samples_planned": 468,
                "total_samples_collected": 468,
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.1,
                "uloq": 1000.0,
                "start_date": now - timedelta(days=400),
                "completion_date": now - timedelta(days=330),
                "principal_investigator": "Dr. Maria Lopez",
                "notes": "Pivotal single-dose PK in healthy volunteers. Completed successfully.",
                "created_at": now - timedelta(days=405),
            },
            {
                "id": "PKS-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "Dupilumab Food Effect Study",
                "study_type": PKStudyType.FOOD_EFFECT,
                "status": PKStudyStatus.COMPLETED,
                "drug_name": "Dupilumab",
                "dose": "300 mg SC",
                "route": "subcutaneous",
                "subjects_planned": 24,
                "subjects_enrolled": 24,
                "sampling_timepoints": ["0", "0.5", "1", "2", "4", "8", "12", "24", "48", "72"],
                "total_samples_planned": 480,
                "total_samples_collected": 472,
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.1,
                "uloq": 1000.0,
                "start_date": now - timedelta(days=350),
                "completion_date": now - timedelta(days=290),
                "principal_investigator": "Dr. Maria Lopez",
                "notes": "Crossover design. No clinically significant food effect observed.",
                "created_at": now - timedelta(days=355),
            },
            {
                "id": "PKS-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "Dupilumab Drug Interaction Study with Methotrexate",
                "study_type": PKStudyType.DRUG_INTERACTION,
                "status": PKStudyStatus.BIOANALYSIS,
                "drug_name": "Dupilumab",
                "dose": "300 mg SC Q2W",
                "route": "subcutaneous",
                "subjects_planned": 30,
                "subjects_enrolled": 28,
                "sampling_timepoints": ["0", "1", "2", "4", "8", "24", "48", "168", "336"],
                "total_samples_planned": 540,
                "total_samples_collected": 504,
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.1,
                "uloq": 1000.0,
                "start_date": now - timedelta(days=180),
                "completion_date": None,
                "principal_investigator": "Dr. Robert Kim",
                "notes": "Evaluating bidirectional interaction with methotrexate.",
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "PKS-008",
                "trial_id": DUPIXENT_TRIAL,
                "study_name": "Dupilumab Population PK in Atopic Dermatitis",
                "study_type": PKStudyType.POPULATION_PK,
                "status": PKStudyStatus.DATA_ANALYSIS,
                "drug_name": "Dupilumab",
                "dose": "300 mg SC Q2W",
                "route": "subcutaneous",
                "subjects_planned": 350,
                "subjects_enrolled": 342,
                "sampling_timepoints": ["sparse"],
                "total_samples_planned": 1050,
                "total_samples_collected": 1026,
                "bioanalytical_method": "LC-MS/MS",
                "lloq": 0.1,
                "uloq": 1000.0,
                "start_date": now - timedelta(days=200),
                "completion_date": None,
                "principal_investigator": "Dr. Robert Kim",
                "notes": "Large-scale population PK model development.",
                "created_at": now - timedelta(days=205),
            },
            {
                "id": "PKS-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "Cemiplimab Single-Dose IV PK Study",
                "study_type": PKStudyType.SINGLE_DOSE,
                "status": PKStudyStatus.COMPLETED,
                "drug_name": "Cemiplimab",
                "dose": "350 mg IV",
                "route": "intravenous",
                "subjects_planned": 30,
                "subjects_enrolled": 30,
                "sampling_timepoints": ["0", "0.5", "1", "2", "4", "8", "24", "48", "72", "168", "336", "504"],
                "total_samples_planned": 360,
                "total_samples_collected": 360,
                "bioanalytical_method": "ELISA",
                "lloq": 0.02,
                "uloq": 800.0,
                "start_date": now - timedelta(days=450),
                "completion_date": now - timedelta(days=380),
                "principal_investigator": "Dr. Angela Park",
                "notes": "Single-dose PK characterization in advanced CSCC patients.",
                "created_at": now - timedelta(days=455),
            },
            {
                "id": "PKS-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "Cemiplimab Multiple-Dose PK in NSCLC",
                "study_type": PKStudyType.MULTIPLE_DOSE,
                "status": PKStudyStatus.DATA_ANALYSIS,
                "drug_name": "Cemiplimab",
                "dose": "350 mg IV Q3W",
                "route": "intravenous",
                "subjects_planned": 60,
                "subjects_enrolled": 58,
                "sampling_timepoints": ["0", "0.5", "1", "4", "24", "168", "336", "504"],
                "total_samples_planned": 480,
                "total_samples_collected": 464,
                "bioanalytical_method": "ELISA",
                "lloq": 0.02,
                "uloq": 800.0,
                "start_date": now - timedelta(days=280),
                "completion_date": None,
                "principal_investigator": "Dr. Angela Park",
                "notes": "Multi-dose PK in NSCLC with steady-state characterization.",
                "created_at": now - timedelta(days=285),
            },
            {
                "id": "PKS-011",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "Cemiplimab Drug Interaction with Carboplatin",
                "study_type": PKStudyType.DRUG_INTERACTION,
                "status": PKStudyStatus.SAMPLE_COLLECTION,
                "drug_name": "Cemiplimab",
                "dose": "350 mg IV Q3W",
                "route": "intravenous",
                "subjects_planned": 40,
                "subjects_enrolled": 25,
                "sampling_timepoints": ["0", "0.5", "1", "2", "4", "8", "24", "168"],
                "total_samples_planned": 320,
                "total_samples_collected": 200,
                "bioanalytical_method": "ELISA",
                "lloq": 0.02,
                "uloq": 800.0,
                "start_date": now - timedelta(days=150),
                "completion_date": None,
                "principal_investigator": "Dr. William Torres",
                "notes": "Evaluating PK interaction with carboplatin combination regimen.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "PKS-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_name": "Cemiplimab Population PK in Solid Tumors",
                "study_type": PKStudyType.POPULATION_PK,
                "status": PKStudyStatus.PLANNED,
                "drug_name": "Cemiplimab",
                "dose": "350 mg IV Q3W",
                "route": "intravenous",
                "subjects_planned": 500,
                "subjects_enrolled": 0,
                "sampling_timepoints": ["sparse"],
                "total_samples_planned": 1500,
                "total_samples_collected": 0,
                "bioanalytical_method": "ELISA",
                "lloq": 0.02,
                "uloq": 800.0,
                "start_date": None,
                "completion_date": None,
                "principal_investigator": "Dr. William Torres",
                "notes": "Planned integrated population PK analysis across solid tumor indications.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for s in studies_data:
            self._pk_studies[s["id"]] = PKStudy(**s)

        # --- 12 Concentration Data records ---
        conc_data = [
            {
                "id": "CD-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "subject_id": "SUBJ-001",
                "period": 1,
                "timepoint_hours": 0.0,
                "nominal_time_hours": 0.0,
                "concentration": 0.0,
                "unit": "ng/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "plasma",
                "assay_date": now - timedelta(days=340),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech A. Martinez",
                "notes": "Predose sample.",
                "created_at": now - timedelta(days=340),
            },
            {
                "id": "CD-002",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "subject_id": "SUBJ-001",
                "period": 1,
                "timepoint_hours": 1.0,
                "nominal_time_hours": 1.0,
                "concentration": 12.5,
                "unit": "ng/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "plasma",
                "assay_date": now - timedelta(days=340),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech A. Martinez",
                "notes": None,
                "created_at": now - timedelta(days=340),
            },
            {
                "id": "CD-003",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "subject_id": "SUBJ-001",
                "period": 1,
                "timepoint_hours": 4.0,
                "nominal_time_hours": 4.0,
                "concentration": 45.2,
                "unit": "ng/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "plasma",
                "assay_date": now - timedelta(days=339),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech A. Martinez",
                "notes": "Cmax observed near this timepoint.",
                "created_at": now - timedelta(days=339),
            },
            {
                "id": "CD-004",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "subject_id": "SUBJ-001",
                "period": 1,
                "timepoint_hours": 336.0,
                "nominal_time_hours": 336.0,
                "concentration": 0.03,
                "unit": "ng/mL",
                "below_lloq": True,
                "sample_quality": "acceptable",
                "matrix": "plasma",
                "assay_date": now - timedelta(days=326),
                "reanalysis": False,
                "flag": "BLQ",
                "analyzed_by": "Lab Tech A. Martinez",
                "notes": "Below LLOQ at 14 days post-dose.",
                "created_at": now - timedelta(days=326),
            },
            {
                "id": "CD-005",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-005",
                "subject_id": "SUBJ-101",
                "period": 1,
                "timepoint_hours": 0.0,
                "nominal_time_hours": 0.0,
                "concentration": 0.0,
                "unit": "ng/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "plasma",
                "assay_date": now - timedelta(days=380),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech B. Johnson",
                "notes": "Predose baseline.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "CD-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-005",
                "subject_id": "SUBJ-101",
                "period": 1,
                "timepoint_hours": 8.0,
                "nominal_time_hours": 8.0,
                "concentration": 28.7,
                "unit": "ng/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "plasma",
                "assay_date": now - timedelta(days=379),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech B. Johnson",
                "notes": "Absorption phase ongoing.",
                "created_at": now - timedelta(days=379),
            },
            {
                "id": "CD-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-005",
                "subject_id": "SUBJ-101",
                "period": 1,
                "timepoint_hours": 168.0,
                "nominal_time_hours": 168.0,
                "concentration": 52.1,
                "unit": "ng/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "serum",
                "assay_date": now - timedelta(days=373),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech B. Johnson",
                "notes": "Near Cmax for SC administration.",
                "created_at": now - timedelta(days=373),
            },
            {
                "id": "CD-008",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-006",
                "subject_id": "SUBJ-102",
                "period": 2,
                "timepoint_hours": 4.0,
                "nominal_time_hours": 4.0,
                "concentration": 15.3,
                "unit": "ng/mL",
                "below_lloq": False,
                "sample_quality": "hemolyzed",
                "matrix": "plasma",
                "assay_date": now - timedelta(days=310),
                "reanalysis": True,
                "flag": "hemolysis",
                "analyzed_by": "Lab Tech B. Johnson",
                "notes": "Hemolyzed sample; reanalysis confirmed value within 15% of original.",
                "created_at": now - timedelta(days=310),
            },
            {
                "id": "CD-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-009",
                "subject_id": "SUBJ-201",
                "period": 1,
                "timepoint_hours": 0.5,
                "nominal_time_hours": 0.5,
                "concentration": 185.4,
                "unit": "ug/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "serum",
                "assay_date": now - timedelta(days=420),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech C. Davis",
                "notes": "End of infusion sample. High concentration expected for IV.",
                "created_at": now - timedelta(days=420),
            },
            {
                "id": "CD-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-009",
                "subject_id": "SUBJ-201",
                "period": 1,
                "timepoint_hours": 24.0,
                "nominal_time_hours": 24.0,
                "concentration": 98.2,
                "unit": "ug/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "serum",
                "assay_date": now - timedelta(days=419),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech C. Davis",
                "notes": "Distribution phase.",
                "created_at": now - timedelta(days=419),
            },
            {
                "id": "CD-011",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-009",
                "subject_id": "SUBJ-201",
                "period": 1,
                "timepoint_hours": 504.0,
                "nominal_time_hours": 504.0,
                "concentration": 12.8,
                "unit": "ug/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "serum",
                "assay_date": now - timedelta(days=399),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech C. Davis",
                "notes": "Terminal elimination phase.",
                "created_at": now - timedelta(days=399),
            },
            {
                "id": "CD-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-010",
                "subject_id": "SUBJ-202",
                "period": 3,
                "timepoint_hours": 0.0,
                "nominal_time_hours": 0.0,
                "concentration": 42.5,
                "unit": "ug/mL",
                "below_lloq": False,
                "sample_quality": "acceptable",
                "matrix": "serum",
                "assay_date": now - timedelta(days=220),
                "reanalysis": False,
                "flag": None,
                "analyzed_by": "Lab Tech C. Davis",
                "notes": "Trough concentration at steady state (Cycle 3, Day 1).",
                "created_at": now - timedelta(days=220),
            },
        ]

        for c in conc_data:
            self._concentration_data[c["id"]] = ConcentrationData(**c)

        # --- 12 Compartmental Models ---
        models_data = [
            {
                "id": "CM-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "model_name": "Aflibercept One-Compartment IV/IVT Model",
                "model_type": ModelType.ONE_COMPARTMENT,
                "software": "NONMEM",
                "objective_function_value": -245.8,
                "aic": -239.8,
                "bic": -228.5,
                "parameters": [
                    {"name": "CL", "value": 0.28, "unit": "L/day", "rse_pct": 8.2},
                    {"name": "Vd", "value": 3.1, "unit": "L", "rse_pct": 12.5},
                    {"name": "Ka", "value": 0.45, "unit": "1/day", "rse_pct": 18.3},
                ],
                "covariates_tested": ["body_weight", "age", "renal_function", "albumin"],
                "significant_covariates": ["body_weight"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 1000,
                "model_qualified": True,
                "modeler": "Dr. Sarah Chen",
                "reviewer": "Dr. James Wright",
                "notes": "Final qualified model for single-dose PK.",
                "created_at": now - timedelta(days=290),
            },
            {
                "id": "CM-002",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-002",
                "model_name": "Aflibercept Two-Compartment with TMDD",
                "model_type": ModelType.TWO_COMPARTMENT,
                "software": "NONMEM",
                "objective_function_value": -512.3,
                "aic": -498.3,
                "bic": -478.1,
                "parameters": [
                    {"name": "CL", "value": 0.31, "unit": "L/day", "rse_pct": 6.8},
                    {"name": "Vc", "value": 3.2, "unit": "L", "rse_pct": 9.1},
                    {"name": "Vp", "value": 4.8, "unit": "L", "rse_pct": 15.2},
                    {"name": "Q", "value": 0.85, "unit": "L/day", "rse_pct": 22.4},
                    {"name": "Kd", "value": 0.5, "unit": "nM", "rse_pct": 25.0},
                ],
                "covariates_tested": ["body_weight", "age", "renal_function", "VEGF_level", "albumin"],
                "significant_covariates": ["body_weight", "VEGF_level"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 500,
                "model_qualified": True,
                "modeler": "Dr. Sarah Chen",
                "reviewer": "Dr. James Wright",
                "notes": "TMDD model captures nonlinear PK at low concentrations.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "CM-003",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "model_name": "Aflibercept NCA Analysis",
                "model_type": ModelType.NONCOMPARTMENTAL,
                "software": "Phoenix WinNonlin",
                "objective_function_value": None,
                "aic": None,
                "bic": None,
                "parameters": [
                    {"name": "AUCinf", "value": 325.6, "unit": "ng*day/mL", "rse_pct": None},
                    {"name": "Cmax", "value": 48.2, "unit": "ng/mL", "rse_pct": None},
                    {"name": "Tmax", "value": 3.5, "unit": "days", "rse_pct": None},
                    {"name": "t1/2", "value": 5.8, "unit": "days", "rse_pct": None},
                ],
                "covariates_tested": [],
                "significant_covariates": [],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": False,
                "bootstrap_runs": 0,
                "model_qualified": True,
                "modeler": "Dr. James Wright",
                "reviewer": "Dr. Sarah Chen",
                "notes": "Standard NCA for regulatory submission.",
                "created_at": now - timedelta(days=295),
            },
            {
                "id": "CM-004",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-003",
                "model_name": "Aflibercept Population PK Mixed-Effects Model",
                "model_type": ModelType.POPULATION_MIXED_EFFECTS,
                "software": "NONMEM",
                "objective_function_value": -1820.5,
                "aic": -1790.5,
                "bic": -1755.2,
                "parameters": [
                    {"name": "CL", "value": 0.29, "unit": "L/day", "rse_pct": 4.2},
                    {"name": "Vc", "value": 3.15, "unit": "L", "rse_pct": 5.8},
                    {"name": "Vp", "value": 4.6, "unit": "L", "rse_pct": 8.9},
                    {"name": "Q", "value": 0.82, "unit": "L/day", "rse_pct": 12.1},
                ],
                "covariates_tested": ["body_weight", "age", "sex", "renal_function", "albumin", "anti_drug_antibody"],
                "significant_covariates": ["body_weight", "anti_drug_antibody"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 2000,
                "model_qualified": False,
                "modeler": "Dr. James Wright",
                "reviewer": None,
                "notes": "Pending external qualification. ADA status is a significant covariate.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "CM-005",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-005",
                "model_name": "Dupilumab One-Compartment SC Absorption",
                "model_type": ModelType.ONE_COMPARTMENT,
                "software": "Monolix",
                "objective_function_value": -398.2,
                "aic": -390.2,
                "bic": -378.5,
                "parameters": [
                    {"name": "CL", "value": 0.15, "unit": "L/day", "rse_pct": 7.5},
                    {"name": "Vd", "value": 4.8, "unit": "L", "rse_pct": 11.2},
                    {"name": "Ka", "value": 0.18, "unit": "1/day", "rse_pct": 14.8},
                    {"name": "F1", "value": 0.64, "unit": "", "rse_pct": 9.5},
                ],
                "covariates_tested": ["body_weight", "injection_site", "age"],
                "significant_covariates": ["body_weight"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 1000,
                "model_qualified": True,
                "modeler": "Dr. Maria Lopez",
                "reviewer": "Dr. Robert Kim",
                "notes": "Bioavailability estimated at 64%. Body weight on CL and Vd.",
                "created_at": now - timedelta(days=320),
            },
            {
                "id": "CM-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-005",
                "model_name": "Dupilumab NCA Summary",
                "model_type": ModelType.NONCOMPARTMENTAL,
                "software": "Phoenix WinNonlin",
                "objective_function_value": None,
                "aic": None,
                "bic": None,
                "parameters": [
                    {"name": "AUCinf", "value": 1285.0, "unit": "ng*day/mL", "rse_pct": None},
                    {"name": "Cmax", "value": 55.8, "unit": "ng/mL", "rse_pct": None},
                    {"name": "Tmax", "value": 7.0, "unit": "days", "rse_pct": None},
                    {"name": "t1/2", "value": 18.2, "unit": "days", "rse_pct": None},
                ],
                "covariates_tested": [],
                "significant_covariates": [],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": False,
                "bootstrap_runs": 0,
                "model_qualified": True,
                "modeler": "Dr. Robert Kim",
                "reviewer": "Dr. Maria Lopez",
                "notes": "Standard NCA parameters for dupilumab SC dosing.",
                "created_at": now - timedelta(days=325),
            },
            {
                "id": "CM-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-008",
                "model_name": "Dupilumab Population PK with TMDD",
                "model_type": ModelType.POPULATION_MIXED_EFFECTS,
                "software": "NONMEM",
                "objective_function_value": -3250.8,
                "aic": -3210.8,
                "bic": -3165.2,
                "parameters": [
                    {"name": "CL", "value": 0.148, "unit": "L/day", "rse_pct": 3.1},
                    {"name": "Vc", "value": 4.72, "unit": "L", "rse_pct": 4.5},
                    {"name": "Vp", "value": 3.85, "unit": "L", "rse_pct": 7.2},
                    {"name": "Q", "value": 0.42, "unit": "L/day", "rse_pct": 11.5},
                    {"name": "Kss", "value": 1.2, "unit": "mg/L", "rse_pct": 15.8},
                ],
                "covariates_tested": ["body_weight", "age", "sex", "disease_severity", "albumin", "anti_drug_antibody"],
                "significant_covariates": ["body_weight", "disease_severity", "anti_drug_antibody"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 1500,
                "model_qualified": False,
                "modeler": "Dr. Robert Kim",
                "reviewer": None,
                "notes": "TMDD with quasi-steady-state approximation. Disease severity on CL.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CM-008",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-008",
                "model_name": "Dupilumab PBPK Skin Distribution Model",
                "model_type": ModelType.PBPK,
                "software": "Simcyp",
                "objective_function_value": None,
                "aic": None,
                "bic": None,
                "parameters": [
                    {"name": "tissue_partition", "value": 0.35, "unit": "", "rse_pct": None},
                    {"name": "skin_perfusion", "value": 0.05, "unit": "L/h/kg", "rse_pct": None},
                    {"name": "lymph_flow", "value": 0.002, "unit": "L/h", "rse_pct": None},
                ],
                "covariates_tested": ["body_weight", "skin_thickness", "disease_severity"],
                "significant_covariates": ["disease_severity"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": False,
                "bootstrap_runs": 0,
                "model_qualified": False,
                "modeler": "Dr. Robert Kim",
                "reviewer": None,
                "notes": "PBPK model predicting skin tissue concentrations. Exploratory.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CM-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-009",
                "model_name": "Cemiplimab Two-Compartment Linear Model",
                "model_type": ModelType.TWO_COMPARTMENT,
                "software": "NONMEM",
                "objective_function_value": -685.4,
                "aic": -673.4,
                "bic": -658.1,
                "parameters": [
                    {"name": "CL", "value": 0.22, "unit": "L/day", "rse_pct": 5.5},
                    {"name": "Vc", "value": 3.45, "unit": "L", "rse_pct": 7.8},
                    {"name": "Vp", "value": 2.95, "unit": "L", "rse_pct": 13.2},
                    {"name": "Q", "value": 0.65, "unit": "L/day", "rse_pct": 18.5},
                ],
                "covariates_tested": ["body_weight", "age", "tumor_burden", "albumin"],
                "significant_covariates": ["body_weight", "albumin"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 1000,
                "model_qualified": True,
                "modeler": "Dr. Angela Park",
                "reviewer": "Dr. William Torres",
                "notes": "Linear kinetics confirmed at 350 mg dose. Well-characterized model.",
                "created_at": now - timedelta(days=370),
            },
            {
                "id": "CM-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-009",
                "model_name": "Cemiplimab NCA Analysis",
                "model_type": ModelType.NONCOMPARTMENTAL,
                "software": "Phoenix WinNonlin",
                "objective_function_value": None,
                "aic": None,
                "bic": None,
                "parameters": [
                    {"name": "AUCinf", "value": 4580.0, "unit": "ug*day/mL", "rse_pct": None},
                    {"name": "Cmax", "value": 198.5, "unit": "ug/mL", "rse_pct": None},
                    {"name": "t1/2", "value": 22.5, "unit": "days", "rse_pct": None},
                    {"name": "CL", "value": 0.076, "unit": "L/day", "rse_pct": None},
                ],
                "covariates_tested": [],
                "significant_covariates": [],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": False,
                "bootstrap_runs": 0,
                "model_qualified": True,
                "modeler": "Dr. William Torres",
                "reviewer": "Dr. Angela Park",
                "notes": "NCA summary statistics for regulatory filing.",
                "created_at": now - timedelta(days=375),
            },
            {
                "id": "CM-011",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-010",
                "model_name": "Cemiplimab Three-Compartment Model",
                "model_type": ModelType.THREE_COMPARTMENT,
                "software": "NONMEM",
                "objective_function_value": -892.1,
                "aic": -870.1,
                "bic": -842.5,
                "parameters": [
                    {"name": "CL", "value": 0.215, "unit": "L/day", "rse_pct": 4.8},
                    {"name": "Vc", "value": 3.5, "unit": "L", "rse_pct": 6.2},
                    {"name": "Vp1", "value": 2.8, "unit": "L", "rse_pct": 10.5},
                    {"name": "Vp2", "value": 1.2, "unit": "L", "rse_pct": 28.5},
                    {"name": "Q1", "value": 0.62, "unit": "L/day", "rse_pct": 15.8},
                    {"name": "Q2", "value": 0.08, "unit": "L/day", "rse_pct": 35.2},
                ],
                "covariates_tested": ["body_weight", "tumor_burden", "PD_L1_expression", "albumin"],
                "significant_covariates": ["body_weight", "tumor_burden"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 800,
                "model_qualified": False,
                "modeler": "Dr. Angela Park",
                "reviewer": None,
                "notes": "Three-compartment tested but marginal improvement over two-compartment.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "CM-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-010",
                "model_name": "Cemiplimab Population PK Final Model",
                "model_type": ModelType.POPULATION_MIXED_EFFECTS,
                "software": "NONMEM",
                "objective_function_value": -1580.2,
                "aic": -1552.2,
                "bic": -1518.8,
                "parameters": [
                    {"name": "CL", "value": 0.218, "unit": "L/day", "rse_pct": 3.5},
                    {"name": "Vc", "value": 3.48, "unit": "L", "rse_pct": 4.8},
                    {"name": "Vp", "value": 2.92, "unit": "L", "rse_pct": 7.5},
                    {"name": "Q", "value": 0.64, "unit": "L/day", "rse_pct": 10.2},
                ],
                "covariates_tested": ["body_weight", "age", "sex", "tumor_burden", "albumin", "ECOG"],
                "significant_covariates": ["body_weight", "albumin", "tumor_burden"],
                "goodness_of_fit_adequate": True,
                "vpc_adequate": True,
                "bootstrap_runs": 2000,
                "model_qualified": True,
                "modeler": "Dr. Angela Park",
                "reviewer": "Dr. William Torres",
                "notes": "Final qualified population PK model. Two-compartment selected over three.",
                "created_at": now - timedelta(days=180),
            },
        ]

        for m in models_data:
            self._compartmental_models[m["id"]] = CompartmentalModel(**m)

        # --- 12 Drug Interactions ---
        interactions_data = [
            {
                "id": "DI-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "perpetrator_drug": "Aflibercept",
                "victim_drug": "Warfarin",
                "interaction_type": InteractionType.SUBSTRATE,
                "severity": InteractionSeverity.NO_INTERACTION,
                "mechanism": "No common metabolic pathway",
                "enzyme_involved": None,
                "auc_ratio": 1.02,
                "cmax_ratio": 0.99,
                "clinical_significance": "No clinically significant interaction",
                "dose_adjustment_needed": False,
                "recommended_adjustment": None,
                "in_vitro_data": True,
                "in_vivo_data": True,
                "assessed_by": "Dr. Sarah Chen",
                "assessment_date": now - timedelta(days=280),
                "notes": "Intravitreal administration limits systemic interaction potential.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "DI-002",
                "trial_id": EYLEA_TRIAL,
                "study_id": None,
                "perpetrator_drug": "Ranibizumab",
                "victim_drug": "Aflibercept",
                "interaction_type": InteractionType.COMBINED,
                "severity": InteractionSeverity.CONTRAINDICATED,
                "mechanism": "Competitive VEGF binding; overlapping mechanism",
                "enzyme_involved": None,
                "auc_ratio": None,
                "cmax_ratio": None,
                "clinical_significance": "Concurrent use of anti-VEGF agents contraindicated",
                "dose_adjustment_needed": False,
                "recommended_adjustment": "Do not co-administer",
                "in_vitro_data": True,
                "in_vivo_data": False,
                "assessed_by": "Dr. James Wright",
                "assessment_date": now - timedelta(days=260),
                "notes": "Pharmacological interaction; not enzyme-mediated.",
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "DI-003",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-007",
                "perpetrator_drug": "Dupilumab",
                "victim_drug": "Methotrexate",
                "interaction_type": InteractionType.INHIBITOR,
                "severity": InteractionSeverity.MILD,
                "mechanism": "IL-4/IL-13 blockade may reverse CYP suppression by cytokines",
                "enzyme_involved": "CYP3A4",
                "auc_ratio": 0.88,
                "cmax_ratio": 0.92,
                "clinical_significance": "Mild decrease in methotrexate exposure; monitor levels",
                "dose_adjustment_needed": False,
                "recommended_adjustment": None,
                "in_vitro_data": True,
                "in_vivo_data": True,
                "assessed_by": "Dr. Robert Kim",
                "assessment_date": now - timedelta(days=160),
                "notes": "Cytokine modulation effect. Clinically not meaningful for most patients.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "DI-004",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-007",
                "perpetrator_drug": "Dupilumab",
                "victim_drug": "Cyclosporine",
                "interaction_type": InteractionType.INHIBITOR,
                "severity": InteractionSeverity.MODERATE,
                "mechanism": "Cytokine suppression restores CYP3A4 activity",
                "enzyme_involved": "CYP3A4",
                "auc_ratio": 0.72,
                "cmax_ratio": 0.78,
                "clinical_significance": "Moderate reduction in cyclosporine exposure; dose monitoring required",
                "dose_adjustment_needed": True,
                "recommended_adjustment": "Monitor cyclosporine levels; may need 20-30% dose increase",
                "in_vitro_data": True,
                "in_vivo_data": True,
                "assessed_by": "Dr. Robert Kim",
                "assessment_date": now - timedelta(days=140),
                "notes": "Clinically significant for narrow therapeutic index drugs metabolized by CYP3A4.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "DI-005",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": None,
                "perpetrator_drug": "Corticosteroids",
                "victim_drug": "Dupilumab",
                "interaction_type": InteractionType.SUBSTRATE,
                "severity": InteractionSeverity.NO_INTERACTION,
                "mechanism": "No pharmacokinetic interaction",
                "enzyme_involved": None,
                "auc_ratio": 1.05,
                "cmax_ratio": 1.03,
                "clinical_significance": "Safe for co-administration",
                "dose_adjustment_needed": False,
                "recommended_adjustment": None,
                "in_vitro_data": False,
                "in_vivo_data": True,
                "assessed_by": "Dr. Maria Lopez",
                "assessment_date": now - timedelta(days=300),
                "notes": "Concomitant topical corticosteroids do not affect dupilumab PK.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "DI-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": None,
                "perpetrator_drug": "Dupilumab",
                "victim_drug": "Oral Contraceptives",
                "interaction_type": InteractionType.SUBSTRATE,
                "severity": InteractionSeverity.NO_INTERACTION,
                "mechanism": "No CYP-mediated interaction",
                "enzyme_involved": None,
                "auc_ratio": 0.98,
                "cmax_ratio": 1.01,
                "clinical_significance": "No dose adjustment needed for oral contraceptives",
                "dose_adjustment_needed": False,
                "recommended_adjustment": None,
                "in_vitro_data": True,
                "in_vivo_data": True,
                "assessed_by": "Dr. Maria Lopez",
                "assessment_date": now - timedelta(days=290),
                "notes": "Important for labeling in reproductive-age female population.",
                "created_at": now - timedelta(days=290),
            },
            {
                "id": "DI-007",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-011",
                "perpetrator_drug": "Carboplatin",
                "victim_drug": "Cemiplimab",
                "interaction_type": InteractionType.SUBSTRATE,
                "severity": InteractionSeverity.NO_INTERACTION,
                "mechanism": "No pharmacokinetic interaction; different elimination pathways",
                "enzyme_involved": None,
                "auc_ratio": 1.04,
                "cmax_ratio": 1.02,
                "clinical_significance": "Safe combination; no PK interaction",
                "dose_adjustment_needed": False,
                "recommended_adjustment": None,
                "in_vitro_data": False,
                "in_vivo_data": True,
                "assessed_by": "Dr. William Torres",
                "assessment_date": now - timedelta(days=120),
                "notes": "Supports carboplatin-cemiplimab combination regimen.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "DI-008",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-011",
                "perpetrator_drug": "Cemiplimab",
                "victim_drug": "Paclitaxel",
                "interaction_type": InteractionType.INDUCER,
                "severity": InteractionSeverity.MILD,
                "mechanism": "Immune activation may modestly affect CYP2C8 activity",
                "enzyme_involved": "CYP2C8",
                "auc_ratio": 0.91,
                "cmax_ratio": 0.94,
                "clinical_significance": "Mild; no dose adjustment recommended",
                "dose_adjustment_needed": False,
                "recommended_adjustment": None,
                "in_vitro_data": True,
                "in_vivo_data": True,
                "assessed_by": "Dr. William Torres",
                "assessment_date": now - timedelta(days=110),
                "notes": "Marginal effect; well within bioequivalence bounds.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "DI-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": None,
                "perpetrator_drug": "Prednisone",
                "victim_drug": "Cemiplimab",
                "interaction_type": InteractionType.INHIBITOR,
                "severity": InteractionSeverity.SEVERE,
                "mechanism": "Systemic corticosteroids suppress immune activation; reduce efficacy",
                "enzyme_involved": None,
                "auc_ratio": 1.01,
                "cmax_ratio": 1.00,
                "clinical_significance": "PK unchanged but PD severely impacted; avoid high-dose systemic steroids",
                "dose_adjustment_needed": True,
                "recommended_adjustment": "Limit prednisone to <= 10 mg/day or equivalent",
                "in_vitro_data": False,
                "in_vivo_data": True,
                "assessed_by": "Dr. Angela Park",
                "assessment_date": now - timedelta(days=200),
                "notes": "Pharmacodynamic interaction; PK unaffected but efficacy compromised.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "DI-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": None,
                "perpetrator_drug": "Nivolumab",
                "victim_drug": "Cemiplimab",
                "interaction_type": InteractionType.COMBINED,
                "severity": InteractionSeverity.CONTRAINDICATED,
                "mechanism": "Dual PD-1 blockade; overlapping mechanism of action",
                "enzyme_involved": None,
                "auc_ratio": None,
                "cmax_ratio": None,
                "clinical_significance": "Concurrent PD-1/PD-L1 inhibitors contraindicated",
                "dose_adjustment_needed": False,
                "recommended_adjustment": "Do not co-administer",
                "in_vitro_data": False,
                "in_vivo_data": False,
                "assessed_by": "Dr. Angela Park",
                "assessment_date": now - timedelta(days=350),
                "notes": "Class-level contraindication for checkpoint inhibitor combinations.",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "DI-011",
                "trial_id": EYLEA_TRIAL,
                "study_id": None,
                "perpetrator_drug": "Aflibercept",
                "victim_drug": "Anti-hypertensives",
                "interaction_type": InteractionType.SUBSTRATE,
                "severity": InteractionSeverity.MILD,
                "mechanism": "VEGF inhibition may cause hypertension requiring dose adjustment",
                "enzyme_involved": None,
                "auc_ratio": 1.0,
                "cmax_ratio": 1.0,
                "clinical_significance": "Monitor blood pressure; may need anti-hypertensive titration",
                "dose_adjustment_needed": True,
                "recommended_adjustment": "Increase anti-hypertensive monitoring frequency",
                "in_vitro_data": False,
                "in_vivo_data": True,
                "assessed_by": "Dr. Sarah Chen",
                "assessment_date": now - timedelta(days=240),
                "notes": "Pharmacodynamic interaction class effect for anti-VEGF agents.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "DI-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": None,
                "perpetrator_drug": "Cemiplimab",
                "victim_drug": "Theophylline",
                "interaction_type": InteractionType.TRANSPORTER,
                "severity": InteractionSeverity.MODERATE,
                "mechanism": "Immune-mediated CYP1A2 restoration in inflammation state",
                "enzyme_involved": "CYP1A2",
                "auc_ratio": 0.75,
                "cmax_ratio": 0.80,
                "clinical_significance": "Monitor theophylline levels; may need dose increase",
                "dose_adjustment_needed": True,
                "recommended_adjustment": "Check theophylline levels after cemiplimab initiation",
                "in_vitro_data": True,
                "in_vivo_data": False,
                "assessed_by": "Dr. Angela Park",
                "assessment_date": now - timedelta(days=180),
                "notes": "Theoretical risk based on CYP1A2 substrate sensitivity analysis.",
                "created_at": now - timedelta(days=180),
            },
        ]

        for di in interactions_data:
            self._drug_interactions[di["id"]] = DrugInteraction(**di)

        # --- 12 Exposure-Response records ---
        er_data = [
            {
                "id": "ER-001",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-002",
                "analysis_name": "Aflibercept AUC vs Visual Acuity Gain",
                "exposure_metric": "AUCss",
                "response_endpoint": "BCVA change from baseline at Week 52",
                "relationship_type": "emax",
                "model_type": "emax_model",
                "subjects_analyzed": 150,
                "significant_relationship": True,
                "p_value": 0.0012,
                "r_squared": 0.42,
                "ec50": 85.0,
                "emax": 15.2,
                "therapeutic_window_lower": 40.0,
                "therapeutic_window_upper": 250.0,
                "dose_recommendation": "2 mg Q8W provides exposure in therapeutic window for most patients",
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=220),
                "notes": "Clear exposure-response relationship for visual acuity endpoint.",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "ER-002",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-002",
                "analysis_name": "Aflibercept Cmin vs Retinal Thickness",
                "exposure_metric": "Cmin_ss",
                "response_endpoint": "Central subfield thickness reduction at Week 52",
                "relationship_type": "linear",
                "model_type": "linear_regression",
                "subjects_analyzed": 145,
                "significant_relationship": True,
                "p_value": 0.0035,
                "r_squared": 0.35,
                "ec50": None,
                "emax": None,
                "therapeutic_window_lower": 0.5,
                "therapeutic_window_upper": 5.0,
                "dose_recommendation": "Maintain Cmin above 0.5 ng/mL for optimal retinal thickness reduction",
                "analyzed_by": "Dr. James Wright",
                "analysis_date": now - timedelta(days=210),
                "notes": "Linear relationship within observed concentration range.",
                "created_at": now - timedelta(days=210),
            },
            {
                "id": "ER-003",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-001",
                "analysis_name": "Aflibercept AUC vs Hypertension Risk",
                "exposure_metric": "AUCinf",
                "response_endpoint": "Incidence of treatment-emergent hypertension",
                "relationship_type": "logistic",
                "model_type": "logistic_regression",
                "subjects_analyzed": 200,
                "significant_relationship": False,
                "p_value": 0.32,
                "r_squared": 0.04,
                "ec50": None,
                "emax": None,
                "therapeutic_window_lower": None,
                "therapeutic_window_upper": None,
                "dose_recommendation": "No exposure-driven hypertension risk at intravitreal doses",
                "analyzed_by": "Dr. James Wright",
                "analysis_date": now - timedelta(days=190),
                "notes": "Systemic exposure too low for E-R relationship with safety endpoint.",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "ER-004",
                "trial_id": EYLEA_TRIAL,
                "study_id": "PKS-003",
                "analysis_name": "Aflibercept AUC vs Immunogenicity",
                "exposure_metric": "AUCss",
                "response_endpoint": "Anti-drug antibody development",
                "relationship_type": "logistic",
                "model_type": "logistic_regression",
                "subjects_analyzed": 195,
                "significant_relationship": False,
                "p_value": 0.55,
                "r_squared": 0.02,
                "ec50": None,
                "emax": None,
                "therapeutic_window_lower": None,
                "therapeutic_window_upper": None,
                "dose_recommendation": None,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=170),
                "notes": "Low immunogenicity overall; no exposure-dependent risk.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "ER-005",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-008",
                "analysis_name": "Dupilumab Cmin vs EASI-75 Response",
                "exposure_metric": "Cmin_ss",
                "response_endpoint": "EASI-75 response at Week 16",
                "relationship_type": "emax",
                "model_type": "emax_model",
                "subjects_analyzed": 340,
                "significant_relationship": True,
                "p_value": 0.00001,
                "r_squared": 0.58,
                "ec50": 25.0,
                "emax": 0.85,
                "therapeutic_window_lower": 10.0,
                "therapeutic_window_upper": 150.0,
                "dose_recommendation": "300 mg Q2W achieves near-maximal efficacy in most patients",
                "analyzed_by": "Dr. Robert Kim",
                "analysis_date": now - timedelta(days=130),
                "notes": "Strong E-R for primary efficacy endpoint. Plateau above ~75 ng/mL.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "ER-006",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-008",
                "analysis_name": "Dupilumab AUC vs IGA Response",
                "exposure_metric": "AUCss",
                "response_endpoint": "IGA 0/1 response at Week 16",
                "relationship_type": "emax",
                "model_type": "emax_model",
                "subjects_analyzed": 335,
                "significant_relationship": True,
                "p_value": 0.00005,
                "r_squared": 0.52,
                "ec50": 1800.0,
                "emax": 0.78,
                "therapeutic_window_lower": 800.0,
                "therapeutic_window_upper": 8000.0,
                "dose_recommendation": "Current dosing regimen provides adequate exposure for IGA response",
                "analyzed_by": "Dr. Robert Kim",
                "analysis_date": now - timedelta(days=125),
                "notes": "Consistent with EASI-75 E-R analysis. Supports 300 mg Q2W.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "ER-007",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-008",
                "analysis_name": "Dupilumab Cmax vs Injection Site Reactions",
                "exposure_metric": "Cmax",
                "response_endpoint": "Injection site reaction frequency",
                "relationship_type": "linear",
                "model_type": "logistic_regression",
                "subjects_analyzed": 340,
                "significant_relationship": False,
                "p_value": 0.18,
                "r_squared": 0.05,
                "ec50": None,
                "emax": None,
                "therapeutic_window_lower": None,
                "therapeutic_window_upper": None,
                "dose_recommendation": None,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=115),
                "notes": "ISRs not exposure-dependent; likely related to injection technique.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "ER-008",
                "trial_id": DUPIXENT_TRIAL,
                "study_id": "PKS-005",
                "analysis_name": "Dupilumab Exposure vs Eosinophil Count",
                "exposure_metric": "AUCss",
                "response_endpoint": "Transient eosinophilia (>1000 cells/uL)",
                "relationship_type": "linear",
                "model_type": "linear_regression",
                "subjects_analyzed": 330,
                "significant_relationship": True,
                "p_value": 0.008,
                "r_squared": 0.12,
                "ec50": None,
                "emax": None,
                "therapeutic_window_lower": None,
                "therapeutic_window_upper": None,
                "dose_recommendation": "Monitor eosinophils; generally transient and self-resolving",
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=105),
                "notes": "Weak but statistically significant relationship. Clinical relevance low.",
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "ER-009",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-010",
                "analysis_name": "Cemiplimab AUC vs Objective Response Rate",
                "exposure_metric": "AUCss",
                "response_endpoint": "ORR by RECIST v1.1",
                "relationship_type": "emax",
                "model_type": "emax_model",
                "subjects_analyzed": 280,
                "significant_relationship": True,
                "p_value": 0.0008,
                "r_squared": 0.38,
                "ec50": 2200.0,
                "emax": 0.55,
                "therapeutic_window_lower": 1000.0,
                "therapeutic_window_upper": 10000.0,
                "dose_recommendation": "350 mg Q3W achieves exposure above EC90 in >90% of patients",
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=160),
                "notes": "Plateau region reached at 350 mg; no benefit from higher doses.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "ER-010",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-010",
                "analysis_name": "Cemiplimab Cmin vs Progression-Free Survival",
                "exposure_metric": "Cmin_ss",
                "response_endpoint": "PFS hazard ratio",
                "relationship_type": "linear",
                "model_type": "cox_regression",
                "subjects_analyzed": 275,
                "significant_relationship": True,
                "p_value": 0.002,
                "r_squared": 0.28,
                "ec50": None,
                "emax": None,
                "therapeutic_window_lower": 30.0,
                "therapeutic_window_upper": None,
                "dose_recommendation": "Maintain Cmin above 30 ug/mL for PFS benefit",
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=145),
                "notes": "Significant correlation between trough levels and PFS.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "ER-011",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-009",
                "analysis_name": "Cemiplimab Exposure vs Immune-Related AEs",
                "exposure_metric": "AUCss",
                "response_endpoint": "Grade 3+ immune-related adverse events",
                "relationship_type": "logistic",
                "model_type": "logistic_regression",
                "subjects_analyzed": 290,
                "significant_relationship": True,
                "p_value": 0.015,
                "r_squared": 0.18,
                "ec50": None,
                "emax": None,
                "therapeutic_window_lower": None,
                "therapeutic_window_upper": 12000.0,
                "dose_recommendation": "Monitor for irAEs at high exposure; no dose cap recommended",
                "analyzed_by": "Dr. William Torres",
                "analysis_date": now - timedelta(days=135),
                "notes": "Modest E-R for safety; benefit-risk still favorable at 350 mg.",
                "created_at": now - timedelta(days=135),
            },
            {
                "id": "ER-012",
                "trial_id": LIBTAYO_TRIAL,
                "study_id": "PKS-010",
                "analysis_name": "Cemiplimab Receptor Occupancy vs T-cell Activation",
                "exposure_metric": "Cmin_ss",
                "response_endpoint": "PD-1 receptor occupancy percentage",
                "relationship_type": "emax",
                "model_type": "emax_model",
                "subjects_analyzed": 120,
                "significant_relationship": True,
                "p_value": 0.00001,
                "r_squared": 0.72,
                "ec50": 15.0,
                "emax": 99.5,
                "therapeutic_window_lower": 5.0,
                "therapeutic_window_upper": None,
                "dose_recommendation": "Near-complete receptor occupancy achieved at 350 mg Q3W trough",
                "analyzed_by": "Dr. William Torres",
                "analysis_date": now - timedelta(days=100),
                "notes": "PK/PD bridge confirming dose selection. >95% RO at trough.",
                "created_at": now - timedelta(days=100),
            },
        ]

        for er in er_data:
            self._exposure_responses[er["id"]] = ExposureResponse(**er)

    # ------------------------------------------------------------------
    # PK Studies
    # ------------------------------------------------------------------

    def list_pk_studies(
        self,
        *,
        trial_id: str | None = None,
        study_type: PKStudyType | None = None,
        status: PKStudyStatus | None = None,
    ) -> list[PKStudy]:
        """List PK studies with optional filters."""
        with self._lock:
            result = list(self._pk_studies.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if study_type is not None:
            result = [s for s in result if s.study_type == study_type]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_pk_study(self, study_id: str) -> PKStudy | None:
        """Get a single PK study by ID."""
        with self._lock:
            return self._pk_studies.get(study_id)

    def create_pk_study(self, payload: PKStudyCreate) -> PKStudy:
        """Create a new PK study."""
        now = datetime.now(timezone.utc)
        study_id = f"PKS-{uuid4().hex[:8].upper()}"
        study = PKStudy(
            id=study_id,
            trial_id=payload.trial_id,
            study_name=payload.study_name,
            study_type=payload.study_type,
            status=PKStudyStatus.PLANNED,
            drug_name=payload.drug_name,
            dose=payload.dose,
            route="oral",
            subjects_planned=payload.subjects_planned,
            subjects_enrolled=0,
            sampling_timepoints=[],
            total_samples_planned=0,
            total_samples_collected=0,
            bioanalytical_method=None,
            lloq=None,
            uloq=None,
            start_date=None,
            completion_date=None,
            principal_investigator=payload.principal_investigator,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._pk_studies[study_id] = study
        logger.info("Created PK study %s for trial %s", study_id, payload.trial_id)
        return study

    def update_pk_study(
        self, study_id: str, payload: PKStudyUpdate
    ) -> PKStudy | None:
        """Update an existing PK study."""
        with self._lock:
            existing = self._pk_studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PKStudy(**data)
            self._pk_studies[study_id] = updated
        return updated

    def delete_pk_study(self, study_id: str) -> bool:
        """Delete a PK study. Returns True if deleted."""
        with self._lock:
            if study_id in self._pk_studies:
                del self._pk_studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Concentration Data
    # ------------------------------------------------------------------

    def list_concentration_data(
        self,
        *,
        trial_id: str | None = None,
        study_id: str | None = None,
        subject_id: str | None = None,
    ) -> list[ConcentrationData]:
        """List concentration data with optional filters."""
        with self._lock:
            result = list(self._concentration_data.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if study_id is not None:
            result = [c for c in result if c.study_id == study_id]
        if subject_id is not None:
            result = [c for c in result if c.subject_id == subject_id]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_concentration_data(self, data_id: str) -> ConcentrationData | None:
        """Get a single concentration data record by ID."""
        with self._lock:
            return self._concentration_data.get(data_id)

    def create_concentration_data(self, payload: ConcentrationDataCreate) -> ConcentrationData:
        """Create a new concentration data record."""
        now = datetime.now(timezone.utc)
        data_id = f"CD-{uuid4().hex[:8].upper()}"
        record = ConcentrationData(
            id=data_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            subject_id=payload.subject_id,
            period=1,
            timepoint_hours=payload.timepoint_hours,
            nominal_time_hours=payload.nominal_time_hours,
            concentration=payload.concentration,
            unit=payload.unit,
            below_lloq=False,
            sample_quality="acceptable",
            matrix="plasma",
            assay_date=None,
            reanalysis=False,
            flag=None,
            analyzed_by=payload.analyzed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._concentration_data[data_id] = record
        logger.info("Created concentration data %s for study %s", data_id, payload.study_id)
        return record

    def update_concentration_data(
        self, data_id: str, payload: ConcentrationDataUpdate
    ) -> ConcentrationData | None:
        """Update an existing concentration data record."""
        with self._lock:
            existing = self._concentration_data.get(data_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ConcentrationData(**data)
            self._concentration_data[data_id] = updated
        return updated

    def delete_concentration_data(self, data_id: str) -> bool:
        """Delete a concentration data record. Returns True if deleted."""
        with self._lock:
            if data_id in self._concentration_data:
                del self._concentration_data[data_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compartmental Models
    # ------------------------------------------------------------------

    def list_compartmental_models(
        self,
        *,
        trial_id: str | None = None,
        study_id: str | None = None,
        model_type: ModelType | None = None,
    ) -> list[CompartmentalModel]:
        """List compartmental models with optional filters."""
        with self._lock:
            result = list(self._compartmental_models.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if study_id is not None:
            result = [m for m in result if m.study_id == study_id]
        if model_type is not None:
            result = [m for m in result if m.model_type == model_type]

        return sorted(result, key=lambda m: m.created_at, reverse=True)

    def get_compartmental_model(self, model_id: str) -> CompartmentalModel | None:
        """Get a single compartmental model by ID."""
        with self._lock:
            return self._compartmental_models.get(model_id)

    def create_compartmental_model(self, payload: CompartmentalModelCreate) -> CompartmentalModel:
        """Create a new compartmental model."""
        now = datetime.now(timezone.utc)
        model_id = f"CM-{uuid4().hex[:8].upper()}"
        model = CompartmentalModel(
            id=model_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            model_name=payload.model_name,
            model_type=payload.model_type,
            software=payload.software,
            objective_function_value=None,
            aic=None,
            bic=None,
            parameters=[],
            covariates_tested=[],
            significant_covariates=[],
            goodness_of_fit_adequate=False,
            vpc_adequate=False,
            bootstrap_runs=0,
            model_qualified=False,
            modeler=payload.modeler,
            reviewer=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._compartmental_models[model_id] = model
        logger.info("Created compartmental model %s for study %s", model_id, payload.study_id)
        return model

    def update_compartmental_model(
        self, model_id: str, payload: CompartmentalModelUpdate
    ) -> CompartmentalModel | None:
        """Update an existing compartmental model."""
        with self._lock:
            existing = self._compartmental_models.get(model_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CompartmentalModel(**data)
            self._compartmental_models[model_id] = updated
        return updated

    def delete_compartmental_model(self, model_id: str) -> bool:
        """Delete a compartmental model. Returns True if deleted."""
        with self._lock:
            if model_id in self._compartmental_models:
                del self._compartmental_models[model_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Drug Interactions
    # ------------------------------------------------------------------

    def list_drug_interactions(
        self,
        *,
        trial_id: str | None = None,
        interaction_type: InteractionType | None = None,
        severity: InteractionSeverity | None = None,
    ) -> list[DrugInteraction]:
        """List drug interactions with optional filters."""
        with self._lock:
            result = list(self._drug_interactions.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if interaction_type is not None:
            result = [d for d in result if d.interaction_type == interaction_type]
        if severity is not None:
            result = [d for d in result if d.severity == severity]

        return sorted(result, key=lambda d: d.assessment_date, reverse=True)

    def get_drug_interaction(self, interaction_id: str) -> DrugInteraction | None:
        """Get a single drug interaction by ID."""
        with self._lock:
            return self._drug_interactions.get(interaction_id)

    def create_drug_interaction(self, payload: DrugInteractionCreate) -> DrugInteraction:
        """Create a new drug interaction record."""
        now = datetime.now(timezone.utc)
        interaction_id = f"DI-{uuid4().hex[:8].upper()}"
        interaction = DrugInteraction(
            id=interaction_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            perpetrator_drug=payload.perpetrator_drug,
            victim_drug=payload.victim_drug,
            interaction_type=payload.interaction_type,
            severity=payload.severity,
            mechanism=None,
            enzyme_involved=None,
            auc_ratio=None,
            cmax_ratio=None,
            clinical_significance=None,
            dose_adjustment_needed=False,
            recommended_adjustment=None,
            in_vitro_data=False,
            in_vivo_data=False,
            assessed_by=payload.assessed_by,
            assessment_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._drug_interactions[interaction_id] = interaction
        logger.info(
            "Created drug interaction %s for trial %s", interaction_id, payload.trial_id
        )
        return interaction

    def update_drug_interaction(
        self, interaction_id: str, payload: DrugInteractionUpdate
    ) -> DrugInteraction | None:
        """Update an existing drug interaction."""
        with self._lock:
            existing = self._drug_interactions.get(interaction_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DrugInteraction(**data)
            self._drug_interactions[interaction_id] = updated
        return updated

    def delete_drug_interaction(self, interaction_id: str) -> bool:
        """Delete a drug interaction. Returns True if deleted."""
        with self._lock:
            if interaction_id in self._drug_interactions:
                del self._drug_interactions[interaction_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Exposure-Response
    # ------------------------------------------------------------------

    def list_exposure_responses(
        self,
        *,
        trial_id: str | None = None,
        study_id: str | None = None,
        significant_only: bool | None = None,
    ) -> list[ExposureResponse]:
        """List exposure-response analyses with optional filters."""
        with self._lock:
            result = list(self._exposure_responses.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if study_id is not None:
            result = [e for e in result if e.study_id == study_id]
        if significant_only is not None and significant_only:
            result = [e for e in result if e.significant_relationship]

        return sorted(result, key=lambda e: e.analysis_date, reverse=True)

    def get_exposure_response(self, er_id: str) -> ExposureResponse | None:
        """Get a single exposure-response analysis by ID."""
        with self._lock:
            return self._exposure_responses.get(er_id)

    def create_exposure_response(self, payload: ExposureResponseCreate) -> ExposureResponse:
        """Create a new exposure-response analysis."""
        now = datetime.now(timezone.utc)
        er_id = f"ER-{uuid4().hex[:8].upper()}"
        er = ExposureResponse(
            id=er_id,
            trial_id=payload.trial_id,
            study_id=payload.study_id,
            analysis_name=payload.analysis_name,
            exposure_metric=payload.exposure_metric,
            response_endpoint=payload.response_endpoint,
            relationship_type="linear",
            model_type="logistic_regression",
            subjects_analyzed=payload.subjects_analyzed,
            significant_relationship=False,
            p_value=None,
            r_squared=None,
            ec50=None,
            emax=None,
            therapeutic_window_lower=None,
            therapeutic_window_upper=None,
            dose_recommendation=None,
            analyzed_by=payload.analyzed_by,
            analysis_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._exposure_responses[er_id] = er
        logger.info("Created exposure-response %s for trial %s", er_id, payload.trial_id)
        return er

    def update_exposure_response(
        self, er_id: str, payload: ExposureResponseUpdate
    ) -> ExposureResponse | None:
        """Update an existing exposure-response analysis."""
        with self._lock:
            existing = self._exposure_responses.get(er_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ExposureResponse(**data)
            self._exposure_responses[er_id] = updated
        return updated

    def delete_exposure_response(self, er_id: str) -> bool:
        """Delete an exposure-response analysis. Returns True if deleted."""
        with self._lock:
            if er_id in self._exposure_responses:
                del self._exposure_responses[er_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ClinicalPharmacokineticsMetrics:
        """Compute aggregated clinical pharmacokinetics metrics."""
        with self._lock:
            studies = list(self._pk_studies.values())
            conc_records = list(self._concentration_data.values())
            models = list(self._compartmental_models.values())
            interactions = list(self._drug_interactions.values())
            er_analyses = list(self._exposure_responses.values())

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

        # Below LLOQ percentage
        total_conc = len(conc_records)
        below_lloq_count = sum(1 for c in conc_records if c.below_lloq)
        below_lloq_pct = round(
            (below_lloq_count / max(1, total_conc)) * 100.0, 1
        )

        # Models by type
        models_by_type: dict[str, int] = {}
        for m in models:
            key = m.model_type.value
            models_by_type[key] = models_by_type.get(key, 0) + 1

        # Qualified models
        qualified = sum(1 for m in models if m.model_qualified)

        # Interactions by severity
        interactions_by_severity: dict[str, int] = {}
        for di in interactions:
            key = di.severity.value
            interactions_by_severity[key] = interactions_by_severity.get(key, 0) + 1

        # Dose adjustments needed
        dose_adj = sum(1 for di in interactions if di.dose_adjustment_needed)

        # Significant relationships
        sig_rel = sum(1 for er in er_analyses if er.significant_relationship)

        return ClinicalPharmacokineticsMetrics(
            total_pk_studies=len(studies),
            studies_by_type=studies_by_type,
            studies_by_status=studies_by_status,
            total_concentration_records=total_conc,
            below_lloq_pct=below_lloq_pct,
            total_models=len(models),
            models_by_type=models_by_type,
            qualified_models=qualified,
            total_interactions=len(interactions),
            interactions_by_severity=interactions_by_severity,
            dose_adjustments_needed=dose_adj,
            total_exposure_response=len(er_analyses),
            significant_relationships=sig_rel,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalPharmacokineticsService | None = None
_instance_lock = threading.Lock()


def get_clinical_pharmacokinetics_service() -> ClinicalPharmacokineticsService:
    """Return the singleton ClinicalPharmacokineticsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalPharmacokineticsService()
    return _instance


def reset_clinical_pharmacokinetics_service() -> ClinicalPharmacokineticsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalPharmacokineticsService()
    return _instance
