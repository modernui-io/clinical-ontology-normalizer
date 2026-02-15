"""OMOP acceptance corpus for mapping quality validation.

P1-010: Provides positive and negative concept pairs for verifying
that the OMOP mapping pipeline correctly maps clinical terms to
standard OMOP concept IDs and rejects known false positives.

OMOP concept IDs reference the OHDSI OMOP CDM vocabulary.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Positive pairs: (input_text, expected_concept_id, expected_concept_name)
# These represent known-correct mappings the system MUST produce.
# ---------------------------------------------------------------------------

POSITIVE_PAIRS: list[tuple[str, int, str]] = [
    # --- Medications (Drug domain) ---
    ("aspirin", 1112807, "aspirin"),
    ("metformin", 1503297, "metformin"),
    ("lisinopril", 1308216, "lisinopril"),
    ("atorvastatin", 1545958, "atorvastatin"),
    ("amoxicillin", 1713332, "amoxicillin"),
    ("omeprazole", 948078, "omeprazole"),
    ("ibuprofen", 1177480, "ibuprofen"),
    # --- Conditions (Condition domain) ---
    ("type 2 diabetes mellitus", 201826, "Type 2 diabetes mellitus"),
    ("essential hypertension", 320128, "Essential hypertension"),
    ("pneumonia", 255848, "Pneumonia"),
    ("acute myocardial infarction", 312327, "Acute myocardial infarction"),
    ("major depressive disorder", 440383, "Major depressive disorder"),
    ("asthma", 317009, "Asthma"),
    ("chronic kidney disease", 46271022, "Chronic kidney disease"),
    # --- Procedures (Procedure domain) ---
    ("CT scan", 4305080, "Computed tomography"),
    ("MRI", 4013636, "Magnetic resonance imaging"),
    ("blood draw", 4091529, "Phlebotomy"),
    ("colonoscopy", 4249893, "Colonoscopy"),
    ("echocardiogram", 4096099, "Echocardiography"),
    # --- Lab tests (Measurement domain) ---
    ("complete blood count", 3000963, "Complete blood count"),
    ("basic metabolic panel", 3019550, "Basic metabolic panel"),
    ("hemoglobin A1c", 3004410, "Hemoglobin A1c"),
    ("lipid panel", 3027114, "Lipid panel"),
    ("serum creatinine", 3016723, "Creatinine in serum"),
]

# ---------------------------------------------------------------------------
# Negative pairs: (input_text, should_not_match_concept_id)
# These represent known FALSE POSITIVE mappings the system should avoid.
# ---------------------------------------------------------------------------

NEGATIVE_PAIRS: list[tuple[str, int]] = [
    # "cold" (common cold) should NOT map to "cold sensation" or temperature
    ("cold", 4295459),  # should not map to Cold sensation
    # "depression" should NOT map to a geographic depression or bone depression
    ("depression", 4129524),  # should not map to Depressed skull fracture
    # "discharge" (hospital discharge) should NOT map to wound discharge
    ("discharge", 4091513),  # should not map to Wound discharge
    # "lead" (lead poisoning) should NOT map to ECG lead
    ("lead", 4171274),  # should not map to ECG lead
    # "mass" should NOT map to body mass/weight
    ("mass", 4146832),  # should not map to Body mass index
    # "growth" should NOT map to child growth (when context is tumor)
    ("growth", 4047133),  # should not map to Growth finding
    # "culture" should NOT map to cultural background
    ("culture", 4197167),  # should not map to Cultural background finding
    # "block" should NOT map to nerve block (when context is heart block)
    ("heart block", 4169095),  # should not map to Nerve block
    # "fluid" should NOT map to IV fluid (when context is pleural fluid)
    ("pleural fluid", 4171440),  # should not map to Intravenous fluid
    # "resistance" should NOT map to drug resistance (when context is insulin)
    ("insulin resistance", 437264),  # should not map to Drug resistance
    # "failure" alone should NOT map to heart failure
    ("failure", 316139),  # should not map to Heart failure
    # "positive" alone should NOT map to HIV positive
    ("positive", 4030840),  # should not map to HIV positive
]
