#!/usr/bin/env python3
"""Seed 7 additional Regeneron pipeline clinical trials into the database.

Adds trials with realistic inclusion/exclusion criteria using proper
criteria JSON structure (criterion_type, codes with display terms, code_system)
that the TrialEligibilityService can evaluate via ILIKE matching.

Idempotent: checks for existing trials by stable UUID before inserting.

Usage:
    cd backend && uv run python3 -m scripts.seed_regeneron_pipeline_trials
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path if running directly
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.database import async_session_maker, init_db  # noqa: E402
from app.models.trial import (  # noqa: E402
    Trial,
    TrialPhase,
    TrialStatus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

NOW = datetime.now(timezone.utc)

# Stable UUIDs for each pipeline trial (predictable across runs)
FIANLIMAB_MELANOMA_ID = "00000000-de00-0004-0000-000000000004"
LINVOSELTAMAB_MM_ID = "00000000-de00-0005-0000-000000000005"
ODRONEXTAMAB_FL_ID = "00000000-de00-0006-0000-000000000006"
ITEPEKIMAB_COPD_ID = "00000000-de00-0007-0000-000000000007"
DUPILUMAB_BP_ID = "00000000-de00-0008-0000-000000000008"
POZELIMAB_MG_ID = "00000000-de00-0009-0000-000000000009"
CEMIPLIMAB_ADJ_CSCC_ID = "00000000-de00-0010-0000-000000000010"

# ============================================================================
# Trial Definitions - 7 Regeneron Pipeline Trials
# ============================================================================

PIPELINE_TRIALS = [
    # ---- 1. Fianlimab + Cemiplimab (Melanoma) ----
    {
        "id": FIANLIMAB_MELANOMA_ID,
        "name": "HARMONY - Fianlimab + Cemiplimab for Advanced Melanoma",
        "nct_number": "NCT05352672",
        "protocol_id": "REGN3767-MEL-3001",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": (
            "A phase 3, randomized, double-blind study of fianlimab (anti-LAG-3) in "
            "combination with cemiplimab (anti-PD-1) versus pembrolizumab monotherapy "
            "as first-line treatment in patients with unresectable locally advanced or "
            "metastatic melanoma."
        ),
        "therapeutic_area": "Oncology",
        "indication_codes": ["C43.9", "C43.0"],
        "enrollment_target": 1100,
        "site_count": 350,
        "start_date": NOW - timedelta(days=900),
        "end_date": NOW + timedelta(days=540),
        "inclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "demographic",
                    "name": "Adult patients",
                    "age_range": {"min_age": 18},
                },
                {
                    "criterion_type": "condition",
                    "name": "Melanoma",
                    "codes": [
                        {"code": "C43.9", "display": "Malignant melanoma of skin, unspecified"},
                        {"code": "C43.0", "display": "Malignant melanoma of lip"},
                        {"code": "172.9", "display": "Melanoma of skin, unspecified site"},
                    ],
                    "code_system": "ICD10CM",
                },
                {
                    "criterion_type": "condition",
                    "name": "Unresectable or metastatic disease",
                    "codes": [
                        {"code": "C78.7", "display": "Secondary malignant neoplasm of liver"},
                        {"code": "C79.9", "display": "Secondary malignant neoplasm, unspecified"},
                    ],
                    "code_system": "ICD10CM",
                },
            ],
            "root_operator": "AND",
        },
        "exclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Uveal melanoma",
                    "codes": [
                        {"code": "C69.3", "display": "Malignant neoplasm of choroid"},
                        {"code": "190.6", "display": "Uveal melanoma"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Active autoimmune disease",
                    "codes": [
                        {"code": "M35.9", "display": "Systemic involvement of connective tissue"},
                        {"code": "M32.9", "display": "Systemic lupus erythematosus"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Active brain metastases",
                    "codes": [
                        {"code": "C79.31", "display": "Secondary malignant neoplasm of brain"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
            ],
            "root_operator": "AND",
        },
    },
    # ---- 2. Linvoseltamab (Multiple Myeloma) ----
    {
        "id": LINVOSELTAMAB_MM_ID,
        "name": "LINKER-MM3 - Linvoseltamab for R/R Multiple Myeloma",
        "nct_number": "NCT05730036",
        "protocol_id": "REGN5458-MM-3001",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": (
            "A phase 3, randomized, open-label study comparing linvoseltamab (REGN5458), "
            "a BCMAxCD3 bispecific antibody, versus elotuzumab/pomalidomide/dexamethasone "
            "in patients with relapsed/refractory multiple myeloma who have received 1-3 "
            "prior lines of therapy."
        ),
        "therapeutic_area": "Oncology - Hematology",
        "indication_codes": ["C90.0", "C90.00", "C90.01"],
        "enrollment_target": 450,
        "site_count": 180,
        "start_date": NOW - timedelta(days=540),
        "end_date": NOW + timedelta(days=730),
        "inclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "demographic",
                    "name": "Adult patients",
                    "age_range": {"min_age": 18},
                },
                {
                    "criterion_type": "condition",
                    "name": "Multiple Myeloma",
                    "codes": [
                        {"code": "C90.0", "display": "Multiple myeloma"},
                        {"code": "C90.00", "display": "Multiple myeloma not having achieved remission"},
                        {"code": "C90.01", "display": "Multiple myeloma in remission"},
                        {"code": "203.00", "display": "Multiple myeloma"},
                    ],
                    "code_system": "ICD10CM",
                },
                {
                    "criterion_type": "measurement",
                    "name": "Measurable serum M-protein",
                    "codes": [
                        {"code": "33358-3", "display": "Protein electrophoresis panel"},
                        {"code": "2639-3", "display": "M-protein serum"},
                    ],
                    "code_system": "LOINC",
                },
            ],
            "root_operator": "AND",
        },
        "exclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Active CNS involvement",
                    "codes": [
                        {"code": "C79.31", "display": "Secondary malignant neoplasm of brain"},
                        {"code": "C79.32", "display": "Secondary malignant neoplasm of cerebral meninges"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Active autoimmune disease",
                    "codes": [
                        {"code": "M35.9", "display": "Systemic involvement of connective tissue"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "procedure",
                    "name": "Prior allogeneic stem cell transplant within 6 months",
                    "codes": [
                        {"code": "41.00", "display": "Bone marrow transplant"},
                        {"code": "0076070", "display": "Allogeneic hematopoietic stem cell transplant"},
                    ],
                    "code_system": "SNOMED",
                    "negated": True,
                },
            ],
            "root_operator": "AND",
        },
    },
    # ---- 3. Odronextamab (Follicular Lymphoma) ----
    {
        "id": ODRONEXTAMAB_FL_ID,
        "name": "OLYMPIA-2 - Odronextamab for Frontline Follicular Lymphoma",
        "nct_number": "NCT06300003",
        "protocol_id": "REGN1979-FL-3002",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": (
            "A phase 3, randomized, open-label study of odronextamab (CD20xCD3 bispecific) "
            "in combination with chemotherapy versus rituximab plus chemotherapy as first-line "
            "treatment in patients with follicular lymphoma."
        ),
        "therapeutic_area": "Oncology - Hematology",
        "indication_codes": ["C82.0", "C82.1", "C82.9"],
        "enrollment_target": 500,
        "site_count": 200,
        "start_date": NOW - timedelta(days=300),
        "end_date": NOW + timedelta(days=900),
        "inclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "demographic",
                    "name": "Adult patients",
                    "age_range": {"min_age": 18},
                },
                {
                    "criterion_type": "condition",
                    "name": "Follicular Lymphoma",
                    "codes": [
                        {"code": "C82.0", "display": "Follicular lymphoma grade I"},
                        {"code": "C82.1", "display": "Follicular lymphoma grade II"},
                        {"code": "C82.9", "display": "Follicular lymphoma, unspecified"},
                    ],
                    "code_system": "ICD10CM",
                },
                {
                    "criterion_type": "measurement",
                    "name": "Adequate hematologic function",
                    "codes": [
                        {"code": "6690-2", "display": "WBC count"},
                        {"code": "26515-7", "display": "Platelets"},
                        {"code": "718-7", "display": "Hemoglobin"},
                    ],
                    "code_system": "LOINC",
                },
            ],
            "root_operator": "AND",
        },
        "exclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Transformed lymphoma",
                    "codes": [
                        {"code": "C83.3", "display": "Diffuse large B-cell lymphoma"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Active hepatitis B or C",
                    "codes": [
                        {"code": "B18.1", "display": "Chronic viral hepatitis B"},
                        {"code": "B18.2", "display": "Chronic viral hepatitis C"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Active CNS lymphoma",
                    "codes": [
                        {"code": "C85.1", "display": "B-cell lymphoma, unspecified, of central nervous system"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
            ],
            "root_operator": "AND",
        },
    },
    # ---- 4. Itepekimab (COPD) ----
    {
        "id": ITEPEKIMAB_COPD_ID,
        "name": "AERIFY-1 - Itepekimab for Moderate-to-Severe COPD",
        "nct_number": "NCT04701983",
        "protocol_id": "REGN3500-COPD-3001",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": (
            "A phase 3, randomized, double-blind, placebo-controlled study evaluating "
            "itepekimab (anti-IL-33) in former smokers with moderate-to-severe chronic "
            "obstructive pulmonary disease (COPD) despite standard inhaled therapy."
        ),
        "therapeutic_area": "Respiratory",
        "indication_codes": ["J44.1", "J44.0", "J44.9"],
        "enrollment_target": 900,
        "site_count": 300,
        "start_date": NOW - timedelta(days=600),
        "end_date": NOW + timedelta(days=500),
        "inclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "demographic",
                    "name": "Adult patients aged 40-85",
                    "age_range": {"min_age": 40, "max_age": 85},
                },
                {
                    "criterion_type": "condition",
                    "name": "COPD",
                    "codes": [
                        {"code": "J44.1", "display": "Chronic obstructive pulmonary disease with acute exacerbation"},
                        {"code": "J44.0", "display": "Chronic obstructive pulmonary disease with acute lower respiratory infection"},
                        {"code": "J44.9", "display": "Chronic obstructive pulmonary disease, unspecified"},
                    ],
                    "code_system": "ICD10CM",
                },
                {
                    "criterion_type": "measurement",
                    "name": "Post-bronchodilator FEV1/FVC ratio < 0.70",
                    "codes": [
                        {"code": "19926-5", "display": "FEV1/FVC"},
                        {"code": "20150-9", "display": "FEV1"},
                    ],
                    "code_system": "LOINC",
                },
                {
                    "criterion_type": "measurement",
                    "name": "Blood eosinophil count >= 300 cells/uL",
                    "codes": [
                        {"code": "26449-9", "display": "Eosinophils"},
                        {"code": "711-2", "display": "Eosinophils count"},
                    ],
                    "code_system": "LOINC",
                    "value_range": {"min_value": 300},
                },
            ],
            "root_operator": "AND",
        },
        "exclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Current asthma diagnosis",
                    "codes": [
                        {"code": "J45.20", "display": "Mild intermittent asthma"},
                        {"code": "J45.50", "display": "Severe persistent asthma"},
                        {"code": "J45.909", "display": "Unspecified asthma"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Active pulmonary tuberculosis",
                    "codes": [
                        {"code": "A15", "display": "Respiratory tuberculosis"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Lung cancer",
                    "codes": [
                        {"code": "C34.9", "display": "Malignant neoplasm of bronchus and lung"},
                        {"code": "C34.90", "display": "Malignant neoplasm of unspecified part of bronchus or lung"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
            ],
            "root_operator": "AND",
        },
    },
    # ---- 5. Dupilumab (Bullous Pemphigoid) ----
    {
        "id": DUPILUMAB_BP_ID,
        "name": "LIBERTY-BP - Dupilumab for Bullous Pemphigoid",
        "nct_number": "NCT04206553",
        "protocol_id": "R668-AD-1747",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_2_3,
        "status": TrialStatus.RECRUITING,
        "description": (
            "A phase 2/3, randomized, double-blind, placebo-controlled study evaluating "
            "dupilumab in adult patients with bullous pemphigoid (BP) who are inadequately "
            "controlled with or intolerant to oral corticosteroids."
        ),
        "therapeutic_area": "Dermatology - Autoimmune",
        "indication_codes": ["L12.0"],
        "enrollment_target": 150,
        "site_count": 90,
        "start_date": NOW - timedelta(days=480),
        "end_date": NOW + timedelta(days=365),
        "inclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "demographic",
                    "name": "Adult patients",
                    "age_range": {"min_age": 18},
                },
                {
                    "criterion_type": "condition",
                    "name": "Bullous Pemphigoid",
                    "codes": [
                        {"code": "L12.0", "display": "Bullous pemphigoid"},
                        {"code": "694.5", "display": "Pemphigoid"},
                    ],
                    "code_system": "ICD10CM",
                },
                {
                    "criterion_type": "measurement",
                    "name": "Positive anti-BP180 or anti-BP230 antibodies",
                    "codes": [
                        {"code": "56718-4", "display": "BP180 antibody"},
                        {"code": "56719-2", "display": "BP230 antibody"},
                    ],
                    "code_system": "LOINC",
                },
            ],
            "root_operator": "AND",
        },
        "exclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Active malignancy",
                    "codes": [
                        {"code": "C80.1", "display": "Malignant neoplasm, unspecified"},
                        {"code": "C80", "display": "malignant"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Other autoimmune blistering disease",
                    "codes": [
                        {"code": "L10.0", "display": "Pemphigus vulgaris"},
                        {"code": "L10.1", "display": "Pemphigus vegetans"},
                        {"code": "L12.2", "display": "Chronic bullous disease of childhood"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Active parasitic infection",
                    "codes": [
                        {"code": "B83.9", "display": "Helminthiasis, unspecified"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
            ],
            "root_operator": "AND",
        },
    },
    # ---- 6. Pozelimab (Myasthenia Gravis) ----
    {
        "id": POZELIMAB_MG_ID,
        "name": "NIMBLE - Pozelimab + Cemdisiran for Generalized Myasthenia Gravis",
        "nct_number": "NCT06400004",
        "protocol_id": "REGN3918-MG-3001",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": (
            "A phase 3, randomized, double-blind, placebo-controlled study evaluating "
            "pozelimab (anti-C5) plus cemdisiran (C5-targeting siRNA) versus placebo in "
            "adults with generalized myasthenia gravis (gMG) who are anti-AChR antibody positive."
        ),
        "therapeutic_area": "Immunology - Neurology",
        "indication_codes": ["G70.00", "G70.01"],
        "enrollment_target": 200,
        "site_count": 100,
        "start_date": NOW - timedelta(days=400),
        "end_date": NOW + timedelta(days=365),
        "inclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "demographic",
                    "name": "Adult patients",
                    "age_range": {"min_age": 18},
                },
                {
                    "criterion_type": "condition",
                    "name": "Generalized Myasthenia Gravis",
                    "codes": [
                        {"code": "G70.00", "display": "Myasthenia gravis without exacerbation"},
                        {"code": "G70.01", "display": "Myasthenia gravis with exacerbation"},
                        {"code": "358.00", "display": "Myasthenia gravis"},
                    ],
                    "code_system": "ICD10CM",
                },
                {
                    "criterion_type": "measurement",
                    "name": "Anti-AChR antibody positive",
                    "codes": [
                        {"code": "11560-5", "display": "Acetylcholine receptor binding antibody"},
                        {"code": "30178-1", "display": "Acetylcholine receptor antibody"},
                    ],
                    "code_system": "LOINC",
                },
            ],
            "root_operator": "AND",
        },
        "exclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Myasthenic crisis within 4 weeks",
                    "codes": [
                        {"code": "G70.01", "display": "Myasthenia gravis with exacerbation"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "procedure",
                    "name": "Thymectomy within 12 months",
                    "codes": [
                        {"code": "07550ZZ", "display": "Destruction of thymus"},
                        {"code": "7.80", "display": "Thymectomy"},
                    ],
                    "code_system": "SNOMED",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Meningococcal infection",
                    "codes": [
                        {"code": "A39", "display": "Meningococcal infection"},
                        {"code": "A39.0", "display": "Meningococcal meningitis"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
            ],
            "root_operator": "AND",
        },
    },
    # ---- 7. Cemiplimab Adjuvant (CSCC) ----
    {
        "id": CEMIPLIMAB_ADJ_CSCC_ID,
        "name": "LIBTAYO Adjuvant - Cemiplimab for High-Risk Resected CSCC",
        "nct_number": "NCT04154943",
        "protocol_id": "R2810-ONC-1788",
        "sponsor": "Regeneron Pharmaceuticals",
        "phase": TrialPhase.PHASE_3,
        "status": TrialStatus.RECRUITING,
        "description": (
            "A phase 3, randomized, double-blind, placebo-controlled study evaluating "
            "cemiplimab as adjuvant treatment in patients with high-risk cutaneous "
            "squamous cell carcinoma (CSCC) following surgery and optional radiation."
        ),
        "therapeutic_area": "Oncology - Dermatology",
        "indication_codes": ["C44.92", "C44.9"],
        "enrollment_target": 412,
        "site_count": 160,
        "start_date": NOW - timedelta(days=720),
        "end_date": NOW + timedelta(days=400),
        "inclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "demographic",
                    "name": "Adult patients",
                    "age_range": {"min_age": 18},
                },
                {
                    "criterion_type": "condition",
                    "name": "Cutaneous Squamous Cell Carcinoma",
                    "codes": [
                        {"code": "C44.92", "display": "Squamous cell carcinoma of skin, unspecified"},
                        {"code": "C44.9", "display": "Malignant neoplasm of skin, unspecified"},
                    ],
                    "code_system": "ICD10CM",
                },
                {
                    "criterion_type": "procedure",
                    "name": "Complete surgical resection",
                    "codes": [
                        {"code": "86.4", "display": "Radical excision of skin lesion"},
                        {"code": "71388002", "display": "Skin biopsy"},
                    ],
                    "code_system": "SNOMED",
                },
            ],
            "root_operator": "AND",
        },
        "exclusion_criteria": {
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Distant metastatic disease",
                    "codes": [
                        {"code": "C79.9", "display": "Secondary malignant neoplasm, unspecified"},
                        {"code": "C78.7", "display": "Secondary malignant neoplasm of liver"},
                        {"code": "C78.0", "display": "Secondary malignant neoplasm of lung"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Autoimmune disease requiring systemic treatment",
                    "codes": [
                        {"code": "M35.9", "display": "Systemic involvement of connective tissue"},
                        {"code": "M32.9", "display": "Systemic lupus erythematosus"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
                {
                    "criterion_type": "condition",
                    "name": "Organ transplant recipient",
                    "codes": [
                        {"code": "Z94.0", "display": "Kidney transplant status"},
                        {"code": "Z94.1", "display": "Heart transplant status"},
                        {"code": "Z94.4", "display": "Liver transplant status"},
                    ],
                    "code_system": "ICD10CM",
                    "negated": True,
                },
            ],
            "root_operator": "AND",
        },
    },
]


async def seed_pipeline_trials() -> None:
    """Seed 7 Regeneron pipeline trials. Idempotent by stable UUID.

    If a trial with the same NCT number exists under a different UUID,
    it is deleted first and re-created with the correct stable UUID and
    proper criteria JSON structure.
    """
    from sqlalchemy import delete, select

    logger.info("=" * 60)
    logger.info("Regeneron Pipeline Trials Seeder (7 trials)")
    logger.info("=" * 60)

    # Initialize DB
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"init_db() warning (may be duplicate index): {e}")

    inserted = 0
    updated = 0
    skipped = 0

    async with async_session_maker() as session:
        for trial_def in PIPELINE_TRIALS:
            trial_id = trial_def["id"]
            nct = trial_def["nct_number"]

            # Check if trial already exists with the correct stable UUID
            result = await session.execute(
                select(Trial.id).where(Trial.id == trial_id).limit(1)
            )
            if result.scalar_one_or_none() is not None:
                logger.info(f"  SKIP (exists with correct UUID): {trial_def['name']}")
                skipped += 1
                continue

            # Check if a trial with the same NCT number exists under a
            # different UUID (from the earlier seed_regeneron_trials.py)
            result = await session.execute(
                select(Trial.id).where(Trial.nct_number == nct).limit(1)
            )
            old_id = result.scalar_one_or_none()
            if old_id is not None:
                # Delete the old trial so we can re-create with stable UUID
                await session.execute(
                    delete(Trial).where(Trial.id == old_id)
                )
                logger.info(f"  REPLACE: removed old UUID {old_id} for [{nct}]")
                updated += 1

            trial = Trial(
                id=trial_id,
                name=trial_def["name"],
                nct_number=trial_def["nct_number"],
                protocol_id=trial_def["protocol_id"],
                sponsor=trial_def["sponsor"],
                phase=trial_def["phase"],
                status=trial_def["status"],
                description=trial_def["description"],
                therapeutic_area=trial_def["therapeutic_area"],
                indication_codes=trial_def["indication_codes"],
                inclusion_criteria=trial_def["inclusion_criteria"],
                exclusion_criteria=trial_def["exclusion_criteria"],
                enrollment_target=trial_def["enrollment_target"],
                site_count=trial_def["site_count"],
                start_date=trial_def["start_date"],
                end_date=trial_def["end_date"],
            )
            session.add(trial)
            inserted += 1
            logger.info(f"  ADD: {trial_def['name']} [{nct}]")

        await session.commit()

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Done. Inserted: {inserted}, Replaced: {updated}, Skipped: {skipped}")
    logger.info("=" * 60)


async def fix_legacy_criteria() -> None:
    """Fix older trials that have criteria stored as list instead of dict.

    The TrialCreate schema expects criteria as dict (with 'criteria' and
    'root_operator' keys). Older seed_regeneron_trials.py stored them as
    plain lists, which causes TrialCreate validation to fail and prevents
    load_from_db from completing.
    """
    from sqlalchemy import select, update

    logger.info("Checking for legacy criteria format (list -> dict)...")
    fixed = 0

    async with async_session_maker() as session:
        result = await session.execute(
            select(Trial).where(Trial.deleted_at.is_(None))
        )
        trials = result.scalars().all()

        for t in trials:
            needs_fix = False
            inc = t.inclusion_criteria
            exc = t.exclusion_criteria

            if isinstance(inc, list):
                inc = {"criteria": inc, "root_operator": "AND"}
                needs_fix = True
            if isinstance(exc, list):
                exc = {"criteria": exc, "root_operator": "AND"}
                needs_fix = True

            if needs_fix:
                await session.execute(
                    update(Trial)
                    .where(Trial.id == t.id)
                    .values(
                        inclusion_criteria=inc,
                        exclusion_criteria=exc,
                    )
                )
                fixed += 1
                logger.info(f"  FIXED criteria format: {t.name}")

        if fixed:
            await session.commit()

    logger.info(f"Fixed {fixed} trials with legacy criteria format")


async def main() -> None:
    try:
        await seed_pipeline_trials()
        await fix_legacy_criteria()
    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
