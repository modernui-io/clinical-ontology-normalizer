#!/usr/bin/env python3
"""Comprehensive demo data seeder for the Clinical Ontology Normalizer.

Seeds ALL demo data in one shot:
  1. Patients via FHIR Bundles (reuses seed_trial_patients pipeline)
  2. Clinical note Documents with realistic text
  3. Mention records with offsets matching document text
  4. MentionConceptCandidate records mapping to OMOP concepts
  5. Trial records in the DB
  6. TrialEnrollment records at various statuses over 60 days
  7. AuditLog entries spread over 30 days

Idempotent: checks if demo data exists before inserting.

Usage:
    python3 -m scripts.seed_demo_data

Or from the backend directory:
    python3 scripts/seed_demo_data.py
"""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add backend to path if running directly
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.database import async_session_maker, init_db  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.mention import Mention, MentionConceptCandidate  # noqa: E402
from app.models.trial import (  # noqa: E402
    EnrollmentStatus,
    Trial,
    TrialEnrollment,
    TrialPhase,
    TrialStatus,
)
from app.schemas.base import Assertion, Domain, Experiencer, JobStatus, Temporality  # noqa: E402

# Import the patient seeding function
from scripts.seed_trial_patients import seed_trial_patients  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Deterministic seed for reproducibility
random.seed(42)

NOW = datetime.now(timezone.utc)

# Stable UUIDs for demo trials (so they're predictable across runs)
EYLEA_TRIAL_ID = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL_ID = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL_ID = "00000000-de00-0003-0000-000000000003"


# =============================================================================
# Clinical Note Templates
# =============================================================================

CLINICAL_NOTES: list[dict[str, Any]] = [
    # --- EYLEA / DME patients ---
    {
        "patient_id": "eylea-pt-001",
        "note_type": "discharge_summary",
        "text": (
            "DISCHARGE SUMMARY\n\n"
            "Patient: Robert Chen  MRN: MRN-E001  DOB: 08/14/1963\n"
            "Admission Date: 11/15/2025  Discharge Date: 11/20/2025\n\n"
            "PRINCIPAL DIAGNOSIS: Diabetic macular edema\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "62-year-old male with history of type 2 diabetes mellitus diagnosed in 2015, "
            "presenting with progressive bilateral visual acuity decline over the past 6 months. "
            "Optical coherence tomography demonstrated central subfield thickness of 425 microns OS "
            "consistent with diabetic macular edema. Current HbA1c is 7.8%. "
            "Patient is on metformin 500 mg twice daily with good compliance.\n\n"
            "MEDICATIONS ON DISCHARGE:\n"
            "1. Metformin 500 mg PO BID\n"
            "2. Aflibercept 2 mg intravitreal injection (scheduled q8w after loading)\n\n"
            "ASSESSMENT AND PLAN:\n"
            "Patient with diabetic macular edema secondary to type 2 diabetes mellitus. "
            "Initiated intravitreal aflibercept therapy. Follow-up OCT in 4 weeks. "
            "Continue metformin. Ophthalmology follow-up scheduled."
        ),
        "mentions": [
            {"text": "type 2 diabetes mellitus", "section": "HPI", "omop_id": 201826, "concept_name": "Type 2 diabetes mellitus", "concept_code": "E11", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "diabetic macular edema", "section": "DIAGNOSIS", "omop_id": 4103532, "concept_name": "Diabetic macular edema", "concept_code": "H35.81", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "visual acuity decline", "section": "HPI", "omop_id": 377871, "concept_name": "Decreased visual acuity", "concept_code": "H54.7", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "metformin 500 mg", "section": "MEDICATIONS", "omop_id": 1503297, "concept_name": "Metformin 500 MG", "concept_code": "860975", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "HbA1c is 7.8%", "section": "HPI", "omop_id": 3004410, "concept_name": "Hemoglobin A1c", "concept_code": "4548-4", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "aflibercept 2 mg", "section": "MEDICATIONS", "omop_id": 44785829, "concept_name": "Aflibercept 2 MG", "concept_code": "1535929", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
    {
        "patient_id": "eylea-pt-002",
        "note_type": "progress_note",
        "text": (
            "OPHTHALMOLOGY PROGRESS NOTE\n\n"
            "Patient: Maria Santos  MRN: MRN-E002  DOB: 11/22/1970\n"
            "Date: 12/05/2025\n\n"
            "SUBJECTIVE:\n"
            "55-year-old female with type 2 diabetes mellitus and essential hypertension "
            "returning for follow-up of diabetic macular edema. Reports mild improvement in "
            "central vision since initiation of anti-VEGF therapy. Denies flashes or floaters.\n\n"
            "OBJECTIVE:\n"
            "VA: OD 20/40, OS 20/50. IOP: OD 14 mmHg, OS 15 mmHg.\n"
            "OCT: Central subfield thickness 380 microns OD, improved from 460 microns.\n"
            "HbA1c 8.5% (last lab 10/15/2025). On metformin and sitagliptin.\n\n"
            "ASSESSMENT:\n"
            "Diabetic macular edema improving on aflibercept therapy. "
            "Hypertension controlled. Diabetes suboptimally controlled.\n\n"
            "PLAN:\n"
            "Continue aflibercept q8w. Refer to endocrinology for diabetes optimization."
        ),
        "mentions": [
            {"text": "type 2 diabetes mellitus", "section": "SUBJECTIVE", "omop_id": 201826, "concept_name": "Type 2 diabetes mellitus", "concept_code": "E11", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "essential hypertension", "section": "SUBJECTIVE", "omop_id": 320128, "concept_name": "Essential hypertension", "concept_code": "I10", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "diabetic macular edema", "section": "SUBJECTIVE", "omop_id": 4103532, "concept_name": "Diabetic macular edema", "concept_code": "H35.81", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "HbA1c 8.5%", "section": "OBJECTIVE", "omop_id": 3004410, "concept_name": "Hemoglobin A1c", "concept_code": "4548-4", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "metformin", "section": "OBJECTIVE", "omop_id": 1503297, "concept_name": "Metformin", "concept_code": "860975", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "sitagliptin", "section": "OBJECTIVE", "omop_id": 1580747, "concept_name": "Sitagliptin", "concept_code": "213169", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
    {
        "patient_id": "eylea-pt-003",
        "note_type": "discharge_summary",
        "text": (
            "DISCHARGE SUMMARY\n\n"
            "Patient: James Williams  MRN: MRN-E003  DOB: 05/30/1954\n"
            "Admission Date: 12/01/2025  Discharge Date: 12/03/2025\n\n"
            "PRINCIPAL DIAGNOSIS: Diabetic retinopathy with macular edema\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "71-year-old male with longstanding type 2 diabetes mellitus since 2010 and "
            "hyperlipidemia. Referred for worsening diabetic retinopathy with macular edema. "
            "HbA1c elevated at 10.2%. Currently on insulin glargine and metformin. "
            "Systolic blood pressure measured at 138 mmHg during visit.\n\n"
            "HOSPITAL COURSE:\n"
            "Patient received intravitreal aflibercept injection OD. Tolerated well. "
            "No post-procedural complications noted.\n\n"
            "DISCHARGE MEDICATIONS:\n"
            "1. Insulin glargine 100 units/mL - continue current dose\n"
            "2. Metformin 500 mg PO BID\n"
            "3. Continue current lipid-lowering therapy"
        ),
        "mentions": [
            {"text": "type 2 diabetes mellitus", "section": "HPI", "omop_id": 201826, "concept_name": "Type 2 diabetes mellitus", "concept_code": "E11", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "diabetic retinopathy with macular edema", "section": "DIAGNOSIS", "omop_id": 4103532, "concept_name": "Diabetic macular edema", "concept_code": "E11.311", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "hyperlipidemia", "section": "HPI", "omop_id": 432867, "concept_name": "Hyperlipidemia", "concept_code": "E78.5", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "HbA1c elevated at 10.2%", "section": "HPI", "omop_id": 3004410, "concept_name": "Hemoglobin A1c", "concept_code": "4548-4", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "insulin glargine", "section": "MEDICATIONS", "omop_id": 1596977, "concept_name": "Insulin glargine", "concept_code": "1373463", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "metformin 500 mg", "section": "MEDICATIONS", "omop_id": 1503297, "concept_name": "Metformin 500 MG", "concept_code": "860975", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
    # --- Dupixent / Atopic Dermatitis patients ---
    {
        "patient_id": "dupixent-pt-001",
        "note_type": "progress_note",
        "text": (
            "DERMATOLOGY PROGRESS NOTE\n\n"
            "Patient: Sarah Kim  MRN: MRN-D001  DOB: 07/25/1991\n"
            "Date: 12/10/2025\n\n"
            "CHIEF COMPLAINT: Follow-up for moderate-to-severe atopic dermatitis.\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "34-year-old female with atopic dermatitis diagnosed in 2016 and comorbid "
            "allergic rhinitis. Previous treatment with triamcinolone cream and tacrolimus "
            "ointment with inadequate response. Current EASI score is 28, indicating "
            "moderate-to-severe disease. Patient reports significant pruritus affecting "
            "sleep quality and quality of life.\n\n"
            "PHYSICAL EXAM:\n"
            "Erythematous, lichenified plaques on bilateral antecubital fossae, popliteal "
            "fossae, and neck. Excoriations noted. No signs of superinfection.\n\n"
            "ASSESSMENT AND PLAN:\n"
            "Moderate-to-severe atopic dermatitis inadequately controlled with topical therapy. "
            "Recommend initiation of dupilumab (Dupixent) 300 mg subcutaneous q2w after loading. "
            "Continue emollient therapy. Follow-up in 16 weeks for EASI reassessment."
        ),
        "mentions": [
            {"text": "atopic dermatitis", "section": "CC", "omop_id": 4280723, "concept_name": "Atopic dermatitis", "concept_code": "L20.9", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "allergic rhinitis", "section": "HPI", "omop_id": 257007, "concept_name": "Allergic rhinitis", "concept_code": "J30.1", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "triamcinolone cream", "section": "HPI", "omop_id": 903963, "concept_name": "Triamcinolone topical", "concept_code": "795346", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "tacrolimus ointment", "section": "HPI", "omop_id": 950637, "concept_name": "Tacrolimus topical", "concept_code": "372048", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "EASI score is 28", "section": "HPI", "omop_id": 36303639, "concept_name": "EASI score", "concept_code": "76382-5", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "dupilumab", "section": "PLAN", "omop_id": 1510627, "concept_name": "Dupilumab", "concept_code": "1876366", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
    {
        "patient_id": "dupixent-pt-002",
        "note_type": "progress_note",
        "text": (
            "DERMATOLOGY CLINIC NOTE\n\n"
            "Patient: David Nguyen  MRN: MRN-D002  DOB: 02/11/1997\n"
            "Date: 11/28/2025\n\n"
            "CHIEF COMPLAINT: Worsening atopic dermatitis flare.\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "28-year-old male with longstanding history of atopic dermatitis since childhood "
            "and mild intermittent asthma. Currently using fluticasone propionate cream with "
            "partial response. EASI score today is 35, consistent with severe disease. "
            "HbA1c 5.4% (normal, no diabetes). Patient expresses frustration with chronic "
            "symptoms and impact on daily activities.\n\n"
            "CURRENT MEDICATIONS:\n"
            "1. Fluticasone propionate 0.05% cream - applied BID to affected areas\n"
            "2. Albuterol inhaler PRN for asthma\n\n"
            "ASSESSMENT:\n"
            "Severe atopic dermatitis refractory to topical corticosteroids. "
            "Candidate for systemic biologic therapy.\n\n"
            "PLAN:\n"
            "Discuss dupilumab initiation. Labs ordered. Return in 2 weeks."
        ),
        "mentions": [
            {"text": "atopic dermatitis", "section": "CC", "omop_id": 4280723, "concept_name": "Atopic dermatitis", "concept_code": "L20.89", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "mild intermittent asthma", "section": "HPI", "omop_id": 317009, "concept_name": "Asthma", "concept_code": "J45.20", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "fluticasone propionate cream", "section": "HPI", "omop_id": 1149380, "concept_name": "Fluticasone topical", "concept_code": "197446", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "EASI score today is 35", "section": "HPI", "omop_id": 36303639, "concept_name": "EASI score", "concept_code": "76382-5", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "HbA1c 5.4%", "section": "HPI", "omop_id": 3004410, "concept_name": "Hemoglobin A1c", "concept_code": "4548-4", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
        ],
    },
    {
        "patient_id": "dupixent-pt-003",
        "note_type": "progress_note",
        "text": (
            "DERMATOLOGY FOLLOW-UP NOTE\n\n"
            "Patient: Jennifer Garcia  MRN: MRN-D003  DOB: 09/04/1983\n"
            "Date: 12/01/2025\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "42-year-old female with atopic dermatitis since 2014. Has failed multiple "
            "topical therapies including triamcinolone and tacrolimus (both discontinued). "
            "Currently on fluticasone propionate with minimal benefit. EASI score 22 today. "
            "Skin involvement primarily trunk and extremities.\n\n"
            "ASSESSMENT:\n"
            "Moderate atopic dermatitis with history of topical treatment failure. "
            "Patient is a candidate for biologic therapy.\n\n"
            "PLAN:\n"
            "Start dupilumab 600 mg loading dose, then 300 mg q2w. "
            "Continue moisturizer regimen. Follow-up 8 weeks."
        ),
        "mentions": [
            {"text": "atopic dermatitis", "section": "HPI", "omop_id": 4280723, "concept_name": "Atopic dermatitis", "concept_code": "L20.9", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "triamcinolone", "section": "HPI", "omop_id": 903963, "concept_name": "Triamcinolone topical", "concept_code": "795346", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "tacrolimus", "section": "HPI", "omop_id": 950637, "concept_name": "Tacrolimus topical", "concept_code": "372048", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "fluticasone propionate", "section": "HPI", "omop_id": 1149380, "concept_name": "Fluticasone topical", "concept_code": "197446", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "EASI score 22", "section": "HPI", "omop_id": 36303639, "concept_name": "EASI score", "concept_code": "76382-5", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
        ],
    },
    # --- Libtayo / CSCC patients ---
    {
        "patient_id": "libtayo-pt-001",
        "note_type": "oncology_consult",
        "text": (
            "ONCOLOGY CONSULTATION NOTE\n\n"
            "Patient: Richard Anderson  MRN: MRN-L001  DOB: 04/08/1951\n"
            "Date: 12/08/2025\n\n"
            "REASON FOR CONSULTATION: Locally advanced cutaneous squamous cell carcinoma.\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "74-year-old male with essential hypertension, referred for evaluation of "
            "cutaneous squamous cell carcinoma diagnosed March 2025 via skin biopsy. "
            "Lesion located on left temple, 3.2 cm diameter, T3N0M0 staging. "
            "Not amenable to curative surgery or radiation. "
            "Systolic blood pressure 142 mmHg today. On lisinopril 10 mg.\n\n"
            "PATHOLOGY:\n"
            "Skin biopsy (03/10/2025): Invasive squamous cell carcinoma, moderately "
            "differentiated. PD-L1 combined positive score (CPS) of 15.\n\n"
            "ASSESSMENT:\n"
            "Locally advanced cutaneous squamous cell carcinoma, not amenable to surgery.\n\n"
            "PLAN:\n"
            "Recommend cemiplimab (Libtayo) 350 mg IV q3w. "
            "Check baseline labs including CBC, CMP, TSH, LFTs. "
            "Discuss potential immune-related adverse events."
        ),
        "mentions": [
            {"text": "cutaneous squamous cell carcinoma", "section": "CC", "omop_id": 4112853, "concept_name": "Squamous cell carcinoma of skin", "concept_code": "C44.92", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "essential hypertension", "section": "HPI", "omop_id": 320128, "concept_name": "Essential hypertension", "concept_code": "I10", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "skin biopsy", "section": "PATHOLOGY", "omop_id": 4180938, "concept_name": "Skin biopsy", "concept_code": "71388002", "vocab": "SNOMED", "domain": Domain.PROCEDURE},
            {"text": "lisinopril 10 mg", "section": "HPI", "omop_id": 1308216, "concept_name": "Lisinopril 10 MG", "concept_code": "316672", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "cemiplimab", "section": "PLAN", "omop_id": 36388308, "concept_name": "Cemiplimab", "concept_code": "2103176", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
    {
        "patient_id": "libtayo-pt-002",
        "note_type": "oncology_consult",
        "text": (
            "ONCOLOGY FOLLOW-UP NOTE\n\n"
            "Patient: Patricia Moore  MRN: MRN-L002  DOB: 11/29/1957\n"
            "Date: 11/20/2025\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "68-year-old female with squamous cell carcinoma of skin diagnosed December 2024. "
            "Status post Mohs micrographic surgery January 2025 with positive margins. "
            "Recurrence noted at surgical site. Also has hyperlipidemia on atorvastatin. "
            "WBC count 7.2 (within normal limits).\n\n"
            "ASSESSMENT:\n"
            "Recurrent cutaneous squamous cell carcinoma post Mohs surgery. "
            "Candidate for systemic immunotherapy.\n\n"
            "PLAN:\n"
            "Initiate cemiplimab 350 mg IV q3w. Staging CT chest/abdomen/pelvis. "
            "Continue atorvastatin 20 mg daily."
        ),
        "mentions": [
            {"text": "squamous cell carcinoma of skin", "section": "HPI", "omop_id": 4112853, "concept_name": "Squamous cell carcinoma of skin", "concept_code": "C44.92", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "Mohs micrographic surgery", "section": "HPI", "omop_id": 4222406, "concept_name": "Mohs micrographic surgery", "concept_code": "177164001", "vocab": "SNOMED", "domain": Domain.PROCEDURE},
            {"text": "hyperlipidemia", "section": "HPI", "omop_id": 432867, "concept_name": "Hyperlipidemia", "concept_code": "E78.5", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "atorvastatin", "section": "HPI", "omop_id": 1545958, "concept_name": "Atorvastatin 20 MG", "concept_code": "36567", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "WBC count 7.2", "section": "HPI", "omop_id": 3000905, "concept_name": "WBC count", "concept_code": "6690-2", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "cemiplimab", "section": "PLAN", "omop_id": 36388308, "concept_name": "Cemiplimab", "concept_code": "2103176", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
    {
        "patient_id": "libtayo-pt-003",
        "note_type": "oncology_consult",
        "text": (
            "ONCOLOGY CONSULTATION NOTE\n\n"
            "Patient: George Taylor  MRN: MRN-L003  DOB: 08/17/1946\n"
            "Date: 12/15/2025\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "79-year-old male with recurrent cutaneous squamous cell carcinoma diagnosed "
            "August 2024 and type 2 diabetes mellitus. HbA1c 6.8%, well-controlled on "
            "metformin 500 mg. Skin biopsy confirmed recurrence at prior excision site. "
            "Multiple actinic keratoses noted on sun-exposed areas.\n\n"
            "ASSESSMENT:\n"
            "Recurrent CSCC. Diabetes well-controlled. "
            "Candidate for checkpoint inhibitor therapy.\n\n"
            "PLAN:\n"
            "Start cemiplimab. Baseline echocardiogram and thyroid panel."
        ),
        "mentions": [
            {"text": "cutaneous squamous cell carcinoma", "section": "HPI", "omop_id": 4112853, "concept_name": "Squamous cell carcinoma of skin", "concept_code": "C44.92", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "type 2 diabetes mellitus", "section": "HPI", "omop_id": 201826, "concept_name": "Type 2 diabetes mellitus", "concept_code": "E11", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "HbA1c 6.8%", "section": "HPI", "omop_id": 3004410, "concept_name": "Hemoglobin A1c", "concept_code": "4548-4", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "metformin 500 mg", "section": "HPI", "omop_id": 1503297, "concept_name": "Metformin 500 MG", "concept_code": "860975", "vocab": "RxNorm", "domain": Domain.DRUG},
            {"text": "skin biopsy", "section": "HPI", "omop_id": 4180938, "concept_name": "Skin biopsy", "concept_code": "71388002", "vocab": "SNOMED", "domain": Domain.PROCEDURE},
        ],
    },
    # --- Ineligible patients ---
    {
        "patient_id": "ineligible-pt-001",
        "note_type": "progress_note",
        "text": (
            "ENDOCRINOLOGY PROGRESS NOTE\n\n"
            "Patient: Thomas Brown  MRN: MRN-X001  DOB: 07/20/1958\n"
            "Date: 12/12/2025\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "67-year-old male with poorly controlled type 2 diabetes mellitus and "
            "diabetic macular edema. HbA1c critically elevated at 13.2% despite "
            "insulin glargine therapy. Patient reports medication non-compliance.\n\n"
            "ASSESSMENT:\n"
            "Uncontrolled diabetes mellitus. HbA1c 13.2% excludes patient from "
            "EYLEA HD clinical trial (threshold < 12%). DME management complicated "
            "by poor glycemic control.\n\n"
            "PLAN:\n"
            "Intensify insulin regimen. Diabetes education referral. "
            "Repeat HbA1c in 3 months."
        ),
        "mentions": [
            {"text": "type 2 diabetes mellitus", "section": "HPI", "omop_id": 201826, "concept_name": "Type 2 diabetes mellitus", "concept_code": "E11", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "diabetic macular edema", "section": "HPI", "omop_id": 4103532, "concept_name": "Diabetic macular edema", "concept_code": "H35.81", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "HbA1c critically elevated at 13.2%", "section": "HPI", "omop_id": 3004410, "concept_name": "Hemoglobin A1c", "concept_code": "4548-4", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "insulin glargine", "section": "HPI", "omop_id": 1596977, "concept_name": "Insulin glargine", "concept_code": "1373463", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
    {
        "patient_id": "ineligible-pt-002",
        "note_type": "progress_note",
        "text": (
            "DERMATOLOGY PROGRESS NOTE\n\n"
            "Patient: Susan Martinez  MRN: MRN-X002  DOB: 04/15/1975\n"
            "Date: 12/05/2025\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "50-year-old female with atopic dermatitis and concurrent malignant neoplasm "
            "diagnosed November 2024. EASI score 25. Active malignancy excludes from "
            "Dupixent clinical trial. Triamcinolone cream partially effective.\n\n"
            "ASSESSMENT:\n"
            "Moderate atopic dermatitis. Active malignancy precludes biologic trial enrollment.\n\n"
            "PLAN:\n"
            "Continue topical therapy. Oncology coordinating cancer treatment. "
            "Revisit biologic eligibility after oncology clearance."
        ),
        "mentions": [
            {"text": "atopic dermatitis", "section": "HPI", "omop_id": 4280723, "concept_name": "Atopic dermatitis", "concept_code": "L20.9", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "malignant neoplasm", "section": "HPI", "omop_id": 443392, "concept_name": "Malignant neoplasm", "concept_code": "C80.1", "vocab": "ICD10CM", "domain": Domain.CONDITION},
            {"text": "EASI score 25", "section": "HPI", "omop_id": 36303639, "concept_name": "EASI score", "concept_code": "76382-5", "vocab": "LOINC", "domain": Domain.MEASUREMENT},
            {"text": "triamcinolone cream", "section": "HPI", "omop_id": 903963, "concept_name": "Triamcinolone topical", "concept_code": "795346", "vocab": "RxNorm", "domain": Domain.DRUG},
        ],
    },
]


# =============================================================================
# Trial Definitions (for DB persistence)
# =============================================================================

DEMO_TRIALS = [
    {
        "id": EYLEA_TRIAL_ID,
        "name": "EYLEA HD - Aflibercept for Diabetic Macular Edema",
        "nct_number": "NCT04429503",
        "protocol_id": "VGFTe-DME-2001",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": "A phase 3 study of high-dose aflibercept in patients with diabetic macular edema.",
        "therapeutic_area": "Ophthalmology",
        "indication_codes": ["H35.81", "E11.311"],
        "enrollment_target": 900,
        "site_count": 300,
    },
    {
        "id": DUPIXENT_TRIAL_ID,
        "name": "LIBERTY ADCHRONOS - Dupilumab for Atopic Dermatitis",
        "nct_number": "NCT02395133",
        "protocol_id": "R668-AD-1334",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": "A phase 3 study evaluating dupilumab in adult patients with moderate-to-severe atopic dermatitis inadequately controlled with topical corticosteroids.",
        "therapeutic_area": "Dermatology",
        "indication_codes": ["L20.9", "L20.89"],
        "enrollment_target": 600,
        "site_count": 250,
    },
    {
        "id": LIBTAYO_TRIAL_ID,
        "name": "LIBTAYO - Cemiplimab for Advanced CSCC",
        "nct_number": "NCT02760498",
        "protocol_id": "R2810-ONC-1540",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": "A phase 3 study of cemiplimab monotherapy in patients with locally advanced or metastatic cutaneous squamous cell carcinoma.",
        "therapeutic_area": "Oncology",
        "indication_codes": ["C44.92", "C44.9"],
        "enrollment_target": 200,
        "site_count": 75,
    },
]

# Map patient prefixes to their associated trial
PATIENT_TRIAL_MAP = {
    "eylea-pt": EYLEA_TRIAL_ID,
    "dupixent-pt": DUPIXENT_TRIAL_ID,
    "libtayo-pt": LIBTAYO_TRIAL_ID,
}

# All patient IDs from seed_trial_patients.py
ALL_PATIENT_IDS = [
    "eylea-pt-001", "eylea-pt-002", "eylea-pt-003", "eylea-pt-004", "eylea-pt-005",
    "dupixent-pt-001", "dupixent-pt-002", "dupixent-pt-003", "dupixent-pt-004", "dupixent-pt-005",
    "libtayo-pt-001", "libtayo-pt-002", "libtayo-pt-003", "libtayo-pt-004",
    "ineligible-pt-001", "ineligible-pt-002", "ineligible-pt-003", "ineligible-pt-004",
]

# Enrollment distribution per trial
ENROLLMENT_CONFIGS: list[dict[str, Any]] = [
    # EYLEA trial: 5 eligible + 1 ineligible
    {"trial_id": EYLEA_TRIAL_ID, "patients": [
        {"id": "eylea-pt-001", "status": EnrollmentStatus.ACTIVE, "score": 0.95, "days_ago": 45},
        {"id": "eylea-pt-002", "status": EnrollmentStatus.ENROLLED, "score": 0.88, "days_ago": 30},
        {"id": "eylea-pt-003", "status": EnrollmentStatus.ELIGIBLE, "score": 0.82, "days_ago": 20},
        {"id": "eylea-pt-004", "status": EnrollmentStatus.SCREENED, "score": 0.91, "days_ago": 10},
        {"id": "eylea-pt-005", "status": EnrollmentStatus.CANDIDATE, "score": 0.86, "days_ago": 5},
        {"id": "ineligible-pt-001", "status": EnrollmentStatus.INELIGIBLE, "score": 0.45, "days_ago": 35},
    ]},
    # Dupixent trial: 5 eligible + 2 ineligible
    {"trial_id": DUPIXENT_TRIAL_ID, "patients": [
        {"id": "dupixent-pt-001", "status": EnrollmentStatus.ACTIVE, "score": 0.93, "days_ago": 50},
        {"id": "dupixent-pt-002", "status": EnrollmentStatus.ENROLLED, "score": 0.89, "days_ago": 38},
        {"id": "dupixent-pt-003", "status": EnrollmentStatus.ELIGIBLE, "score": 0.85, "days_ago": 22},
        {"id": "dupixent-pt-004", "status": EnrollmentStatus.SCREENED, "score": 0.78, "days_ago": 12},
        {"id": "dupixent-pt-005", "status": EnrollmentStatus.CANDIDATE, "score": 0.76, "days_ago": 3},
        {"id": "ineligible-pt-002", "status": EnrollmentStatus.SCREEN_FAILED, "score": 0.40, "days_ago": 40},
        {"id": "ineligible-pt-004", "status": EnrollmentStatus.INELIGIBLE, "score": 0.35, "days_ago": 28},
    ]},
    # Libtayo trial: 4 eligible + 1 ineligible
    {"trial_id": LIBTAYO_TRIAL_ID, "patients": [
        {"id": "libtayo-pt-001", "status": EnrollmentStatus.COMPLETED, "score": 0.97, "days_ago": 58},
        {"id": "libtayo-pt-002", "status": EnrollmentStatus.ACTIVE, "score": 0.91, "days_ago": 42},
        {"id": "libtayo-pt-003", "status": EnrollmentStatus.ENROLLED, "score": 0.84, "days_ago": 25},
        {"id": "libtayo-pt-004", "status": EnrollmentStatus.ELIGIBLE, "score": 0.88, "days_ago": 15},
        {"id": "ineligible-pt-003", "status": EnrollmentStatus.SCREEN_FAILED, "score": 0.38, "days_ago": 32},
    ]},
]

# Criteria met/failed templates
EYLEA_CRITERIA_MET = [
    {"criterion": "Type 2 Diabetes Mellitus", "code": "E11"},
    {"criterion": "Diabetic Macular Edema", "code": "H35.81"},
    {"criterion": "Age >= 18", "value": True},
]
EYLEA_CRITERIA_FAILED_HBA1C = [
    {"criterion": "HbA1c < 12%", "code": "4548-4", "value": "13.2%", "reason": "HbA1c exceeds 12% threshold"},
]
DUPIXENT_CRITERIA_MET = [
    {"criterion": "Atopic Dermatitis", "code": "L20.9"},
    {"criterion": "Age 18-75", "value": True},
    {"criterion": "EASI >= 16", "value": True},
]
DUPIXENT_CRITERIA_FAILED_CANCER = [
    {"criterion": "No active malignancy", "code": "C80.1", "reason": "Active malignant neoplasm"},
]
DUPIXENT_CRITERIA_FAILED_TB = [
    {"criterion": "No active tuberculosis", "code": "A15", "reason": "Active respiratory tuberculosis"},
]
LIBTAYO_CRITERIA_MET = [
    {"criterion": "Cutaneous SCC", "code": "C44.92"},
    {"criterion": "Not amenable to surgery", "value": True},
    {"criterion": "No autoimmune disease", "value": True},
]
LIBTAYO_CRITERIA_FAILED_CTD = [
    {"criterion": "No autoimmune disease", "code": "M35.9", "reason": "Systemic connective tissue disease"},
]


# =============================================================================
# Audit Log Templates
# =============================================================================

AUDIT_ACTIONS = [
    ("create", "patient", True, "POST", "/api/fhir/import"),
    ("create", "document", True, "POST", "/api/documents"),
    ("read", "patient", True, "GET", "/api/patients/{id}"),
    ("read", "document", True, "GET", "/api/documents/{id}"),
    ("read", "clinical_fact", True, "GET", "/api/clinical-facts/{id}"),
    ("search", "patient", False, "GET", "/api/patients"),
    ("search", "document", False, "GET", "/api/documents"),
    ("search", "clinical_fact", False, "GET", "/api/clinical-facts"),
    ("export", "fhir_resource", True, "POST", "/api/fhir/export"),
    ("read", "knowledge_graph", False, "GET", "/api/knowledge-graph/{id}"),
    ("search", "knowledge_graph", False, "GET", "/api/knowledge-graph"),
    ("read", "fhir_resource", True, "GET", "/api/fhir/resources/{id}"),
    ("create", "clinical_fact", True, "POST", "/api/clinical-facts"),
    ("read", "report", False, "GET", "/api/reports/trial-enrollment"),
]

DEMO_USER_IDS = ["demo-user", "dr-smith", "nurse-jones", "admin-user", "researcher-lee"]
SESSION_IDS = [f"session-{i:04d}" for i in range(1, 11)]


# =============================================================================
# Seeding Functions
# =============================================================================


async def _check_demo_data_exists() -> bool:
    """Check if demo data has already been seeded."""
    from sqlalchemy import select

    async with async_session_maker() as session:
        # Check for a known demo document
        result = await session.execute(
            select(Document.id).where(Document.patient_id == "eylea-pt-001").limit(1)
        )
        return result.scalar_one_or_none() is not None


async def seed_documents_and_mentions() -> tuple[int, int, int]:
    """Seed clinical note documents with mentions and concept candidates.

    Returns (doc_count, mention_count, candidate_count).
    """
    doc_count = 0
    mention_count = 0
    candidate_count = 0

    for note_def in CLINICAL_NOTES:
        async with async_session_maker() as session:
            doc_id = str(uuid4())
            doc = Document(
                id=doc_id,
                patient_id=note_def["patient_id"],
                note_type=note_def["note_type"],
                text=note_def["text"],
                extra_metadata={
                    "source": "demo_seed",
                    "note_date": (NOW - timedelta(days=random.randint(1, 30))).isoformat(),
                },
                status=JobStatus.COMPLETED,
                processed_at=NOW - timedelta(days=random.randint(0, 5)),
            )
            session.add(doc)
            doc_count += 1

            full_text = note_def["text"]
            for m_def in note_def["mentions"]:
                mention_text = m_def["text"]
                # Find the actual offset in the document text
                start_offset = full_text.find(mention_text)
                if start_offset == -1:
                    # Try case-insensitive search
                    lower_text = full_text.lower()
                    start_offset = lower_text.find(mention_text.lower())
                if start_offset == -1:
                    logger.warning(
                        f"  Could not find mention '{mention_text}' in document for {note_def['patient_id']}"
                    )
                    continue

                end_offset = start_offset + len(mention_text)
                mention_id = str(uuid4())

                mention = Mention(
                    id=mention_id,
                    document_id=doc_id,
                    text=mention_text,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    lexical_variant=mention_text.lower(),
                    section=m_def.get("section"),
                    assertion=Assertion.PRESENT,
                    temporality=Temporality.CURRENT,
                    experiencer=Experiencer.PATIENT,
                    confidence=round(random.uniform(0.85, 0.99), 3),
                )
                session.add(mention)
                mention_count += 1

                # Add concept candidate
                candidate = MentionConceptCandidate(
                    id=str(uuid4()),
                    mention_id=mention_id,
                    omop_concept_id=m_def["omop_id"],
                    concept_name=m_def["concept_name"],
                    concept_code=m_def["concept_code"],
                    vocabulary_id=m_def["vocab"],
                    domain_id=m_def["domain"],
                    score=round(random.uniform(0.88, 0.99), 3),
                    method="demo_exact_match",
                    rank=1,
                )
                session.add(candidate)
                candidate_count += 1

            await session.commit()

    return doc_count, mention_count, candidate_count


async def seed_trials() -> int:
    """Seed Trial records to the database. Returns count."""
    from sqlalchemy import select

    count = 0
    async with async_session_maker() as session:
        for trial_def in DEMO_TRIALS:
            # Check if trial already exists
            existing = await session.execute(
                select(Trial.id).where(Trial.id == trial_def["id"]).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                logger.info(f"  Trial '{trial_def['name']}' already exists, skipping")
                continue

            trial = Trial(
                id=trial_def["id"],
                name=trial_def["name"],
                nct_number=trial_def["nct_number"],
                protocol_id=trial_def["protocol_id"],
                sponsor=trial_def["sponsor"],
                phase=trial_def["phase"],
                status=trial_def["status"],
                description=trial_def["description"],
                therapeutic_area=trial_def["therapeutic_area"],
                indication_codes=trial_def["indication_codes"],
                enrollment_target=trial_def["enrollment_target"],
                site_count=trial_def["site_count"],
                start_date=NOW - timedelta(days=90),
            )
            session.add(trial)
            count += 1

        await session.commit()
    return count


async def seed_enrollments() -> int:
    """Seed TrialEnrollment records with realistic state transitions. Returns count."""
    count = 0

    async with async_session_maker() as session:
        for config in ENROLLMENT_CONFIGS:
            trial_id = config["trial_id"]

            for p in config["patients"]:
                patient_id = p["id"]
                status = p["status"]
                days_ago = p["days_ago"]

                enrollment_id = str(uuid4())
                screening_date = NOW - timedelta(days=days_ago)
                enrollment_date = None
                withdrawal_date = None

                # Set dates based on status progression
                if status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED):
                    enrollment_date = screening_date + timedelta(days=random.randint(3, 10))
                if status == EnrollmentStatus.COMPLETED:
                    withdrawal_date = enrollment_date + timedelta(days=random.randint(14, 30))

                # Determine criteria met/failed based on trial and patient
                criteria_met = None
                criteria_failed = None
                if trial_id == EYLEA_TRIAL_ID:
                    criteria_met = EYLEA_CRITERIA_MET
                    if status in (EnrollmentStatus.INELIGIBLE, EnrollmentStatus.SCREEN_FAILED):
                        criteria_failed = EYLEA_CRITERIA_FAILED_HBA1C
                elif trial_id == DUPIXENT_TRIAL_ID:
                    criteria_met = DUPIXENT_CRITERIA_MET
                    if patient_id == "ineligible-pt-002":
                        criteria_failed = DUPIXENT_CRITERIA_FAILED_CANCER
                    elif patient_id == "ineligible-pt-004":
                        criteria_failed = DUPIXENT_CRITERIA_FAILED_TB
                elif trial_id == LIBTAYO_TRIAL_ID:
                    criteria_met = LIBTAYO_CRITERIA_MET
                    if status in (EnrollmentStatus.INELIGIBLE, EnrollmentStatus.SCREEN_FAILED):
                        criteria_failed = LIBTAYO_CRITERIA_FAILED_CTD

                enrollment = TrialEnrollment(
                    id=enrollment_id,
                    trial_id=trial_id,
                    patient_id=patient_id,
                    enrollment_status=status,
                    match_score=p["score"],
                    criteria_met=criteria_met,
                    criteria_failed=criteria_failed,
                    screening_date=screening_date,
                    enrollment_date=enrollment_date,
                    withdrawal_date=withdrawal_date,
                    site_id="SITE-001",
                    notes=f"Demo enrollment - seeded {NOW.strftime('%Y-%m-%d')}",
                )
                session.add(enrollment)
                count += 1

        await session.commit()
    return count


async def seed_audit_logs() -> int:
    """Seed AuditLog entries spread over 30 days. Returns count."""
    count = 0

    async with async_session_maker() as session:
        for i in range(80):
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            timestamp = NOW - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

            action_def = random.choice(AUDIT_ACTIONS)
            action_name, resource_type, phi_accessed, method, path = action_def

            patient_id = random.choice(ALL_PATIENT_IDS) if phi_accessed else None
            resource_id = str(uuid4()) if action_name in ("read", "export") else None

            audit = AuditLog(
                id=str(uuid4()),
                timestamp=timestamp,
                user_id=random.choice(DEMO_USER_IDS),
                action=action_name,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=f"10.0.{random.randint(1, 10)}.{random.randint(1, 254)}",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Demo Browser",
                request_id=f"req-{uuid4().hex[:12]}",
                request_method=method,
                request_path=path.replace("{id}", str(uuid4())[:8]) if "{id}" in path else path,
                response_status=200,
                details={"source": "demo_seed", "demo": True},
                phi_accessed=phi_accessed,
                patient_id=patient_id,
                session_id=random.choice(SESSION_IDS),
                success=True,
            )
            session.add(audit)
            count += 1

        # Add a few failed audit entries
        for i in range(5):
            days_ago = random.randint(0, 30)
            timestamp = NOW - timedelta(days=days_ago, hours=random.randint(0, 23))

            audit = AuditLog(
                id=str(uuid4()),
                timestamp=timestamp,
                user_id=random.choice(DEMO_USER_IDS),
                action="auth_failure",
                resource_type="system",
                resource_id=None,
                ip_address=f"192.168.{random.randint(1, 5)}.{random.randint(1, 254)}",
                user_agent="Mozilla/5.0 Unknown Agent",
                request_id=f"req-{uuid4().hex[:12]}",
                request_method="POST",
                request_path="/api/auth/login",
                response_status=401,
                details={"source": "demo_seed", "demo": True, "reason": "invalid_credentials"},
                phi_accessed=False,
                patient_id=None,
                session_id=None,
                success=False,
                error_message="Authentication failed: invalid credentials",
            )
            session.add(audit)
            count += 1

        await session.commit()
    return count


# =============================================================================
# Main Entry Point
# =============================================================================


async def seed_demo_data() -> None:
    """Run all demo data seeders."""
    logger.info("=" * 60)
    logger.info("Clinical Ontology Normalizer - Demo Data Seeder")
    logger.info("=" * 60)

    await init_db()

    doc_count = mention_count = candidate_count = trial_count = enrollment_count = audit_count = 0

    # Step 1: Seed patients via FHIR import pipeline
    logger.info("\n[1/5] Seeding patients via FHIR import...")
    try:
        await seed_trial_patients()
    except Exception as e:
        logger.error(f"FHIR patient import failed: {e}", exc_info=True)
        logger.info("Continuing with remaining seed steps...")

    # Step 2: Seed clinical note documents with mentions (skip if already done)
    if await _check_demo_data_exists():
        logger.info("\n[2/5] Documents already seeded — skipping.")
    else:
        logger.info("\n[2/5] Seeding clinical documents and NLP mentions...")
        doc_count, mention_count, candidate_count = await seed_documents_and_mentions()
        logger.info(f"  Created {doc_count} documents, {mention_count} mentions, {candidate_count} concept candidates")

    # Step 3: Seed trial records to DB (skip if already done)
    from sqlalchemy import select as sa_select, func as sa_func
    async with async_session_maker() as session:
        existing_trials = (await session.execute(sa_select(sa_func.count()).select_from(Trial))).scalar() or 0
    if existing_trials > 0:
        logger.info(f"\n[3/5] Trials already seeded ({existing_trials}) — skipping.")
    else:
        logger.info("\n[3/5] Seeding trial records...")
        trial_count = await seed_trials()
        logger.info(f"  Created {trial_count} trials in database")

    # Step 4: Seed enrollment records (skip if already done)
    async with async_session_maker() as session:
        existing_enrollments = (await session.execute(sa_select(sa_func.count()).select_from(TrialEnrollment))).scalar() or 0
    if existing_enrollments > 0:
        logger.info(f"\n[4/5] Enrollments already seeded ({existing_enrollments}) — skipping.")
    else:
        logger.info("\n[4/5] Seeding trial enrollments...")
        enrollment_count = await seed_enrollments()
        logger.info(f"  Created {enrollment_count} enrollment records")

    # Step 5: Seed audit logs (skip if already done)
    async with async_session_maker() as session:
        existing_audits = (await session.execute(sa_select(sa_func.count()).select_from(AuditLog).where(AuditLog.details.contains({"demo": True})))).scalar() or 0
    if existing_audits > 0:
        logger.info(f"\n[5/5] Audit logs already seeded ({existing_audits}) — skipping.")
    else:
        logger.info("\n[5/5] Seeding audit log entries...")
        audit_count = await seed_audit_logs()
        logger.info(f"  Created {audit_count} audit log entries")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Demo Data Seeding Complete")
    logger.info("=" * 60)
    logger.info(f"  Patients: 18 (via FHIR import)")
    logger.info(f"  Documents: {doc_count}")
    logger.info(f"  Mentions: {mention_count}")
    logger.info(f"  Concept Candidates: {candidate_count}")
    logger.info(f"  Trials: {trial_count}")
    logger.info(f"  Enrollments: {enrollment_count}")
    logger.info(f"  Audit Logs: {audit_count}")
    logger.info("=" * 60)


async def main() -> None:
    """Main entry point."""
    try:
        await seed_demo_data()
    except Exception as e:
        logger.error(f"Demo seeding failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
