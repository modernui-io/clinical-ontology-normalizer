# EpiKG Physician Validation Protocol

## Two-Physician Blinded Adjudication of ClinicalBench and SliceBench

**Protocol Version:** 1.0
**Date:** 2026-02-26
**Study:** EpiKG -- Epistemic Knowledge Graph-Augmented Retrieval for Clinical QA
**Benchmarks:** ClinicalBench (400 questions, 9 categories) and SliceBench (144 questions, 6 patients)

---

## 1. Study Design

### 1.1 Objective

Validate the accuracy of two automated evaluation methods used in the EpiKG paper:

1. **ClinicalBench deterministic keyword evaluator** -- exact word-boundary regex matching of assertion/temporal keywords against model answers.
2. **SliceBench LLM-as-judge** -- Claude Opus 4.6 scoring Claude Sonnet 4.5 answers on a correct/incorrect scale.

Additionally, assess the quality of the gold-standard questions and answers themselves.

### 1.2 Design Summary

- **Two independent physician reviewers**, each blinded to condition labels and automated scores.
- **Stratified sample** covering both benchmarks (see Section 2 for sample sizes).
- **Third adjudicator** resolves disagreements.
- **Inter-rater reliability** measured by Cohen's kappa.

### 1.3 Blinding

Reviewers see:
- The clinical question
- The source clinical context (note excerpt or structured context)
- The gold-standard expected answer
- The model-generated answer

Reviewers do NOT see:
- The condition label (C1, C4, C4g, C6, C7, B0-B4)
- The model name (MedGemma 27B vs. Claude Opus 4.6)
- The automated score (keyword match result or LLM-judge verdict)
- Other reviewer's scores (until reconciliation)

---

## 2. Sample Selection Strategy

### 2.1 Rationale

Full adjudication of all 544 questions (400 ClinicalBench + 144 SliceBench) across all conditions would require reviewing 2,000+ question-answer pairs -- impractical for physician time. A stratified sample targets the categories and conditions where automated evaluation is most likely to err.

### 2.2 ClinicalBench Sampling (Target: n=120 question-answer pairs)

**Stratification by category and risk of evaluator error:**

| Category | Total Questions | Sample Size | Sampling Rationale |
|---|---|---|---|
| Uncertainty | 40 | 20 (50%) | Pilot revealed overly strict scoring; highest error risk |
| Sequence | 40 | 20 (50%) | Pilot revealed overly strict scoring |
| Change | 30 | 15 (50%) | Complex multi-admission; soft keyword overlap scoring |
| Current state | 50 | 15 (30%) | Keyword-based temporal classification is fragile |
| Historical | 50 | 15 (30%) | Large regression (-46pp) under C4g; may reflect evaluator vs. retrieval issue |
| Conditional | 20 | 10 (50%) | Small n; keyword "if" may false-positive |
| Family history | 30 | 10 (33%) | Large swing across conditions (0% to 70%) |
| Duration | 30 | 10 (33%) | Soft scoring threshold (>=0.3) |
| Negation | 110 | 5 (5%) | High ceiling accuracy (86-100%); low error risk |

**Condition sampling within each category:** For each sampled question, review the model answer from two conditions: C1 (LLM alone) and C4g (intent-aware KG-RAG). This produces 120 questions x 2 conditions = **240 scored pairs** for ClinicalBench.

**Selection method:** Random sample within each category, stratified to ensure representation of both correct and incorrect automated scores (aim for ~50/50 split where possible, to maximize evaluator error detection power).

### 2.3 SliceBench Sampling (Target: n=48 question-answer pairs)

Sample 8 questions per patient (48 total) across all 6 patients, focusing on:
- Hard longitudinal categories (cross-encounter medication timelines, problem list reconciliation)
- Cases where B2 and B3 scores diverge (the critical KG contribution comparison)

For each sampled question, review the B2 (all notes RAG) and B3 (KG-RAG) answers = **96 scored pairs** for SliceBench.

### 2.4 Total Physician Workload

| Benchmark | Questions | Conditions per Q | Total Pairs | Est. Time per Pair | Total Time |
|---|---|---|---|---|---|
| ClinicalBench | 120 | 2 | 240 | 2-3 min | 8-12 hours |
| SliceBench | 48 | 2 | 96 | 3-4 min | 5-6 hours |
| **Total** | **168** | -- | **336** | -- | **13-18 hours per reviewer** |

This can be split across 3-4 sessions of 4-5 hours each.

---

## 3. What Physicians See (Case Report Form)

Each review item presents the following fields in a standardized form:

```
================================================================
ITEM ID: [randomized opaque identifier, e.g., "VAL_0042"]
================================================================

CATEGORY: [e.g., "uncertainty", "change", "current_state"]

QUESTION:
  "What is the diagnostic certainty for alcohol?"

CLINICAL CONTEXT (source note excerpt):
  "Patient was ward of the ___, doesn't know full details of
   family history. Mother with possible alcohol abuse. Father
   deceased at ___ from Hodgkin's Disease per old records."

GOLD-STANDARD EXPECTED ANSWER:
  "Uncertain. alcohol is suspected but not confirmed. Further
   workup may be needed."

MODEL-GENERATED ANSWER:
  "Based on the clinical record, alcohol abuse is mentioned as
   a possibility in the family history section. The note states
   'possible alcohol abuse' for the patient's mother, indicating
   this is not confirmed but rather suspected."

================================================================
PHYSICIAN ASSESSMENT (fill in below):
================================================================
```

### 3.1 Order Randomization

- All 336 pairs are randomized into a single sequence per reviewer using a fixed random seed (seed=42).
- ClinicalBench and SliceBench items are interleaved.
- The two conditions for the same question are never adjacent (minimum 20-item gap).

---

## 4. Scoring Rubric

### 4.1 Gold-Standard Quality Assessment

For each item, the reviewer first assesses the gold-standard expected answer:

| Rating | Code | Definition |
|---|---|---|
| **Correct** | `GS_CORRECT` | The gold-standard answer is clinically accurate given the provided context. The question is well-formed and the expected answer correctly captures the clinical fact. |
| **Partially correct** | `GS_PARTIAL` | The gold-standard answer is directionally correct but contains an imprecision, over-simplification, or missing nuance. Example: "absent" when the note says "unlikely" (uncertainty, not negation). |
| **Incorrect** | `GS_INCORRECT` | The gold-standard answer is clinically wrong given the source context. Example: gold standard says "negated" but the note says "history of" (affirmed, historical). |
| **Ambiguous context** | `GS_AMBIGUOUS` | The source clinical context is insufficient to determine the correct answer. The question may be valid but the provided excerpt does not contain enough information. |

### 4.2 Model Answer Assessment

Then the reviewer assesses the model-generated answer against the clinical context (NOT against the gold standard -- the reviewer uses their own clinical judgment):

| Rating | Code | Definition |
|---|---|---|
| **Correct** | `MA_CORRECT` | The model answer correctly addresses the clinical question. It identifies the right assertion status, temporal relationship, or clinical fact, and does not contain clinically dangerous errors. |
| **Partially correct** | `MA_PARTIAL` | The model answer is directionally correct but contains a meaningful imprecision. Examples: correct assertion but wrong temporal qualifier; identifies the right condition but misattributes it; uses hedging language when the note is definitive (or vice versa). |
| **Incorrect** | `MA_INCORRECT` | The model answer is clinically wrong. It misidentifies the assertion status (e.g., says "present" when negated), gets the temporal ordering wrong, attributes a condition to the wrong person, or contains a hallucination contradicted by the source context. |
| **Indeterminate** | `MA_INDETERMINATE` | The model answer is too vague, off-topic, or malformed to evaluate. The model may have refused to answer or produced irrelevant output. |

### 4.3 Automated Evaluator Fairness

Finally, the reviewer assesses whether the automated score was fair (this is revealed AFTER the reviewer submits their gold-standard and model-answer ratings, to prevent anchoring):

| Rating | Code | Definition |
|---|---|---|
| **Fair** | `AUTO_FAIR` | The automated score (correct/incorrect) matches the reviewer's clinical assessment. |
| **Too strict** | `AUTO_STRICT` | The automated evaluator marked the answer incorrect, but the reviewer judges it correct or partially correct. (False negative by the evaluator.) |
| **Too lenient** | `AUTO_LENIENT` | The automated evaluator marked the answer correct, but the reviewer judges it incorrect or only partially correct. (False positive by the evaluator.) |

### 4.4 Clinical Safety Flag

For any item where the model answer could lead to patient harm if acted upon (e.g., affirming a negated condition, missing an active problem), the reviewer sets a binary safety flag:

- `SAFETY_CONCERN = true` -- This error could lead to clinical harm.
- `SAFETY_CONCERN = false` -- This error is benign or unlikely to affect clinical decisions.

### 4.5 Free-Text Notes

An optional field for the reviewer to explain their reasoning, flag gold-standard issues, or note ambiguities. Required when `GS_INCORRECT` or `GS_AMBIGUOUS` is selected.

---

## 5. Inter-Rater Reliability

### 5.1 Primary Metric

**Cohen's kappa** on the 3-class model answer assessment (`MA_CORRECT`, `MA_PARTIAL`, `MA_INCORRECT`; `MA_INDETERMINATE` excluded from kappa calculation).

Interpretation thresholds (Landis & Koch 1977):
- kappa < 0.20: Poor agreement
- 0.21-0.40: Fair
- 0.41-0.60: Moderate
- 0.61-0.80: Substantial
- 0.81-1.00: Almost perfect

**Target: kappa >= 0.60** (substantial agreement). If kappa < 0.40 after the first 50 items, the protocol calls for a calibration session (see Section 5.3).

### 5.2 Secondary Metrics

- Cohen's kappa on gold-standard quality (`GS_CORRECT` vs. not).
- Cohen's kappa on automated evaluator fairness (`AUTO_FAIR` vs. not).
- Percent agreement on the binary safety flag.
- Category-stratified kappa (reported per ClinicalBench category).

### 5.3 Calibration

Before beginning the full review:
1. Both reviewers independently score the same 10 calibration items (drawn from the same pool but excluded from final analysis).
2. Reviewers meet to discuss discrepancies and align on rubric interpretation.
3. Calibration items are discarded; the 336 study items are then scored independently.

If kappa < 0.40 at the 50-item checkpoint:
1. Pause scoring.
2. Identify systematic disagreement patterns (e.g., one reviewer consistently rates uncertainty answers as partial while the other rates them correct).
3. Hold a reconciliation discussion on the disagreement pattern.
4. Re-score the first 50 items (both reviewers) and resume.

---

## 6. Disagreement Resolution

### 6.1 Definition of Disagreement

A disagreement occurs when the two reviewers' model answer ratings differ by more than one level:
- `CORRECT` vs. `INCORRECT` = disagreement (requires resolution)
- `CORRECT` vs. `PARTIAL` = minor disagreement (recorded but not escalated)
- `PARTIAL` vs. `INCORRECT` = minor disagreement (recorded but not escalated)

### 6.2 Resolution Process

1. **Third adjudicator** (a board-certified physician not involved in the primary review) independently scores all major disagreements using the same blinded form.
2. **Majority rule**: The final rating is whichever rating 2 of 3 reviewers agree on.
3. If all three disagree (3-way split), the item is flagged as `UNRESOLVED` and excluded from evaluator accuracy calculations (but reported in the paper).

### 6.3 Minor Disagreement Handling

For CORRECT vs. PARTIAL and PARTIAL vs. INCORRECT splits:
- Both ratings are recorded.
- For the purpose of computing evaluator error rates, PARTIAL is treated as a separate category (not collapsed).
- Sensitivity analysis: report evaluator error rates under both "strict" (PARTIAL = INCORRECT) and "lenient" (PARTIAL = CORRECT) interpretations.

---

## 7. What This Validates

### 7.1 Primary Validation Targets

| Target | How Measured | Reported As |
|---|---|---|
| **Keyword evaluator accuracy** | % of ClinicalBench items where AUTO_FAIR = true | Evaluator precision/recall for each category |
| **LLM-judge accuracy** | % of SliceBench items where AUTO_FAIR = true | Judge agreement rate with physicians |
| **Gold-standard quality** | % of items where GS_CORRECT = true | Gold standard error rate, by category |
| **Category-specific evaluator bias** | AUTO_STRICT vs. AUTO_LENIENT rates per category | Directional bias (strict vs. lenient) per category |

### 7.2 Specific Hypotheses Tested

1. **The keyword evaluator is too strict on uncertainty and sequence categories** (as suggested by the pilot, n=5). Predicted: AUTO_STRICT rate > 20% for uncertainty and sequence; < 10% for negation.

2. **The keyword evaluator misses semantically correct answers that use different phrasing.** Predicted: AUTO_STRICT errors concentrate on categories with free-form answers (change, duration, current_state) rather than categories with constrained keyword sets (negation).

3. **The LLM-as-judge is more lenient than physicians.** Predicted: AUTO_LENIENT rate for SliceBench > AUTO_LENIENT rate for ClinicalBench (because the LLM judge may accept plausible-sounding but clinically imprecise answers).

4. **Gold-standard errors are non-uniform across categories.** Predicted: GS error rate is higher for change and current_state (which depend on cross-admission inference) than for negation (which is locally verifiable in a single note excerpt).

### 7.3 What This Does NOT Validate

- The choice of benchmark questions (topic coverage, difficulty distribution)
- The representativeness of the 45 MIMIC-IV patients
- Whether the conditions (C1, C4, C4g, etc.) are correctly implemented
- Multi-site generalizability

---

## 8. Practical Considerations

### 8.1 Physician Qualifications

- Board-certified or board-eligible in internal medicine, emergency medicine, or a medical subspecialty.
- Active clinical practice (at least 0.5 FTE clinical time) to ensure familiarity with current clinical documentation patterns.
- Prior experience with clinical NLP evaluation preferred but not required.

### 8.2 MIMIC-IV Data Access

**All three physician reviewers must hold active PhysioNet Credentialed Health Data Use Agreements** for MIMIC-IV (v1.5.0 or later). This is required because:
- Review items include verbatim MIMIC-IV clinical note excerpts.
- Reviewers may need to consult the full clinical record for context (especially for cross-admission questions).
- The PhysioNet DUA prohibits sharing credentialed data with uncredentialed individuals.

**Process:**
1. Physicians who do not already have PhysioNet access must complete the CITI "Data or Specimens Only Research" course and apply at https://physionet.org.
2. Approval typically takes 1-2 weeks.
3. The review materials will be distributed via a secure system accessible only to credentialed users (not email).

### 8.3 IRB Considerations

MIMIC-IV is a de-identified dataset approved for research under a blanket IRB waiver from the MIT Committee on the Use of Humans as Experimental Subjects. Physician adjudication of system outputs derived from MIMIC-IV falls under this existing authorization and does not constitute human subjects research (no new data collection from patients). A local IRB determination of "not human subjects research" should be obtained from each reviewer's institution if required by institutional policy.

### 8.4 Review Platform

A web-based review interface (already partially built at `/validate` in the frontend) presents:
- Randomized items with the fields described in Section 3.
- Radio buttons for each rating scale.
- Free-text notes field.
- Progress tracker.
- Items are saved after each submission; reviewers can pause and resume.

The automated evaluator score is hidden during initial review and revealed only after the reviewer submits their assessment (two-phase display).

### 8.5 Timeline

| Milestone | Target Date | Duration |
|---|---|---|
| Protocol finalization and IRB determination | Week 0 | 1 week |
| PhysioNet credentialing (if needed) | Weeks 0-2 | 1-2 weeks |
| Calibration session (10 items, both reviewers) | Week 2 | 1 session (2 hours) |
| Independent review (336 items each) | Weeks 2-5 | 3 weeks (4-5 hrs/week) |
| Inter-rater reliability analysis | Week 5 | 2 days |
| Third adjudicator resolves disagreements | Weeks 5-6 | 1 week |
| Final analysis and paper integration | Week 6 | 3 days |

### 8.6 Compensation

Physician reviewers should be compensated at a rate commensurate with clinical consultation ($150-250/hour is typical for medical record review in research settings). Estimated total: $2,000-4,500 per primary reviewer; $500-1,500 for the third adjudicator (disagreement resolution only).

---

## 9. How Results Feed Back Into the Paper

### 9.1 Evaluator Error Rate Reporting

For each ClinicalBench category, report:
- **Keyword evaluator false-negative rate** (AUTO_STRICT / total items in category): How often the keyword evaluator marks a clinically correct answer as incorrect.
- **Keyword evaluator false-positive rate** (AUTO_LENIENT / total items in category): How often it marks a clinically incorrect answer as correct.

For SliceBench overall:
- **LLM-judge agreement rate** with physician consensus.
- **Directional bias** (strict vs. lenient).

### 9.2 Recalibrated Accuracy Estimates

Using the physician adjudication as ground truth, compute a recalibrated accuracy for each condition:

```
Recalibrated_Accuracy(condition) =
    Automated_Accuracy(condition)
    + (evaluator_false_negative_rate * fraction_scored_incorrect)
    - (evaluator_false_positive_rate * fraction_scored_correct)
```

This is reported as a sensitivity analysis in the paper -- the headline numbers remain the automated scores (for reproducibility), with physician-recalibrated estimates in a companion table.

### 9.3 Gold-Standard Corrections

If physician review identifies gold-standard errors (GS_INCORRECT or GS_AMBIGUOUS):
1. Document each error with the reviewer's rationale.
2. Correct the gold standard and re-run the keyword evaluator.
3. Report both original and corrected results.
4. If gold-standard corrections change any headline finding (e.g., reverse the sign of a condition delta), this is reported prominently.

### 9.4 Paper Text Updates

The current paper text (Appendix A.9) states:

> "A full two-physician blinded adjudication (n >= 30) is planned but not yet complete."

Upon completion, this will be replaced with:
- Sample size and stratification details.
- Cohen's kappa for model answer rating and evaluator fairness.
- Per-category evaluator error rates.
- Recalibrated accuracy table.
- Any gold-standard corrections.

### 9.5 Reporting Transparency

All physician ratings will be released as a supplementary JSONL file with the following fields per item:

```json
{
  "item_id": "VAL_0042",
  "question_id": "bench_a_uncertainty_4d840683",
  "category": "uncertainty",
  "benchmark": "clinicalbench",
  "reviewer_id": "R1",
  "gold_standard_rating": "GS_CORRECT",
  "model_answer_rating": "MA_PARTIAL",
  "auto_evaluator_fairness": "AUTO_STRICT",
  "safety_concern": false,
  "notes": "",
  "timestamp": "2026-03-15T10:23:00Z"
}
```

---

## Appendix: Category-Specific Scoring Guidance

To help calibrate reviewer expectations:

**Negation:** The model must correctly identify that a condition is negated/absent. Saying "no evidence of X" or "X is denied" both count as correct. Saying "the patient was evaluated for X" without affirming or negating is PARTIAL.

**Uncertainty:** The model must convey diagnostic uncertainty. Acceptable phrasings include "possible," "suspected," "not confirmed," "may have," or clinical hedging language ("concerning for," "suggestive of"). Simply naming the condition without a qualifier is INCORRECT.

**Conditional:** The model must identify that a clinical action or finding is contingent on a condition. The key test: does the answer convey "if X, then Y" or "depending on Z"?

**Family history:** The model must correctly attribute a condition to a family member (not the patient). Saying "the patient has a family history of X" is CORRECT. Saying "the patient has X" when only the family member does is INCORRECT.

**Sequence:** The model must identify the correct temporal ordering of two events. Getting the order reversed is INCORRECT. Identifying both events without ordering them is PARTIAL.

**Current state:** The model must identify whether a condition is currently active. Saying "currently active" or "ongoing" is CORRECT for active conditions. Saying "history of" for a currently active condition is INCORRECT.

**Historical:** The model must identify a condition as past/resolved. Saying "formerly" or "resolved" is CORRECT. Saying "the patient has X" (implying current) for a resolved condition is INCORRECT.

**Duration:** The model must provide temporal duration information (chronic vs. new, number of admissions, approximate timeframe). Vague answers ("has been present") without duration information are PARTIAL.

**Change:** The model must identify what changed between admissions (added, removed, or continued conditions/medications). Identifying the concepts without classifying the change direction is PARTIAL.
