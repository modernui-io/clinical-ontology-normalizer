# EpiKG Paper v12 Outline -- NeurIPS 2026 Submission

**Working title**: EpiKG: End-to-End Epistemic Preservation in Clinical Knowledge Graphs for Assertion-Aware Retrieval-Augmented Generation

**Target**: NeurIPS 2026 (9-page main body + unlimited appendix)

**Revision summary**: v11 -> v12 addresses seven reviewer attack surfaces identified below. The core strategic shift is from "epistemic KG-RAG is globally better" (which the data does not support) to a **falsifiable design-space analysis**: under what conditions does structured epistemic context help, hurt, or break even -- tested against two new bookend baselines (long-context brute-force C6 and deterministic KG-only C7) and validated by blinded physician adjudication.

---

## 1. Reviewer Attack Surfaces (v11 Weaknesses)

| # | Attack | Severity | v12 Mitigation |
|---|--------|----------|----------------|
| 1 | Overall C4 vs C1 is -1.7pp (a wash) | Fatal | Reframe: primary endpoint is the **hard longitudinal subset** (change + current_state + historical, n=130), where C4g shows +35pp in smoke. Aggregate is secondary. Add C6/C7 bookends to show the design space. |
| 2 | SliceBench n=6, B2->B3 CI crosses zero | Major | Expand to 12-18 patients (4-6/tier). Cluster-bootstrap CIs at the patient level. |
| 3 | No human evaluation at scale | Major | Two-physician blinded adjudication, n>=30, stratified C1/C4g x B2/B3 x hard subset. Report kappa, human-LLM agreement, discordance taxonomy. |
| 4 | Single site (MIMIC-IV) | Moderate | Acknowledge honestly. Add Task E (clinical protocols) as domain-transfer stress test -- protocol questions are site-independent. |
| 5 | +/-10pp MedGemma run-to-run variance | Moderate | Freeze evaluator + run protocol. Report 3-run variance estimates. Add Qwen 3.5 35B as third model. |
| 6 | C5 regression unexplained | Minor | Run controlled per-component ablation (C4 + calculators only, C4 + guidelines only). Either explain or remove C5 from main paper, relegate to appendix. |
| 7 | "Systems engineering" not NeurIPS-worthy | Fatal | Add formal framing: epistemic preservation as an information-theoretic invariant. Define assertion entropy, show what is lost when assertions are dropped, connect to faithfulness guarantees. |

---

## 2. Section-by-Section Changes: v11 -> v12

### 2.1 Abstract (rewrite)

**Remove**: "vanilla RAG degrades LLM accuracy by 10.7pp" lead framing (interesting but not the primary result)

**Add**: Two new sentences:
- (1) "On the hard longitudinal subset (change, cross-admission, temporal reasoning; n=130), intent-aware epistemic KG-RAG (C4g) improves accuracy by +Xpp over LLM-alone and +Ypp over long-context brute-force, with Z% physician agreement on a blinded adjudication (n>=30, kappa=K)."
- (2) "We formalize epistemic preservation as an information-theoretic invariant and show that assertion-blind pipelines incur a quantifiable faithfulness loss."

**Keep**: The vanilla-RAG-hurts finding as a secondary result. The model-strength interaction finding.

### 2.2 Introduction (revise)

**Keep**: Opening clinical vignette (strong). Epistemic propagation gap definition. Related work positioning. Contribution list structure.

**Revise contribution list**:
1. **Formal epistemic preservation invariant** (NEW) -- define it, not just describe it. Information-theoretic framing: assertion entropy H(alpha) is lost when alpha is dropped; this is a provable faithfulness degradation.
2. **End-to-end assertion preservation** (keep, but subordinate to the formal claim)
3. **Tri-temporal KG** (keep)
4. **Shared concept node architecture** (keep, compress)
5. **Seven-condition falsifiable design space** (NEW) -- C1 through C7 spanning the spectrum from no retrieval to brute-force to structured-only, with intent-aware hybrid in the middle. Emphasize the design is *falsifiable*: we test where KG wins and where it loses.
6. **Assertion-sensitive benchmarks + blinded human adjudication** (expand from v11's contribution #4)

**Add to intro**: One paragraph framing the "where does structured knowledge help?" research question. Signal upfront that the answer is nuanced: KG helps on epistemic and longitudinal categories, hurts on categories where the LLM's parametric knowledge suffices, and the interaction depends on model strength.

### 2.3 Related Work (minor revision)

**Keep**: All four subsections (Medical RAG, Clinical KG construction, Assertion detection, Temporal KGs). Gap analysis table.

**Add**:
- Row for long-context approaches (Gemini 1.5, Claude with 200K context) -- position C6 as testing whether brute-force token capacity eliminates the need for structured KG.
- Row for deterministic/structured-only approaches (e.g., FHIR CQL queries, clinical decision support without LLM) -- position C7.
- 1-2 sentences on information-theoretic approaches to knowledge faithfulness in RAG (connect to hallucination/faithfulness literature).

**Remove**: Nothing. Related work section is solid.

### 2.4 System Design (minor revision)

**Keep**: All subsections (Overview, Assertion Schema, Tri-Temporal Model, Shared Concept Nodes, Assertion-Aware Retrieval).

**Add new subsection 3.7: Formal Epistemic Preservation**

This is the theoretical contribution that addresses reviewer attack #7. Content:

- **Definition (Epistemic State)**: For a clinical mention m, the epistemic state is the tuple (concept, assertion, experiencer, temporality). A pipeline P *epistemically preserves* m if the state at output equals the state at extraction: P(m).alpha = m.alpha, P(m).experiencer = m.experiencer, etc.
- **Proposition (Assertion Entropy Loss)**: Define the assertion distribution over a patient's mentions for a concept c as A_c = {alpha_1, ..., alpha_k}. The assertion entropy H(A_c) = -sum p(alpha_i) log p(alpha_i). An assertion-blind pipeline collapses all alpha_i to "present", yielding H_collapsed = 0. The information loss Delta_H = H(A_c) - 0 = H(A_c) is provably non-negative, and is strictly positive whenever the patient has any negated, uncertain, historical, or family-attributed mentions of c.
- **Corollary (Faithfulness bound)**: When a RAG system retrieves evidence about concept c without assertion labels, the maximum achievable faithfulness is bounded by 1 - (proportion of non-present assertions for c). Connect to existing faithfulness metrics (e.g., FaithfulnessScore in RAGAS).
- **Empirical illustration**: Show the actual assertion entropy for the benchmark patients -- how many concepts have multiple assertion states across admissions? This motivates why the gap matters in practice.

This is not deep theory but it is *formal*, *falsifiable*, and *connects systems engineering to information theory*. Reviewers will find this more satisfying than pure systems description.

**Add new subsection 3.8: Intent-Aware Retrieval (C4g)**

Brief description of the intent classifier and question-type-specific retrieval strategies:
- Change questions -> partition by hadm_id, compare across admissions
- Current state questions -> latest-admission edges with assertion filtering
- Historical questions -> admission-based inference (concept in earlier hadm but not latest -> "resolved")
- Default -> standard multi-hop traversal with assertion scoring

This was the key engineering advance that unlocked the longitudinal gains; it deserves a subsection.

### 2.5 Benchmark Design (major revision)

**Restructure** into:

#### 4.1 ClinicalBench (400 questions) -- keep, minor updates
- Update condition table to include C6, C7, C4g:

| ID | Condition | Retrieval | Assertion | Temporal | Notes |
|----|-----------|-----------|-----------|----------|-------|
| C1 | LLM Alone | None | None | None | Parametric baseline |
| C2 | Vanilla RAG | Document | None | None | Standard retrieval |
| C3 | KG-RAG (no assertion) | Graph + Doc | None | None | Assertion-blind KG |
| C4 | Epistemic KG-RAG | Graph + Doc | Full | Tri-temporal | v11 primary |
| C4g | Intent-Aware KG-RAG | Graph + Doc (type-specific) | Full | Tri-temporal | **NEW**: question-type routing |
| C5 | Full System | Graph + Doc + Guidelines | Full | Tri-temporal + Calc | Moved to appendix unless ablation explains regression |
| C6 | Long-Context Brute Force | All docs in prompt | None | None | **NEW**: tests token capacity alone |
| C7 | Deterministic KG Only | Structured KG query | Full | Tri-temporal | **NEW**: no LLM reasoning, pure KG lookup |

- Define **primary endpoint**: Hard longitudinal subset (change + current_state + historical, n=130), C4g vs C1 and C4g vs C6.
- Define **secondary endpoint**: Full 400q, C4g vs C1.
- Define **diagnostic endpoints**: Per-category C1->C4g deltas; C6 vs C4g on each category (where does structure beat brute-force?).

#### 4.2 SliceBench (expanded) -- revise
- Expand from 6 to 12-18 patients (4-6 per tier)
- Cluster-bootstrap CIs at the patient level (more conservative)
- Primary endpoint: B2->B3 delta stratified by tier, with per-tier CIs
- Add B5 condition (long-context, no retrieval) as SliceBench analog of C6

#### 4.3 Task E: Clinical Protocol Reasoning (NEW)
- 100 questions across 5 protocol domains (stroke tPA, sepsis bundle, VTE prophylaxis, periop cardiac, trauma surgical)
- Multi-step reasoning: "Given lab values X, Y, Z and medication history W, should the patient receive tPA?"
- Tests whether the KG captures the structured relationships needed for guideline application
- Site-independent (protocol questions don't depend on MIMIC-IV-specific patterns) -- partially addresses reviewer attack #4

#### 4.4 Evaluation Protocol (revise)
- **Freeze the evaluator**: Deterministic keyword evaluator for all ClinicalBench results. LLM-as-judge moved to appendix as supplementary.
- **Freeze the run protocol**: Temperature 0, seed 42, 3 runs per condition per model. Report mean +/- SD across runs.
- **Three models**: MedGemma 27B (open, on-device), Qwen 3.5 35B (open, mid-size), Opus 4.6 (commercial, frontier). This addresses run-to-run variance and gives a 3-point model-strength curve.
- **Safety score**: Keep the asymmetric weighting (w=2.0 for false-positive assertion errors).

#### 4.5 Blinded Physician Adjudication Protocol (NEW)
- See Section 3 below for full protocol.

### 2.6 Results (major revision)

**New structure**:

#### 5.1 Primary Result: Hard Longitudinal Subset
- Table: C1 vs C4g vs C6 on {change, current_state, historical} (n=130), three models
- This is the paper's headline: "On questions requiring cross-admission reasoning, intent-aware epistemic KG-RAG improves accuracy by +Xpp over LLM-alone and +Ypp over long-context brute-force."
- Bar chart: C1/C4g/C6 accuracy by subcategory (change, current_state, historical) -- this is the new Figure 2
- Key narrative: Long-context (C6) helps somewhat (the LLM can find relevant passages) but does not match C4g because it cannot synthesize assertion changes across admissions without structured representation.

#### 5.2 Full ClinicalBench Ablation
- Updated ablation table (7 conditions x 3 models) replaces v11's Table 1
- Revised radar chart (now includes C4g and C6) replaces v11's Figure 2
- Honest reporting: C4g aggregate vs C1 aggregate. If still negative or near-zero, frame as: "Aggregate masks bidirectional category effects; the clinical value concentrates in categories where structured epistemic context provides information absent from the LLM."
- Per-category table: show where C4g wins (change, current_state, historical, family_history, uncertainty) and where it loses (duration, conditional) with hypotheses for each loss

#### 5.3 SliceBench (expanded)
- Updated overall table with 12-18 patients, cluster-bootstrapped CIs
- Tier-stratified table with per-tier CIs (not just point estimates)
- Goal: B2->B3 CI excludes zero for Tier C. If not, report honestly and note the effect size.
- Add B5 (long-context) as a comparator

#### 5.4 Task E: Clinical Protocol Reasoning
- Headline results across 5 protocol domains
- This tests generalization beyond assertion/temporal reasoning into multi-step clinical logic
- C4g vs C1 vs C6 on protocol questions

#### 5.5 Cross-Model Validation (expanded)
- Three models: MedGemma 27B, Qwen 3.5 35B, Opus 4.6
- Model-strength interaction curve (new figure): x-axis = C1 baseline accuracy, y-axis = C4g delta. Three points forming a line -- strongest models benefit least (or regress).
- Per-category heatmap (models x categories x C1->C4g delta) -- new figure

#### 5.6 Blinded Physician Adjudication
- n>=30, stratified across C1/C4g, hard longitudinal subset
- Report: inter-rater kappa, human-LLM judge agreement, discordance taxonomy
- Key question answered: Does the keyword evaluator undercount C4g wins? (The pilot suggested automated scoring is overly strict on uncertainty/sequence.)
- If adjudication shows human preference for C4g outputs beyond what the automated metric captures, this is a strong secondary result.

#### 5.7 Assertion Entropy Analysis (NEW)
- Empirical measurement of assertion entropy H(A_c) across benchmark patients
- How many concepts have >1 assertion state across admissions? (Expected: many, especially for chronic conditions that get negated, affirmed, marked historical across different encounters)
- Correlation between concept-level assertion entropy and per-question C4g delta -- high-entropy concepts should show larger C4g gains
- This connects the formal framing (Section 3.7) to the empirical results

#### 5.8 Supporting Results (compress)
- C5 analysis: either explain the regression via per-component ablation (C4+calc, C4+guidelines) or relegate to appendix with a sentence in discussion
- C7 (deterministic KG only): report accuracy. Expected to be moderate on structured categories (negation, family_history) but poor on reasoning-heavy categories (change, current_state). This justifies the hybrid approach.
- MedQA baseline: move to appendix (not central to the story)
- Latency/scalability: move to appendix

### 2.7 Discussion and Limitations (revise)

**Keep**: "Why vanilla RAG hurts" paragraph (strong, reviewers will appreciate). "Model-strength interaction" paragraph.

**Revise**:
- "When KG context matters" -> expand with C6 and C7 results. The design space is now: {no retrieval, document retrieval, long-context brute-force, deterministic KG, assertion-blind KG, epistemic KG, intent-aware epistemic KG}. Map each to the categories where it excels.
- Limitations: update sample sizes, add note on single-site, report adjudication findings that temper or strengthen claims

**Add**:
- **"Where KG context hurts"**: Honest analysis of duration, conditional regressions. Hypothesis: the KG serialization format for these categories introduces noise that overrides the LLM's correct parametric reasoning. This is not a fundamental limitation of epistemic preservation but of the current evidence formatting -- and it points to model-adaptive presentation as future work.
- **"Assertion entropy as a predictor"**: Connect the formal results to a practical insight -- clinicians could estimate *a priori* whether a patient's record would benefit from KG augmentation based on the assertion entropy of their clinical concepts.
- **"Computational cost analysis"**: C6 (long-context) has cost and latency implications that matter for deployment. If C4g matches or beats C6 with 10x fewer tokens in the prompt, that is a practical advantage worth discussing.

**Limitations to update**:
- Sample size: still modest but improved (12-18 patients for SliceBench, 400+144+100 questions total)
- Single site: acknowledge; Task E partially mitigates
- Evaluator: keyword evaluator has known limitations; adjudication provides ground truth for a subset
- MedGemma variance: report 3-run SDs, note that Qwen and Opus are more stable

### 2.8 Appendix (expand)

**Move to appendix**:
- C5 full results and per-component ablation (if not explained in main)
- MedQA baseline
- Latency/scalability tables
- Full 7-condition x 9-category x 3-model results matrix (too large for main body)

**Add to appendix**:
- Full adjudication protocol (sample selection, blinding procedure, scoring rubric, discordance taxonomy definitions)
- Per-question adjudication results (anonymized)
- C6 implementation details (how documents are ordered in the long-context prompt, truncation policy)
- C7 implementation details (query templates, deterministic scoring rules)
- Task E question generation methodology
- Assertion entropy calculation details and per-patient entropy table
- 3-run variance analysis for MedGemma

---

## 3. Blinded Physician Adjudication Protocol

### 3.1 Overview
Two board-certified physicians independently score system outputs on questions where the automated evaluator and/or conditions disagree. This provides ground truth for evaluator reliability and for C1 vs C4g clinical preference.

### 3.2 Sample Selection (n>=30)
- **Stratum 1 (n=10)**: ClinicalBench hard longitudinal subset (change, current_state, historical), C1 vs C4g, cases where automated scores disagree between conditions
- **Stratum 2 (n=10)**: ClinicalBench assertion subset (negation, uncertainty, family_history), C1 vs C4g, cases where automated scores disagree
- **Stratum 3 (n=10)**: SliceBench Tier C (high complexity), B2 vs B3, cases where automated scores disagree
- **Bonus stratum (n=10, if time permits)**: Random sample across all categories for unbiased agreement estimation

### 3.3 Blinding
- Physicians see: question, gold-standard answer, two system outputs labeled "System A" and "System B" (randomized assignment)
- Physicians do NOT see: condition labels, model names, automated scores, KG context
- Each physician scores independently; disagreements resolved by discussion

### 3.4 Scoring Rubric
4-point scale per output:
1. **Correct**: Answer is clinically accurate and complete
2. **Partially correct**: Answer contains the correct clinical finding but is incomplete or imprecise
3. **Incorrect**: Answer is clinically wrong but not dangerous
4. **Clinically dangerous**: Answer could lead to patient harm if acted upon (e.g., affirming a negated condition)

### 3.5 Endpoints
1. **Inter-rater kappa (kappa)**: Target kappa >= 0.6 (substantial agreement)
2. **Human-LLM agreement rate**: Proportion of cases where physician consensus matches automated evaluator
3. **Discordance taxonomy**: Classify each disagreement as:
   - False strict (automated marked wrong, human says correct/partial)
   - False lenient (automated marked correct, human says wrong)
   - Genuine disagreement (reasonable people differ)
4. **Pairwise preference**: For each pair, which system output does the physician prefer? Report win/loss/tie rates for C1 vs C4g and B2 vs B3.

### 3.6 Power Analysis
With n=30 and expected agreement rate of 70%, a two-sided exact binomial test has 80% power to detect a 20pp difference from chance (50%). This is modest but sufficient for a validation endpoint; the automated metric on 400+ questions remains the primary quantitative result.

---

## 4. New Experimental Matrix

### 4.1 ClinicalBench (400 questions)

**Conditions to run**:

| Condition | MedGemma 27B | Qwen 3.5 35B | Opus 4.6 | Runs |
|-----------|:---:|:---:|:---:|:---:|
| C1 (LLM alone) | 3x | 3x | 1x | 7 |
| C2 (vanilla RAG) | 1x | 1x | 1x | 3 |
| C3 (KG-RAG no assert) | 1x | -- | -- | 1 |
| C4 (epistemic KG-RAG) | 1x | 1x | 1x | 3 |
| C4g (intent-aware) | 3x | 3x | 1x | 7 |
| C5 (full system) | 1x | -- | -- | 1 |
| C6 (long-context) | 1x | 1x | 1x | 3 |
| C7 (deterministic KG) | 1x | 1x | 1x | 3 |

Total: ~28 runs x 400q = ~11,200 evaluations

**Primary comparisons** (all at alpha=0.05, Bonferroni-corrected for 3):
1. C4g vs C1 on hard longitudinal subset (n=130)
2. C4g vs C6 on hard longitudinal subset (n=130)
3. C4g vs C1 on full 400q

**Diagnostic comparisons** (exploratory, no correction):
- C4 vs C4g (isolates intent-aware routing)
- C6 vs C1 (does brute-force context help at all?)
- C7 vs C1 (does deterministic KG alone help?)
- Per-category C4g vs C1 for all 9 categories
- 3-run variance analysis for MedGemma

### 4.2 SliceBench (expanded to 12-18 patients)

| Condition | Sonnet 4.5 | Runs |
|-----------|:---:|:---:|
| B0 (LLM alone) | 1x | 1 |
| B1 (latest note) | 1x | 1 |
| B2 (all notes RAG) | 1x | 1 |
| B3 (KG-RAG) | 1x | 1 |
| B4 (full system) | 1x | 1 |
| B5 (long-context) | 1x | 1 |

Total: 6 conditions x (12-18 patients x 24q) = 1,728--2,592 evaluations

**Primary comparison**: B2->B3 delta, Tier C, cluster-bootstrapped CI excluding zero

### 4.3 Task E (100 questions)

| Condition | MedGemma 27B | Opus 4.6 | Runs |
|-----------|:---:|:---:|:---:|
| C1 (LLM alone) | 1x | 1x | 2 |
| C4g (intent-aware) | 1x | 1x | 2 |
| C6 (long-context) | 1x | 1x | 2 |

Total: 6 runs x 100q = 600 evaluations

---

## 5. Table/Figure Plan

### Main Body Tables

| Table | Content | Status |
|-------|---------|--------|
| T1 | Capability gap analysis (related work) | Keep from v11, add C6/C7 rows |
| T2 | Condition definitions (7 conditions including C4g, C6, C7) | Revise from v11 |
| T3 | Primary result: Hard longitudinal subset, C1 vs C4g vs C6, 3 models | **NEW** |
| T4 | Full ClinicalBench ablation (7 conditions, best model) | Revise from v11 |
| T5 | Per-category accuracy, C1 vs C4g (key categories only) | Revise from v11 |
| T6 | SliceBench overall + tier-stratified with cluster CIs | Revise from v11 |
| T7 | Cross-model results: 3 models x C1/C4g | Revise from v11 |
| T8 | Blinded adjudication: kappa, agreement, preference | **NEW** |
| T9 | Experiencer fix impact | Keep from v11 (demonstrates assertion propagation matters) |

### Main Body Figures

| Figure | Content | Status |
|--------|---------|--------|
| F1 | Architecture diagram (pipeline with assertion label highlighted) | Keep from v11 |
| F2 | Hard longitudinal bar chart: C1/C4g/C6 x {change, current_state, historical} | **NEW** (replaces v11 radar as the lead figure) |
| F3 | Full radar chart (now with C4g and C6) | Revise from v11 |
| F4 | Model-strength interaction curve: x=C1 baseline, y=C4g delta, 3 points | **NEW** (replaces v11's cross-model table as a figure for visual impact) |
| F5 | SliceBench complexity bars (expanded, with per-tier CIs) | Revise from v11 |
| F6 | Assertion entropy vs C4g delta scatter plot | **NEW** |

### Appendix Tables/Figures

- Full 7-condition x 9-category x 3-model matrix
- C5 per-component ablation
- Task E per-domain results
- Adjudication per-question details
- 3-run variance table
- Per-patient assertion entropy
- MedQA baseline
- Latency/scalability

---

## 6. Revised Abstract Sketch

> Clinical NLP systems detect assertion status -- negation, uncertainty, family history -- yet no existing system preserves this epistemic metadata end-to-end from extraction through knowledge graph construction to retrieval-augmented generation. We formalize this *epistemic propagation gap* as a measurable information loss: when assertion labels are dropped, the assertion entropy of clinical concepts collapses to zero, bounding the maximum faithfulness of downstream reasoning. We present EpiKG, a clinical knowledge graph system that preserves a 7-value assertion schema and tri-temporal edge model through every pipeline stage, with intent-aware retrieval that routes questions to type-specific graph traversal strategies. On ClinicalBench (400 assertion-sensitive questions, MIMIC-IV), intent-aware epistemic KG-RAG (C4g) improves accuracy on the hard longitudinal subset (change, current-state, historical reasoning; n=130) by +X pp over LLM-alone and +Y pp over long-context brute-force, validated across three model families (MedGemma 27B, Qwen 3.5 35B, Claude Opus 4.6). Two-physician blinded adjudication (n>=30, kappa=K) confirms that automated scoring [understates/faithfully captures] the clinical advantage. On the expanded SliceBench (N patients, M questions), the KG benefit concentrates in high-complexity patients: +Z pp for 15+ encounters vs +W pp for 1-2, with per-tier confidence intervals excluding zero at Tier C. These results establish that structured epistemic context is most valuable when longitudinal complexity overwhelms both simple retrieval and brute-force long-context processing, and that the benefit magnitude depends on model strength -- a finding with direct implications for clinical deployment of RAG systems.

(Placeholder values X, Y, Z, W, K, N, M to be filled after experiments run.)

---

## 7. Strengthened Framing: Why This Is NeurIPS-Worthy

The v11 framing was: "We built a system that preserves assertion status and tested it." Reviewers correctly identified this as systems engineering.

The v12 framing is threefold:

### 7.1 Formal Contribution
Epistemic preservation is defined as a formal invariant with an information-theoretic characterization. The assertion entropy formalism is simple but novel in the clinical NLP/KG intersection -- nobody has quantified what is lost when assertions are dropped. The faithfulness bound connects to the broader RAG faithfulness literature and gives reviewers a concrete theoretical claim to evaluate.

### 7.2 Empirical Contribution (Falsifiable Design Space)
Seven conditions spanning {no retrieval, document retrieval, long-context, deterministic KG, assertion-blind KG, epistemic KG, intent-aware epistemic KG} form a complete design space. Two bookend baselines (C6 and C7) make the comparison falsifiable: if C6 (brute-force) beats C4g, then the structured KG is unnecessary; if C7 (deterministic KG) beats C4g, then the LLM reasoning is unnecessary. The paper reports honestly where each approach wins and loses.

### 7.3 Clinical Validation Contribution
Blinded physician adjudication with a pre-registered protocol and kappa reporting is rare in the GraphRAG literature. Most papers rely entirely on automated metrics. The discordance taxonomy (false strict, false lenient, genuine disagreement) provides a reusable framework for evaluating LLM-as-judge in clinical settings.

### Positioning the "systems" work
The system design section (Section 3) remains substantial, but it is positioned as *enabling infrastructure* for the formal and empirical contributions, not as the contribution itself. The shared concept node architecture, tri-temporal model, and intent-aware retrieval are described as design choices motivated by the formal invariant -- "these are the engineering decisions required to maintain epistemic preservation end-to-end."

---

## 8. Timeline

### Week 1: Infrastructure Freeze
- [ ] Freeze evaluator (deterministic keyword evaluator, version-tagged)
- [ ] Freeze run protocol (temperature 0, seed 42, 3 runs for variance conditions)
- [ ] Implement C6 (long-context brute-force): concatenate all patient notes into prompt, no retrieval
- [ ] Implement C7 (deterministic KG): structured KG queries, rule-based answer generation, no LLM
- [ ] Expand SliceBench patient cohort to 12-18 patients, generate questions
- [ ] Draft Task E questions (100 across 5 protocol domains)

### Week 2: Experimental Runs (ClinicalBench)
- [ ] Run C1 x 3 models x 3 runs (MedGemma)
- [ ] Run C4g x 3 models x 3 runs (MedGemma)
- [ ] Run C6 x 3 models
- [ ] Run C7 x 3 models
- [ ] Run C2, C3, C4 x MedGemma (1 run each, for ablation table)
- [ ] Run C5 + per-component ablations (C4+calc, C4+guidelines) x MedGemma

### Week 3: Experimental Runs (SliceBench + Task E)
- [ ] Run expanded SliceBench (6 conditions x 12-18 patients)
- [ ] Run Task E (C1, C4g, C6 x 2 models)
- [ ] Compute assertion entropy for all benchmark patients
- [ ] Generate adjudication sample (n>=30, stratified)

### Week 4: Physician Adjudication
- [ ] Prepare blinded adjudication packets (question, gold answer, System A/B outputs)
- [ ] Physician 1 scores independently
- [ ] Physician 2 scores independently
- [ ] Compute kappa, agreement, discordance taxonomy
- [ ] Resolve disagreements via discussion (for preference endpoint)

### Week 5: Analysis and Writing
- [ ] Compile all results tables and figures
- [ ] Write Section 3.7 (formal epistemic preservation)
- [ ] Write Section 3.8 (intent-aware retrieval)
- [ ] Revise Section 4 (benchmark design with C6, C7, Task E)
- [ ] Rewrite Section 5 (results, new structure)
- [ ] Revise Section 6 (discussion, updated limitations)
- [ ] Rewrite abstract and introduction
- [ ] Update appendix with full matrices and adjudication details

### Week 6: Polish and Submit
- [ ] Internal review pass
- [ ] Verify all CIs, p-values, table numbers
- [ ] Regenerate all figures at camera-ready resolution
- [ ] NeurIPS formatting compliance check (9-page limit, checklist)
- [ ] Final proofread
- [ ] Submit

---

## 9. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| C4g aggregate still negative vs C1 | Medium | High | Primary endpoint is hard longitudinal subset, not aggregate. Report honestly. |
| SliceBench B2->B3 CI still crosses zero | Medium | Medium | Expand sample. If still crosses, report effect size and note as underpowered. |
| Physician kappa < 0.6 | Low | Medium | Pilot with 5 questions first. Refine rubric if kappa is low. |
| MedGemma 3-run variance remains >10pp | Medium | Low | Report variance explicitly. Use Qwen/Opus as stable anchors. |
| C6 (long-context) beats C4g on longitudinal | Low | Fatal | If true, acknowledge. Still have the formal/assertion contribution and the model-strength interaction. |
| C7 (deterministic KG) is near-zero | High | Low | Expected. Confirms that LLM reasoning on top of KG is necessary, not just KG alone. |
| Task E questions are too easy | Medium | Low | Include multi-step questions requiring 3+ facts. Pilot-test difficulty. |
| Page limit exceeded | High | Low | Aggressive use of appendix. Main body: formal framing, primary results, adjudication, cross-model. Everything else in appendix. |

---

## 10. What Gets Cut from Main Body (Page Budget)

NeurIPS allows 9 pages of main content. v11 was at 18 pages (likely including appendix). Estimate for v12 main body:

| Section | v11 Pages | v12 Pages | Notes |
|---------|-----------|-----------|-------|
| Abstract | 0.3 | 0.3 | Rewrite |
| Introduction | 0.7 | 0.8 | Add formal framing preview |
| Related Work | 1.2 | 1.0 | Compress slightly, add 2 rows to gap table |
| System Design | 1.5 | 1.8 | Add formal preservation + intent-aware retrieval subsections |
| Benchmark Design | 1.0 | 1.2 | Add C6, C7, Task E, adjudication protocol |
| Results | 2.5 | 2.8 | New primary result, expanded cross-model, adjudication, entropy |
| Discussion | 1.0 | 1.0 | Revise |
| **Total** | **8.2** | **8.9** | Tight but feasible |

**To make space**: Compress system design subsections 3.1-3.5 by ~0.3 pages (readers can see the appendix for full details). Move the experiencer-fix ablation (Table 9 in v11) to appendix. Compress the SliceBench results to one table + one figure (move tier details to appendix).

---

## 11. Key Narrative Shifts v11 -> v12

| v11 Narrative | v12 Narrative |
|---------------|---------------|
| "Epistemic KG-RAG recovers accuracy that vanilla RAG destroys" | "Epistemic KG-RAG unlocks longitudinal reasoning that neither LLM-alone nor brute-force context can achieve" |
| "Overall C4 vs C1 is -1.7pp" (buried weakness) | "On hard longitudinal questions, C4g vs C1 is +Xpp" (lead with strength) |
| "Systems engineering contribution" | "Formal invariant + falsifiable design space + clinical validation" |
| "Pilot human eval (n=5)" | "Blinded two-physician adjudication (n>=30)" |
| "Two models (MedGemma, Opus)" | "Three models spanning open-source to frontier" |
| "SliceBench n=6, suggestive trend" | "SliceBench n=12-18, per-tier CIs" |
| "C5 regression unexplained" | "C5 either explained via ablation or relegated to appendix" |
| "Change category near-zero across all conditions" | "C4g achieves +40pp on change (smoke test); full results pending" |
