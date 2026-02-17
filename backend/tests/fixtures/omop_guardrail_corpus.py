"""UMLS/OMOP precision guardrail corpus for hierarchy string-fallback matching.

ROL-08 / P2-008: This corpus extends the P1-010 acceptance corpus with pairs
specifically designed to test the strict-mode fallback matching in
OMOPHierarchyService._string_fallback_match(). The pairs target clinically
dangerous near-matches that MUST be rejected when Neo4j is unavailable and
the service falls back to string similarity.

The 0.85 Jaccard bigram threshold (P1-008) is the production guardrail.
"""

# ---------------------------------------------------------------------------
# Section 1: False-positive pairs that MUST be REJECTED by strict-mode fallback
# ---------------------------------------------------------------------------
# Format: (patient_term, target_term, rejection_reason)
#
# These pairs share substrings or word overlap but are clinically distinct.
# Accepting any of these would be a patient-safety error.

HIERARCHY_FALSE_POSITIVE_PAIRS: list[tuple[str, str, str]] = [
    # --- Unsafe medication near-matches ---
    (
        "metformin",
        "metronidazole",
        "Diabetes drug vs antibiotic - wrong drug class entirely",
    ),
    (
        "hydralazine",
        "hydroxyzine",
        "Antihypertensive vs antihistamine - different mechanism and indication",
    ),
    (
        "carboplatin",
        "carbamazepine",
        "Platinum chemo agent vs antiepileptic - life-threatening confusion",
    ),
    (
        "prednisone",
        "prednisolone",
        "Different corticosteroids with different bioavailability and dosing",
    ),
    (
        "clonidine",
        "clonazepam",
        "Alpha-agonist antihypertensive vs benzodiazepine anticonvulsant",
    ),
    (
        "vincristine",
        "vinblastine",
        "Different vinca alkaloids with distinct toxicity profiles (neurotoxic vs myelosuppressive)",
    ),
    # --- Condition word-overlap false positives ---
    (
        "type 1 diabetes",
        "type 2 diabetes",
        "Autoimmune vs metabolic diabetes - fundamentally different pathology and treatment",
    ),
    (
        "pulmonary hypertension",
        "essential hypertension",
        "Pulmonary vascular disease vs systemic hypertension - different organs and treatment",
    ),
    (
        "small cell lung cancer",
        "non-small cell lung cancer",
        "Distinct cancer subtypes with completely different staging, treatment, and prognosis",
    ),
    (
        "acute pancreatitis",
        "chronic pancreatitis",
        "Acute inflammatory emergency vs chronic fibrotic disease - different management",
    ),
    (
        "chronic kidney disease",
        "polycystic kidney disease",
        "General CKD vs specific genetic etiology - different monitoring and treatment",
    ),
    # --- Ambiguous single-token overlap ---
    (
        "chest pain",
        "chest tube",
        "Symptom vs procedure - completely unrelated clinical concepts sharing 'chest'",
    ),
]

# ---------------------------------------------------------------------------
# Section 2: Pairs that MUST be ACCEPTED (exact string matches)
# ---------------------------------------------------------------------------
# Format: (patient_term, target_term, acceptance_reason)
#
# Exact matches should always pass regardless of mode.

HIERARCHY_MUST_ACCEPT_PAIRS: list[tuple[str, str, str]] = [
    (
        "pneumonia",
        "pneumonia",
        "Exact match - same condition term",
    ),
    (
        "essential hypertension",
        "essential hypertension",
        "Exact match - multi-word condition",
    ),
    (
        "type 2 diabetes mellitus",
        "type 2 diabetes mellitus",
        "Exact match - multi-word condition with qualifier",
    ),
    (
        "aspirin",
        "aspirin",
        "Exact match - medication",
    ),
    (
        "acute myocardial infarction",
        "acute myocardial infarction",
        "Exact match - multi-word acute condition",
    ),
    (
        "serum creatinine",
        "serum creatinine",
        "Exact match - lab measurement",
    ),
]

# ---------------------------------------------------------------------------
# Section 3: Similarity boundary cases around the 0.85 threshold
# ---------------------------------------------------------------------------
# Format: (str_a, str_b, min_expected_similarity, max_expected_similarity, description)
#
# These test the Jaccard bigram similarity computation near the decision
# boundary. Values are empirically determined against the implementation.

SIMILARITY_BOUNDARY_CASES: list[tuple[str, str, float, float, str]] = [
    (
        "metformin",
        "metformin",
        1.0,
        1.0,
        "Identical strings must score 1.0",
    ),
    (
        "",
        "metformin",
        0.0,
        0.0,
        "Empty string must score 0.0",
    ),
    (
        "a",
        "b",
        0.0,
        0.0,
        "Single-char mismatch must score 0.0",
    ),
    (
        "metformin",
        "metronidazole",
        0.0,
        0.40,
        "Dangerous drug pair must score well below 0.85 threshold",
    ),
    (
        "prednisone",
        "prednisolone",
        0.75,
        0.84,
        "Corticosteroid pair must score below 0.85 threshold",
    ),
    (
        "aspirin",
        "aspirin tablet",
        0.40,
        0.84,
        "Near-match with qualifier should score below 0.85 threshold",
    ),
]

# ---------------------------------------------------------------------------
# Section 4: Ambiguous mapping pairs requiring reject/downgrade/review
# ---------------------------------------------------------------------------
# Format: (input_text, plausible_concept_id, correct_action, reason_code)
#
# Actions:
#   reject         — must NOT appear as top match
#   downgrade      — may appear but match_quality must NOT be "exact"
#   flag_for_review — mapper may return but should emit a review flag
#
# Reason codes:
#   LASA_DRUG              — Look-Alike Sound-Alike drug confusion
#   UNQUALIFIED_CONDITION  — Ambiguous condition lacking required qualifier
#   ABBREVIATION_COLLISION — Clinical abbreviation with multiple expansions
#   SPECIMEN_AMBIGUITY     — Same analyte in different specimen contexts
#   CROSS_DOMAIN_COLLISION — Term exists in multiple OMOP domains

VALID_AMBIGUOUS_ACTIONS = {"reject", "downgrade", "flag_for_review"}
VALID_REASON_CODES = {
    "LASA_DRUG",
    "UNQUALIFIED_CONDITION",
    "ABBREVIATION_COLLISION",
    "SPECIMEN_AMBIGUITY",
    "CROSS_DOMAIN_COLLISION",
}

GUARDRAIL_AMBIGUOUS_PAIRS: list[tuple[str, int, str, str]] = [
    # --- LASA drugs ---
    (
        "losartan",
        1308216,  # lisinopril — different RAAS mechanism (ARB vs ACE-I)
        "reject",
        "LASA_DRUG",
    ),
    (
        "cephalexin",
        1713332,  # amoxicillin — different antibiotic class
        "reject",
        "LASA_DRUG",
    ),
    (
        "hydroxychloroquine",
        1177480,  # ibuprofen — antimalarial/DMARD vs NSAID
        "reject",
        "LASA_DRUG",
    ),
    (
        "omeprazole",
        1545958,  # atorvastatin — PPI vs statin
        "reject",
        "LASA_DRUG",
    ),
    # --- Unqualified conditions ---
    (
        "diabetes",
        201826,  # Type 2 diabetes mellitus — unqualified, could be type 1 or 2
        "flag_for_review",
        "UNQUALIFIED_CONDITION",
    ),
    (
        "hypertension",
        320128,  # Essential hypertension — could be secondary or pulmonary
        "flag_for_review",
        "UNQUALIFIED_CONDITION",
    ),
    (
        "anemia",
        255848,  # Pneumonia — totally wrong domain, dangerous
        "reject",
        "UNQUALIFIED_CONDITION",
    ),
    # --- Abbreviation collisions ---
    (
        "MS",
        312327,  # Acute MI — abbreviation collision (MS = multiple sclerosis, mitral stenosis, morphine sulfate)
        "reject",
        "ABBREVIATION_COLLISION",
    ),
    (
        "PE",
        255848,  # Pneumonia — PE = pulmonary embolism, physical exam, pleural effusion
        "reject",
        "ABBREVIATION_COLLISION",
    ),
    (
        "RA",
        320128,  # Essential hypertension — RA = rheumatoid arthritis, right atrium
        "reject",
        "ABBREVIATION_COLLISION",
    ),
    # --- Specimen ambiguity ---
    (
        "urine glucose",
        3004410,  # Hemoglobin A1c — wrong analyte entirely
        "reject",
        "SPECIMEN_AMBIGUITY",
    ),
    (
        "urine sodium",
        3016723,  # Serum creatinine — different analyte and specimen
        "reject",
        "SPECIMEN_AMBIGUITY",
    ),
    # --- Cross-domain collisions ---
    (
        "aspirin allergy",
        1112807,  # aspirin (Drug) — allergy is a Condition, not a Drug
        "reject",
        "CROSS_DOMAIN_COLLISION",
    ),
    (
        "insulin resistance",
        1503297,  # metformin (Drug) — insulin resistance is a Condition
        "reject",
        "CROSS_DOMAIN_COLLISION",
    ),
    (
        "colonoscopy finding",
        4249893,  # Colonoscopy (Procedure) — finding is an Observation, not a Procedure
        "downgrade",
        "CROSS_DOMAIN_COLLISION",
    ),
]

# ---------------------------------------------------------------------------
# Section 5: Per-domain positive pairs for precision gate testing
# ---------------------------------------------------------------------------
# Format per domain: list of (input_text, expected_concept_id, expected_concept_name)

DOMAIN_POSITIVE_PAIRS: dict[str, list[tuple[str, int, str]]] = {
    "medication": [
        ("aspirin", 1112807, "aspirin"),
        ("metformin", 1503297, "metformin"),
        ("lisinopril", 1308216, "lisinopril"),
        ("atorvastatin", 1545958, "atorvastatin"),
        ("amoxicillin", 1713332, "amoxicillin"),
        ("omeprazole", 948078, "omeprazole"),
        ("ibuprofen", 1177480, "ibuprofen"),
        ("warfarin", 1310149, "warfarin"),
    ],
    "condition": [
        ("type 2 diabetes mellitus", 201826, "Type 2 diabetes mellitus"),
        ("essential hypertension", 320128, "Essential hypertension"),
        ("pneumonia", 255848, "Pneumonia"),
        ("acute myocardial infarction", 312327, "Acute myocardial infarction"),
        ("major depressive disorder", 440383, "Major depressive disorder"),
        ("asthma", 317009, "Asthma"),
        ("chronic kidney disease", 46271022, "Chronic kidney disease"),
        ("heart failure", 316139, "Heart failure"),
    ],
    "procedure": [
        ("CT scan", 4305080, "Computed tomography"),
        ("MRI", 4013636, "Magnetic resonance imaging"),
        ("blood draw", 4091529, "Phlebotomy"),
        ("colonoscopy", 4249893, "Colonoscopy"),
        ("echocardiogram", 4096099, "Echocardiography"),
        ("chest x-ray", 4058286, "Chest X-ray"),
        ("EKG", 4152194, "Electrocardiogram"),
    ],
    "measurement": [
        ("complete blood count", 3000963, "Complete blood count"),
        ("basic metabolic panel", 3019550, "Basic metabolic panel"),
        ("hemoglobin A1c", 3004410, "Hemoglobin A1c"),
        ("lipid panel", 3027114, "Lipid panel"),
        ("serum creatinine", 3016723, "Creatinine in serum"),
        ("blood urea nitrogen", 3013682, "Blood urea nitrogen"),
        ("thyroid stimulating hormone", 3019170, "TSH"),
    ],
}

# ---------------------------------------------------------------------------
# Section 6: Per-domain precision thresholds
# ---------------------------------------------------------------------------
# Medications have the highest threshold because drug confusion is
# the most directly dangerous mapping error.

DOMAIN_PRECISION_THRESHOLDS: dict[str, float] = {
    "medication": 0.90,
    "condition": 0.80,
    "procedure": 0.75,
    "measurement": 0.80,
}
