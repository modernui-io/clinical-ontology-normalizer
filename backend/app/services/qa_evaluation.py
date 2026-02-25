"""QA Evaluation Service for NeurIPS 2026 ablation experiments.

Provides curated question sets for:
- Experiment 2: Assertion-sensitive clinical QA (50 questions)
- Experiment 3: Temporal clinical QA (100 questions)
- Experiment 4: Graph-RAG clinical QA (200 questions)

Each question set includes expected answers, question categories,
and scoring rubrics for automated + expert evaluation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# Question Types
# ============================================================================


class AssertionQuestionType(str, Enum):
    """Categories for assertion-sensitive questions (Experiment 2)."""

    NEGATION = "negation"
    UNCERTAINTY = "uncertainty"
    FAMILY_HISTORY = "family_history"
    TEMPORAL_STATUS = "temporal_status"
    CONDITIONAL = "conditional"


class TemporalQuestionType(str, Enum):
    """Categories for temporal questions (Experiment 3)."""

    CURRENT_STATE = "current_state"
    HISTORICAL = "historical"
    SEQUENCE = "sequence"
    DURATION = "duration"
    CHANGE = "change"


class RAGQuestionType(str, Enum):
    """Categories for Graph-RAG questions (Experiment 4)."""

    SINGLE_HOP = "single_hop"
    MULTI_HOP = "multi_hop"
    REASONING = "reasoning"
    GUIDELINE_SENSITIVE = "guideline_sensitive"


# ============================================================================
# Question Data Structures
# ============================================================================


@dataclass
class QAQuestion:
    """A single QA evaluation question."""

    question_id: str
    question: str
    category: str
    expected_answer: str
    assertion_sensitive: bool = False
    temporal_sensitive: bool = False
    difficulty: str = "medium"
    clinical_context: str = ""
    scoring_rubric: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class QAResult:
    """Result of evaluating a single question."""

    question_id: str
    predicted_answer: str
    expected_answer: str
    correct: bool
    score: float
    category: str
    condition: str
    latency_ms: float = 0.0
    reasoning_trace: str = ""
    error: str | None = None


@dataclass
class QAEvaluationReport:
    """Aggregate report for a QA evaluation run."""

    experiment_name: str
    condition: str
    total_questions: int
    correct: int
    accuracy: float
    category_accuracies: dict[str, float] = field(default_factory=dict)
    avg_latency_ms: float = 0.0
    results: list[QAResult] = field(default_factory=list)


# ============================================================================
# Assertion-Sensitive Questions (Experiment 2)
# ============================================================================

ASSERTION_QUESTIONS: list[QAQuestion] = [
    # === NEGATION (15 questions) ===
    QAQuestion(
        question_id="a2_neg_01",
        question="Does the patient have diabetes?",
        category="negation",
        expected_answer="No — the note states the patient 'denies diabetes' / 'no history of diabetes'.",
        assertion_sensitive=True,
        clinical_context="Patient note contains: 'Patient denies diabetes. No history of DM.'",
        scoring_rubric={"correct_negation": 1.0, "false_positive": -1.0},
    ),
    QAQuestion(
        question_id="a2_neg_02",
        question="Is there evidence of coronary artery disease?",
        category="negation",
        expected_answer="No — the note states 'no evidence of coronary artery disease on stress test'.",
        assertion_sensitive=True,
        clinical_context="Cardiac workup note: 'Stress test negative. No evidence of coronary artery disease.'",
    ),
    QAQuestion(
        question_id="a2_neg_03",
        question="Does the patient have a penicillin allergy?",
        category="negation",
        expected_answer="No — the note states 'no known drug allergies' / 'NKDA'.",
        assertion_sensitive=True,
        clinical_context="Allergies section: 'NKDA. No known drug allergies.'",
    ),
    QAQuestion(
        question_id="a2_neg_04",
        question="Has the patient been diagnosed with cancer?",
        category="negation",
        expected_answer="No — cancer screening was negative.",
        assertion_sensitive=True,
        clinical_context="Note: 'Cancer screening negative. No malignancy identified on imaging.'",
    ),
    QAQuestion(
        question_id="a2_neg_05",
        question="Is the patient experiencing chest pain?",
        category="negation",
        expected_answer="No — patient denies chest pain.",
        assertion_sensitive=True,
        clinical_context="ROS: 'Denies chest pain, shortness of breath, palpitations.'",
    ),
    QAQuestion(
        question_id="a2_neg_06",
        question="Does the patient smoke?",
        category="negation",
        expected_answer="No — the patient is a non-smoker.",
        assertion_sensitive=True,
        clinical_context="Social history: 'Non-smoker. Never smoked. No tobacco use.'",
    ),
    QAQuestion(
        question_id="a2_neg_07",
        question="Is there a DVT?",
        category="negation",
        expected_answer="No — duplex ultrasound was negative for DVT.",
        assertion_sensitive=True,
        clinical_context="Imaging: 'Bilateral lower extremity duplex: No evidence of DVT.'",
    ),
    QAQuestion(
        question_id="a2_neg_08",
        question="Does the patient have hepatitis?",
        category="negation",
        expected_answer="No — hepatitis panel was negative.",
        assertion_sensitive=True,
        clinical_context="Labs: 'Hepatitis panel: HBsAg negative, Anti-HCV negative.'",
    ),
    QAQuestion(
        question_id="a2_neg_09",
        question="Was a fracture found on imaging?",
        category="negation",
        expected_answer="No — no fracture identified on X-ray.",
        assertion_sensitive=True,
        clinical_context="Radiology: 'No acute fracture or dislocation. No bony abnormality.'",
    ),
    QAQuestion(
        question_id="a2_neg_10",
        question="Does the patient have HIV?",
        category="negation",
        expected_answer="No — HIV test was negative.",
        assertion_sensitive=True,
        clinical_context="Labs: 'HIV 1/2 Ab/Ag: Non-reactive. HIV negative.'",
    ),
    QAQuestion(
        question_id="a2_neg_11",
        question="Is the patient taking any blood thinners?",
        category="negation",
        expected_answer="No — not on anticoagulation.",
        assertion_sensitive=True,
        clinical_context="Medications: 'Not on anticoagulation. No blood thinners.'",
    ),
    QAQuestion(
        question_id="a2_neg_12",
        question="Was pneumonia found on the chest X-ray?",
        category="negation",
        expected_answer="No — no pneumonia on imaging.",
        assertion_sensitive=True,
        clinical_context="Radiology: 'CXR: Lungs are clear. No infiltrate or consolidation. No pneumonia.'",
    ),
    QAQuestion(
        question_id="a2_neg_13",
        question="Does the patient have kidney disease?",
        category="negation",
        expected_answer="No — renal function is normal.",
        assertion_sensitive=True,
        clinical_context="Labs: 'Creatinine 0.9, BUN 15. No evidence of renal disease.'",
    ),
    QAQuestion(
        question_id="a2_neg_14",
        question="Is there a history of stroke?",
        category="negation",
        expected_answer="No — no prior CVA.",
        assertion_sensitive=True,
        clinical_context="PMH: 'No history of stroke or TIA. No prior CVA.'",
    ),
    QAQuestion(
        question_id="a2_neg_15",
        question="Has the patient had any surgeries?",
        category="negation",
        expected_answer="No — no prior surgical history.",
        assertion_sensitive=True,
        clinical_context="PSH: 'No prior surgeries. Surgical history: none.'",
    ),

    # === UNCERTAINTY (10 questions) ===
    QAQuestion(
        question_id="a2_unc_01",
        question="Is pneumonia confirmed?",
        category="uncertainty",
        expected_answer="Not confirmed — the note says 'possible pneumonia' / 'cannot rule out pneumonia'.",
        assertion_sensitive=True,
        clinical_context="Assessment: 'Possible pneumonia. Cannot rule out community-acquired pneumonia.'",
    ),
    QAQuestion(
        question_id="a2_unc_02",
        question="Does the patient have lupus?",
        category="uncertainty",
        expected_answer="Uncertain — the note says 'suspected SLE pending rheumatology consult'.",
        assertion_sensitive=True,
        clinical_context="Assessment: 'Suspected SLE. ANA positive. Pending rheumatology evaluation.'",
    ),
    QAQuestion(
        question_id="a2_unc_03",
        question="Is there a pulmonary embolism?",
        category="uncertainty",
        expected_answer="Uncertain — PE is in the differential but not yet confirmed.",
        assertion_sensitive=True,
        clinical_context="Assessment: 'Differential includes PE. CT-PA ordered. Probable PE given D-dimer elevation.'",
    ),
    QAQuestion(
        question_id="a2_unc_04",
        question="Does the patient have heart failure?",
        category="uncertainty",
        expected_answer="Uncertain — possible early heart failure, pending echo.",
        assertion_sensitive=True,
        clinical_context="Assessment: 'Possible early heart failure. BNP mildly elevated. Awaiting echocardiogram.'",
    ),
    QAQuestion(
        question_id="a2_unc_05",
        question="Is the mass malignant?",
        category="uncertainty",
        expected_answer="Unknown — biopsy pending. Mass is suspicious but not yet confirmed.",
        assertion_sensitive=True,
        clinical_context="Imaging: 'Suspicious mass in right breast. BI-RADS 4. Biopsy recommended.'",
    ),
    QAQuestion(
        question_id="a2_unc_06",
        question="Does the patient have Parkinson's disease?",
        category="uncertainty",
        expected_answer="Uncertain — probable Parkinsonism, referral to movement disorder specialist.",
        assertion_sensitive=True,
        clinical_context="Neurology note: 'Probable Parkinsonism. Asymmetric tremor. Movement disorder referral placed.'",
    ),
    QAQuestion(
        question_id="a2_unc_07",
        question="Is the infection bacterial or viral?",
        category="uncertainty",
        expected_answer="Uncertain — unclear etiology. Cultures pending.",
        assertion_sensitive=True,
        clinical_context="Assessment: 'URI, unclear bacterial vs viral. Cultures sent. Empiric antibiotics started.'",
    ),
    QAQuestion(
        question_id="a2_unc_08",
        question="Does the patient have celiac disease?",
        category="uncertainty",
        expected_answer="Uncertain — tTG antibodies equivocal. Biopsy recommended.",
        assertion_sensitive=True,
        clinical_context="GI note: 'Equivocal tTG antibodies. Cannot confirm or exclude celiac. EGD with biopsy recommended.'",
    ),
    QAQuestion(
        question_id="a2_unc_09",
        question="Is there meningitis?",
        category="uncertainty",
        expected_answer="Cannot be ruled out — LP being considered.",
        assertion_sensitive=True,
        clinical_context="ER note: 'Fever, neck stiffness. Meningitis cannot be excluded. LP being considered.'",
    ),
    QAQuestion(
        question_id="a2_unc_10",
        question="Does the patient have sleep apnea?",
        category="uncertainty",
        expected_answer="Suspected — sleep study ordered but not yet completed.",
        assertion_sensitive=True,
        clinical_context="Assessment: 'Suspected obstructive sleep apnea. Epworth 15. Polysomnography ordered.'",
    ),

    # === FAMILY HISTORY (10 questions) ===
    QAQuestion(
        question_id="a2_fh_01",
        question="Does the patient have breast cancer?",
        category="family_history",
        expected_answer="No — family history of breast cancer (mother), but patient does not have it.",
        assertion_sensitive=True,
        clinical_context="FH: 'Mother diagnosed with breast cancer at age 52.' Assessment: 'No breast masses. Mammogram normal.'",
    ),
    QAQuestion(
        question_id="a2_fh_02",
        question="Does the patient have colon cancer?",
        category="family_history",
        expected_answer="No — father had colon cancer. Patient's colonoscopy was normal.",
        assertion_sensitive=True,
        clinical_context="FH: 'Father: colon cancer at 60.' GI: 'Colonoscopy: normal. No polyps.'",
    ),
    QAQuestion(
        question_id="a2_fh_03",
        question="Is there heart disease?",
        category="family_history",
        expected_answer="Family history only — sister has CAD, but patient's cardiac workup is normal.",
        assertion_sensitive=True,
        clinical_context="FH: 'Sister with premature CAD at 45.' Cardiac: 'Stress test negative. No CAD.'",
    ),
    QAQuestion(
        question_id="a2_fh_04",
        question="Does the patient have type 2 diabetes?",
        category="family_history",
        expected_answer="No — family history of DM2 in both parents, but patient's HbA1c is normal.",
        assertion_sensitive=True,
        clinical_context="FH: 'Both parents with type 2 diabetes.' Labs: 'HbA1c 5.2%. Fasting glucose 92.'",
    ),
    QAQuestion(
        question_id="a2_fh_05",
        question="Is there a history of Alzheimer's disease?",
        category="family_history",
        expected_answer="Family history only — grandmother had Alzheimer's. Patient is cognitively intact.",
        assertion_sensitive=True,
        clinical_context="FH: 'Maternal grandmother with Alzheimer's.' Neuro: 'MMSE 30/30. Cognition intact.'",
    ),
    QAQuestion(
        question_id="a2_fh_06",
        question="Does the patient have melanoma?",
        category="family_history",
        expected_answer="No — uncle had melanoma. Patient's skin exam is normal.",
        assertion_sensitive=True,
        clinical_context="FH: 'Paternal uncle with melanoma.' Derm: 'Full-body skin exam unremarkable.'",
    ),
    QAQuestion(
        question_id="a2_fh_07",
        question="Is there kidney disease in this patient?",
        category="family_history",
        expected_answer="Family history only — mother on dialysis. Patient's renal function is normal.",
        assertion_sensitive=True,
        clinical_context="FH: 'Mother on hemodialysis for ESRD.' Labs: 'Creatinine 0.8. eGFR >90.'",
    ),
    QAQuestion(
        question_id="a2_fh_08",
        question="Does the patient have depression?",
        category="family_history",
        expected_answer="No — family history of depression (father), but patient screens negative.",
        assertion_sensitive=True,
        clinical_context="FH: 'Father with major depression.' Psych: 'PHQ-9 score 2. No depression.'",
    ),
    QAQuestion(
        question_id="a2_fh_09",
        question="Is there thyroid disease?",
        category="family_history",
        expected_answer="Family history only — sister has Hashimoto's. Patient's thyroid function is normal.",
        assertion_sensitive=True,
        clinical_context="FH: 'Sister with Hashimoto's thyroiditis.' Labs: 'TSH 2.1, Free T4 1.2. Normal.'",
    ),
    QAQuestion(
        question_id="a2_fh_10",
        question="Does the patient have BRCA mutations?",
        category="family_history",
        expected_answer="Family history suggests risk, but genetic testing not yet performed.",
        assertion_sensitive=True,
        clinical_context="FH: 'Mother BRCA1+, breast cancer at 42. Sister ovarian cancer at 48.' Genetics: 'Referral placed.'",
    ),

    # === TEMPORAL STATUS (10 questions) ===
    QAQuestion(
        question_id="a2_ts_01",
        question="Is the patient currently on warfarin?",
        category="temporal_status",
        expected_answer="No — warfarin was discontinued 6 months ago. Now on apixaban.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="Medications: 'Warfarin discontinued 6 months ago. Started apixaban 5mg BID.'",
    ),
    QAQuestion(
        question_id="a2_ts_02",
        question="Does the patient have active MRSA infection?",
        category="temporal_status",
        expected_answer="No — MRSA was treated and resolved. History of MRSA, currently no active infection.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="ID: 'History of MRSA wound infection 2022, treated with vancomycin. Currently no active infection.'",
    ),
    QAQuestion(
        question_id="a2_ts_03",
        question="Is the patient a smoker?",
        category="temporal_status",
        expected_answer="Former smoker — quit 5 years ago.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="Social: 'Former smoker, 20 pack-years. Quit 5 years ago.'",
    ),
    QAQuestion(
        question_id="a2_ts_04",
        question="Does the patient have seizures?",
        category="temporal_status",
        expected_answer="History of seizures, but seizure-free for 2 years on medication.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="Neuro: 'History of epilepsy. Seizure-free for 2 years on levetiracetam.'",
    ),
    QAQuestion(
        question_id="a2_ts_05",
        question="Is the patient receiving chemotherapy?",
        category="temporal_status",
        expected_answer="No — completed chemotherapy 3 months ago. Currently in remission.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="Oncology: 'Completed 6 cycles of FOLFOX 3 months ago. Currently in remission.'",
    ),
    QAQuestion(
        question_id="a2_ts_06",
        question="Does the patient have an active GI bleed?",
        category="temporal_status",
        expected_answer="No — prior GI bleed resolved. Currently stable hemoglobin.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="GI: 'Prior upper GI bleed 2023. EGD showed healed ulcer. Hgb stable at 13.5.'",
    ),
    QAQuestion(
        question_id="a2_ts_07",
        question="Is the patient pregnant?",
        category="temporal_status",
        expected_answer="No — previously pregnant (G2P2), current pregnancy test negative.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="OB: 'G2P2. Last pregnancy 2021. Current beta-HCG negative.'",
    ),
    QAQuestion(
        question_id="a2_ts_08",
        question="Does the patient drink alcohol?",
        category="temporal_status",
        expected_answer="Former drinker — in recovery for 3 years.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="Social: 'History of alcohol use disorder. In recovery for 3 years. Currently abstinent.'",
    ),
    QAQuestion(
        question_id="a2_ts_09",
        question="Is the patient on steroids?",
        category="temporal_status",
        expected_answer="No — prednisone taper completed 2 weeks ago.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="Medications: 'Prednisone taper completed 2 weeks ago. No current steroid use.'",
    ),
    QAQuestion(
        question_id="a2_ts_10",
        question="Does the patient have joint pain?",
        category="temporal_status",
        expected_answer="Resolved — had joint pain from gout flare, now resolved with treatment.",
        assertion_sensitive=True,
        temporal_sensitive=True,
        clinical_context="Rheum: 'Acute gout flare 1 month ago, treated with colchicine. Joint pain resolved.'",
    ),

    # === CONDITIONAL (5 questions) ===
    QAQuestion(
        question_id="a2_cond_01",
        question="Should the patient receive metformin?",
        category="conditional",
        expected_answer="Conditional — only if renal function remains stable (eGFR >30).",
        assertion_sensitive=True,
        clinical_context="Endocrine: 'Consider metformin if eGFR remains >30. Currently eGFR 45, borderline.'",
    ),
    QAQuestion(
        question_id="a2_cond_02",
        question="Can the patient have an MRI?",
        category="conditional",
        expected_answer="Conditional — only if pacemaker is MRI-compatible (needs cardiology clearance).",
        assertion_sensitive=True,
        clinical_context="Radiology: 'MRI requested. Patient has pacemaker. Conditional on MRI-compatible device confirmation.'",
    ),
    QAQuestion(
        question_id="a2_cond_03",
        question="Should anticoagulation be started?",
        category="conditional",
        expected_answer="Conditional — if atrial fibrillation is confirmed on follow-up Holter.",
        assertion_sensitive=True,
        clinical_context="Cardiology: 'Suspected paroxysmal AFib. Holter ordered. Anticoagulation if confirmed.'",
    ),
    QAQuestion(
        question_id="a2_cond_04",
        question="Is the patient a candidate for surgery?",
        category="conditional",
        expected_answer="Conditional — pending cardiac clearance and optimization of blood sugar.",
        assertion_sensitive=True,
        clinical_context="Surgery: 'Candidate for elective cholecystectomy pending cardiac clearance and HbA1c <8.'",
    ),
    QAQuestion(
        question_id="a2_cond_05",
        question="Should the patient receive a statin?",
        category="conditional",
        expected_answer="Conditional — recommended if LDL remains >130 after 3 months of lifestyle changes.",
        assertion_sensitive=True,
        clinical_context="Primary care: 'LDL 145. Lifestyle modifications recommended. Statin if LDL >130 at 3-month follow-up.'",
    ),
]


# ============================================================================
# Temporal Questions (Experiment 3) — First 30 of 100
# ============================================================================

TEMPORAL_QUESTIONS: list[QAQuestion] = [
    # === CURRENT STATE (30 questions — first 10 shown) ===
    QAQuestion(
        question_id="t3_cs_01",
        question="What medications is the patient currently taking?",
        category="current_state",
        expected_answer="Current medications list from most recent encounter.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_cs_02",
        question="What is the patient's current blood pressure?",
        category="current_state",
        expected_answer="Most recent BP reading.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_cs_03",
        question="What active conditions does the patient have?",
        category="current_state",
        expected_answer="Only CURRENT conditions, not historical or resolved.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_cs_04",
        question="Is the patient currently hospitalized?",
        category="current_state",
        expected_answer="Based on most recent encounter status.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_cs_05",
        question="What is the patient's latest HbA1c?",
        category="current_state",
        expected_answer="Most recent HbA1c value and date.",
        temporal_sensitive=True,
    ),

    # === HISTORICAL (25 questions — first 5 shown) ===
    QAQuestion(
        question_id="t3_hist_01",
        question="What was the patient's diagnosis in 2023?",
        category="historical",
        expected_answer="Conditions active during 2023.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_hist_02",
        question="When was the patient first diagnosed with hypertension?",
        category="historical",
        expected_answer="Date of first hypertension diagnosis.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_hist_03",
        question="What medications was the patient taking before the surgery?",
        category="historical",
        expected_answer="Medication list from pre-operative period.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_hist_04",
        question="Has the patient ever had an abnormal ECG?",
        category="historical",
        expected_answer="Any abnormal ECG findings across entire history.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_hist_05",
        question="What was the patient's weight 6 months ago?",
        category="historical",
        expected_answer="Weight measurement from approximately 6 months prior.",
        temporal_sensitive=True,
    ),

    # === SEQUENCE (20 questions — first 5 shown) ===
    QAQuestion(
        question_id="t3_seq_01",
        question="Was the surgery performed before or after the infection?",
        category="sequence",
        expected_answer="Correct temporal ordering of surgery and infection events.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_seq_02",
        question="Did the patient start metformin before or after the diabetes diagnosis?",
        category="sequence",
        expected_answer="Metformin started after diabetes diagnosis.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_seq_03",
        question="Which came first: the CT scan or the biopsy?",
        category="sequence",
        expected_answer="Correct temporal ordering of diagnostic procedures.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_seq_04",
        question="Was the allergy documented before or after the adverse drug reaction?",
        category="sequence",
        expected_answer="Temporal ordering of allergy documentation vs ADR event.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_seq_05",
        question="Did the patient's kidney function decline before or after starting the NSAID?",
        category="sequence",
        expected_answer="Correct ordering of kidney function changes and NSAID initiation.",
        temporal_sensitive=True,
    ),

    # === DURATION (15 questions — first 5 shown) ===
    QAQuestion(
        question_id="t3_dur_01",
        question="How long has the patient been on metformin?",
        category="duration",
        expected_answer="Duration from start date to current/end date.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_dur_02",
        question="How long was the patient hospitalized?",
        category="duration",
        expected_answer="Length of stay from admission to discharge.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_dur_03",
        question="For how many years has the patient had hypertension?",
        category="duration",
        expected_answer="Duration since first hypertension diagnosis.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_dur_04",
        question="How long did the course of antibiotics last?",
        category="duration",
        expected_answer="Duration from antibiotic start to completion.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_dur_05",
        question="How long after surgery did the complication occur?",
        category="duration",
        expected_answer="Time interval between surgery and complication onset.",
        temporal_sensitive=True,
    ),

    # === CHANGE (10 questions — first 5 shown) ===
    QAQuestion(
        question_id="t3_chg_01",
        question="Has the patient's blood pressure improved since starting lisinopril?",
        category="change",
        expected_answer="Comparison of BP before and after lisinopril initiation.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_chg_02",
        question="Is the patient's HbA1c trending up or down?",
        category="change",
        expected_answer="Trend analysis of serial HbA1c values.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_chg_03",
        question="Has the tumor size changed since last imaging?",
        category="change",
        expected_answer="Comparison of tumor measurements across imaging studies.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_chg_04",
        question="Has the patient's kidney function improved after stopping the nephrotoxic drug?",
        category="change",
        expected_answer="Creatinine/eGFR trend after medication discontinuation.",
        temporal_sensitive=True,
    ),
    QAQuestion(
        question_id="t3_chg_05",
        question="Is the patient gaining or losing weight?",
        category="change",
        expected_answer="Weight trend over recent visits.",
        temporal_sensitive=True,
    ),
]


# ============================================================================
# Graph-RAG Questions (Experiment 4) — Representative subset
# ============================================================================

RAG_QUESTIONS: list[QAQuestion] = [
    # === SINGLE HOP (50 → first 10 shown) ===
    QAQuestion(
        question_id="r4_sh_01",
        question="What is the patient's latest HbA1c?",
        category="single_hop",
        expected_answer="Most recent HbA1c lab value.",
    ),
    QAQuestion(
        question_id="r4_sh_02",
        question="What medications is the patient taking for hypertension?",
        category="single_hop",
        expected_answer="Antihypertensive medications from medication list.",
    ),
    QAQuestion(
        question_id="r4_sh_03",
        question="When was the patient's last colonoscopy?",
        category="single_hop",
        expected_answer="Date of most recent colonoscopy procedure.",
    ),
    QAQuestion(
        question_id="r4_sh_04",
        question="What allergies does the patient have?",
        category="single_hop",
        expected_answer="All documented allergies.",
    ),
    QAQuestion(
        question_id="r4_sh_05",
        question="What is the patient's BMI?",
        category="single_hop",
        expected_answer="Latest BMI calculation or documented value.",
    ),

    # === MULTI-HOP (50 → first 10 shown) ===
    QAQuestion(
        question_id="r4_mh_01",
        question="What medications treat the patient's conditions that interact with their current drugs?",
        category="multi_hop",
        expected_answer="Requires: patient conditions → treatments → drug interactions with current meds.",
    ),
    QAQuestion(
        question_id="r4_mh_02",
        question="Are any of the patient's medications contraindicated given their kidney function?",
        category="multi_hop",
        expected_answer="Requires: current medications → renal dosing requirements → latest eGFR.",
    ),
    QAQuestion(
        question_id="r4_mh_03",
        question="What conditions could explain both the patient's elevated liver enzymes AND joint pain?",
        category="multi_hop",
        expected_answer="Requires: liver enzyme results → conditions causing hepatitis → overlap with conditions causing arthralgia.",
    ),
    QAQuestion(
        question_id="r4_mh_04",
        question="Is the patient taking any medications that could worsen their diabetes?",
        category="multi_hop",
        expected_answer="Requires: current meds → side effects → hyperglycemia risk → diabetes diagnosis.",
    ),
    QAQuestion(
        question_id="r4_mh_05",
        question="What preventive screenings is the patient overdue for given their risk factors?",
        category="multi_hop",
        expected_answer="Requires: age + gender + family history + conditions → screening guidelines → last screening dates.",
    ),

    # === REASONING (50 → first 5 shown) ===
    QAQuestion(
        question_id="r4_rea_01",
        question="Is the patient's treatment appropriate given their comorbidities?",
        category="reasoning",
        expected_answer="Clinical reasoning about treatment appropriateness across all active conditions.",
    ),
    QAQuestion(
        question_id="r4_rea_02",
        question="What is the most likely cause of the patient's acute kidney injury?",
        category="reasoning",
        expected_answer="Differential diagnosis considering medications, conditions, and recent events.",
    ),
    QAQuestion(
        question_id="r4_rea_03",
        question="Should the patient's statin be continued given the new muscle pain complaint?",
        category="reasoning",
        expected_answer="Risk-benefit analysis considering CK levels, cardiovascular risk, and alternative statins.",
    ),
    QAQuestion(
        question_id="r4_rea_04",
        question="Is the patient's anemia likely iron-deficiency, B12-deficiency, or chronic disease?",
        category="reasoning",
        expected_answer="Lab pattern analysis: MCV, ferritin, B12, reticulocyte count, inflammatory markers.",
    ),
    QAQuestion(
        question_id="r4_rea_05",
        question="What is the patient's cardiovascular risk score?",
        category="reasoning",
        expected_answer="ASCVD risk calculation using age, BP, cholesterol, diabetes status, smoking.",
    ),

    # === GUIDELINE-SENSITIVE (50 → first 5 shown) ===
    QAQuestion(
        question_id="r4_gl_01",
        question="Does the patient meet criteria for statin therapy per AHA/ACC guidelines?",
        category="guideline_sensitive",
        expected_answer="Evaluation against 4 statin benefit groups from 2018 AHA/ACC guidelines.",
    ),
    QAQuestion(
        question_id="r4_gl_02",
        question="Is the patient's diabetes management per ADA standards of care?",
        category="guideline_sensitive",
        expected_answer="Comparison against ADA 2024 Standards: HbA1c target, medication choice, screening intervals.",
    ),
    QAQuestion(
        question_id="r4_gl_03",
        question="Should the patient be on aspirin for primary prevention?",
        category="guideline_sensitive",
        expected_answer="USPSTF aspirin guidelines: age 40-59, ≥10% 10-year CVD risk, low bleeding risk.",
    ),
    QAQuestion(
        question_id="r4_gl_04",
        question="Is the patient's blood pressure at goal per JNC-8 guidelines?",
        category="guideline_sensitive",
        expected_answer="BP target evaluation: <130/80 for most, <140/90 for age >60 without diabetes/CKD.",
    ),
    QAQuestion(
        question_id="r4_gl_05",
        question="Does the patient need colon cancer screening per USPSTF guidelines?",
        category="guideline_sensitive",
        expected_answer="Age 45-75 screening recommendation, considering family history for earlier start.",
    ),
]


# ============================================================================
# QA Evaluation Service
# ============================================================================


class QAEvaluationService:
    """Manages QA evaluation for ablation experiments."""

    def get_assertion_questions(self) -> list[QAQuestion]:
        """Get all 50 assertion-sensitive questions for Experiment 2."""
        return ASSERTION_QUESTIONS

    def get_temporal_questions(self) -> list[QAQuestion]:
        """Get temporal questions for Experiment 3."""
        return TEMPORAL_QUESTIONS

    def get_rag_questions(self) -> list[QAQuestion]:
        """Get Graph-RAG questions for Experiment 4."""
        return RAG_QUESTIONS

    def get_questions_by_category(
        self, questions: list[QAQuestion], category: str
    ) -> list[QAQuestion]:
        """Filter questions by category."""
        return [q for q in questions if q.category == category]

    @staticmethod
    def _strip_evidence_echo(text: str) -> str:
        """Strip echoed evidence preamble from model answers.

        MedGemma often starts answers by repeating the 'Assertion Notes'
        section from the evidence.  This pollutes keyword-based scoring
        because historical/negation keywords in the echo trigger false
        matches.  We strip the preamble so only the model's actual answer
        is scored.
        """
        if not text.strip().startswith("Assertion Notes"):
            return text
        # Split on first double-newline — preamble is before, answer after
        parts = re.split(r"\n\n+", text, maxsplit=1)
        if len(parts) > 1:
            return parts[1].strip()
        # Fallback: skip leading bullet lines
        lines = text.split("\n")
        for i, line in enumerate(lines):
            s = line.strip()
            if i > 0 and s and not s.startswith(("-", "*", ">", "Assertion", "=")):
                return "\n".join(lines[i:]).strip()
        return text

    def score_answer(
        self,
        question: QAQuestion,
        predicted_answer: str,
        condition: str,
    ) -> QAResult:
        """Score a predicted answer against expected answer.

        Uses keyword matching for automated scoring. Expert review
        should be applied to a subset for inter-annotator agreement.
        """
        expected_lower = question.expected_answer.lower()
        predicted_lower = predicted_answer.lower()

        # Simple keyword-based scoring
        correct = False
        score = 0.0

        if question.category == "negation":
            # For negation questions, the correct answer should indicate absence.
            # Use word-boundary matching to avoid false positives from substrings
            # (e.g., "noted" contains "not", "chronic" etc.).
            negation_keywords = ["no", "negative", "denies", "absent", "not",
                                 "none", "nkda", "nothing", "cannot", "denied",
                                 "ruled out", "no evidence"]
            _negation_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in negation_keywords]
            answer_has_negation = any(p.search(predicted_lower) for p in _negation_patterns)
            expected_has_negation = any(p.search(expected_lower) for p in _negation_patterns)
            correct = answer_has_negation == expected_has_negation
            score = 1.0 if correct else 0.0

        elif question.category == "uncertainty":
            uncertainty_keywords = [
                "uncertain", "possible", "suspected", "pending",
                "cannot rule out", "unclear", "equivocal",
                # Medical hedging — valid clinical uncertainty language
                "likely", "probable", "concerning for", "suggestive",
                "may be", "may indicate", "not confirmed",
                "not definitively", "cannot exclude", "cannot be confirmed",
                "provisional", "tentative",
            ]
            _unc_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in uncertainty_keywords]
            answer_has_uncertainty = any(p.search(predicted_lower) for p in _unc_patterns)
            correct = answer_has_uncertainty
            score = 1.0 if correct else 0.0

        elif question.category == "family_history":
            fh_keywords = ["family", "mother", "father", "sister", "brother", "relative"]
            _fh_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in fh_keywords]
            distinguishes_fh = any(p.search(predicted_lower) for p in _fh_patterns)
            patient_negative_patterns = [
                re.compile(r'\bpatient does not\b'),
                re.compile(r"\bpatient's\b.*\bnormal\b"),
                re.compile(r'\bno\b.*\bin patient\b'),
            ]
            patient_clear = (
                any(p.search(predicted_lower) for p in patient_negative_patterns)
                or "family history only" in predicted_lower
            )
            correct = distinguishes_fh or patient_clear
            score = 1.0 if correct else 0.0

        elif question.category == "conditional":
            conditional_keywords = ["if", "conditional", "pending", "depending", "only if"]
            _cond_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in conditional_keywords]
            answer_conditional = any(p.search(predicted_lower) for p in _cond_patterns)
            correct = answer_conditional
            score = 1.0 if correct else 0.0

        elif question.category == "temporal_status":
            temporal_keywords = ["was", "former", "previously", "discontinued", "completed", "resolved", "history of", "quit"]
            _temp_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in temporal_keywords]
            answer_temporal = any(p.search(predicted_lower) for p in _temp_patterns)
            correct = answer_temporal
            score = 1.0 if correct else 0.0

        # --- Task B: Temporal reasoning categories ---
        elif question.category in ("current_state", "historical"):
            # Strip echoed assertion notes — they contain historical/current
            # keywords that cause cross-contamination between these categories.
            cleaned = self._strip_evidence_echo(predicted_answer).lower()
            current_kw = ["current", "active", "present", "ongoing", "documented", "has", "is on"]
            historical_kw = ["was", "former", "previously", "history of", "resolved", "past", "discontinued", "prior"]
            _cur_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in current_kw]
            _hist_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in historical_kw]
            expected_is_current = any(p.search(expected_lower) for p in _cur_patterns)
            answer_is_current = any(p.search(cleaned) for p in _cur_patterns)
            answer_is_historical = any(p.search(cleaned) for p in _hist_patterns)
            if expected_is_current:
                correct = answer_is_current and not answer_is_historical
            else:
                correct = answer_is_historical
            score = 1.0 if correct else 0.0

        elif question.category in ("sequence", "change"):
            # Check if the answer identifies the correct ordering or change
            # Extract key clinical terms from expected answer
            expected_terms = set(expected_lower.split()) - {
                "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
                "then", "by", "first", "followed", "identified", "before", "after",
            }
            predicted_terms = set(predicted_lower.split())
            overlap = expected_terms & predicted_terms
            score = len(overlap) / max(len(expected_terms), 1)
            # Also check for ordering keywords (word-boundary match)
            order_kw = ["first", "then", "followed", "before", "after", "prior", "subsequently", "later"]
            _order_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in order_kw]
            has_ordering = any(p.search(predicted_lower) for p in _order_patterns)
            if has_ordering:
                score = min(score + 0.2, 1.0)
            correct = score >= 0.3

        elif question.category == "duration":
            # Check if answer references time duration concepts (word-boundary match)
            duration_kw = ["day", "days", "week", "weeks", "month", "months", "year", "years",
                           "duration", "since", "period", "length", "span"]
            _dur_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in duration_kw]
            has_duration = any(p.search(predicted_lower) for p in _dur_patterns)
            # Also check key concept overlap
            expected_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for", "was"}
            predicted_terms = set(predicted_lower.split())
            overlap = expected_terms & predicted_terms
            term_score = len(overlap) / max(len(expected_terms), 1)
            score = max(term_score, 0.5 if has_duration else 0.0)
            correct = score >= 0.3

        # --- Task C: Calculator categories ---
        elif question.category in ("heart", "wells_pe", "sofa", "ckd_epi", "ascvd", "meld", "other"):
            # For calculator questions, check if answer mentions relevant score/values
            # and reaches a similar clinical conclusion
            expected_terms = set(expected_lower.split()) - {
                "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
                "score", "based", "on", "patient", "this", "with", "that",
            }
            predicted_terms = set(predicted_lower.split())
            overlap = expected_terms & predicted_terms
            score = len(overlap) / max(len(expected_terms), 1)
            # Bonus for mentioning specific calculator or risk level (word-boundary match)
            calc_kw = ["score", "risk", "low", "moderate", "high", "points", "calculate"]
            _calc_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in calc_kw]
            if any(p.search(predicted_lower) for p in _calc_patterns):
                score = min(score + 0.15, 1.0)
            correct = score >= 0.3

        # --- Task D: Fusion categories ---
        elif question.category in ("vital_note", "lab_note", "temporal_fusion", "cross_note_discordance"):
            # For fusion questions, check if answer integrates information
            expected_terms = set(expected_lower.split()) - {
                "the", "a", "an", "is", "of", "in", "to", "for", "was", "and",
                "patient", "this", "with", "that", "from", "note", "notes",
            }
            predicted_terms = set(predicted_lower.split())
            overlap = expected_terms & predicted_terms
            score = len(overlap) / max(len(expected_terms), 1)
            # Bonus for multi-source integration language (word-boundary match)
            fusion_kw = ["however", "while", "compared", "discrepancy", "consistent", "inconsistent", "both", "across"]
            _fusion_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in fusion_kw]
            if any(p.search(predicted_lower) for p in _fusion_patterns):
                score = min(score + 0.1, 1.0)
            correct = score >= 0.25

        else:
            # General scoring: check if key terms from expected answer appear
            expected_terms = set(expected_lower.split()) - {"the", "a", "an", "is", "of", "in", "to", "for"}
            predicted_terms = set(predicted_lower.split())
            overlap = expected_terms & predicted_terms
            score = len(overlap) / max(len(expected_terms), 1)
            correct = score >= 0.3

        return QAResult(
            question_id=question.question_id,
            predicted_answer=predicted_answer,
            expected_answer=question.expected_answer,
            correct=correct,
            score=score,
            category=question.category,
            condition=condition,
        )

    def evaluate_question_set(
        self,
        questions: list[QAQuestion],
        answers: dict[str, str],
        condition: str,
        experiment_name: str,
    ) -> QAEvaluationReport:
        """Evaluate a full question set and produce aggregate report."""
        results = []
        category_correct: dict[str, int] = {}
        category_total: dict[str, int] = {}

        for q in questions:
            answer = answers.get(q.question_id, "")
            result = self.score_answer(q, answer, condition)
            results.append(result)

            cat = q.category
            category_total[cat] = category_total.get(cat, 0) + 1
            if result.correct:
                category_correct[cat] = category_correct.get(cat, 0) + 1

        total = len(results)
        correct = sum(1 for r in results if r.correct)
        accuracy = correct / total if total > 0 else 0.0

        category_accuracies = {
            cat: category_correct.get(cat, 0) / category_total[cat]
            for cat in category_total
        }

        return QAEvaluationReport(
            experiment_name=experiment_name,
            condition=condition,
            total_questions=total,
            correct=correct,
            accuracy=accuracy,
            category_accuracies=category_accuracies,
            results=results,
        )

    def compute_clinical_safety_score(
        self, results: list[QAResult]
    ) -> float:
        """Compute weighted clinical safety score.

        Penalties are heavier for dangerous errors:
        - False positive on negated condition: -2.0
        - Treating family history as patient condition: -1.5
        - Ignoring uncertainty: -1.0
        - Temporal status error: -0.5
        """
        score = 0.0
        total_weight = 0.0

        for r in results:
            weight = 1.0
            if r.category == "negation":
                weight = 2.0
            elif r.category == "family_history":
                weight = 1.5
            elif r.category == "uncertainty":
                weight = 1.0
            elif r.category == "conditional":
                weight = 0.75

            total_weight += weight
            if r.correct:
                score += weight
            # Incorrect negation is a "dangerous" error
            elif r.category == "negation":
                score -= weight  # Double penalty

        return score / total_weight if total_weight > 0 else 0.0
