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
