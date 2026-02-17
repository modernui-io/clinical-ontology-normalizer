# P4-010-I: Causal Reasoning Implementation Constraints

**Task:** P4-010-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Implementation constraints document complete (deferred per ADR)
**ADR Reference:** `docs/decisions/p4-010-causal-inference.md`

## Summary

This document defines the implementation constraints, safety guardrails, and activation pathway for advancing from the current correlation-based causal reasoning service to formal causal inference capabilities. All causal inference activation is gated on five simultaneous trust metric thresholds defined in P4-010-D. Until those thresholds are met, clinical outputs remain labeled as correlation/ranking per the P1-015 closure.

## Current State Assessment

| Component | File | Lines | Key Abstractions | Maturity |
|-----------|------|-------|------------------|----------|
| Causal Reasoning Service | `backend/app/services/causal_reasoning_service.py` | 569 | `CausalRelationType` (10 enum values), `TemporalOrder` (5 enum values), `CausalLink`, `CausalChain`, `CausalQuery`, `CounterfactualQuery`, `CounterfactualResult` | Pilot (scaffold) |
| Hybrid Clinical Analyzer | `backend/app/services/hybrid_clinical_analyzer.py` | 1,049 | `AnalysisType` (8 enum values), `StructuredContext`, `HybridAnalysisResult`, deterministic+LLM pipeline, grounded reasoning | Pilot (active) |

### Causal Reasoning Service Assessment

The service currently provides:
- **Chain discovery:** `find_causal_chains()` via Cypher traversal on Neo4j knowledge graph
- **Treatment pathway analysis:** `find_treatment_pathways()` filtering for TREATS/PREVENTS relations
- **Adverse event pathway analysis:** `find_adverse_event_pathways()` filtering for ADVERSE_EFFECT_OF/MAY_CAUSE/CAUSES relations
- **Disease progression analysis:** `analyze_progression()` filtering for LEADS_TO/COMPLICATION_OF/EXACERBATES relations
- **Counterfactual reasoning:** `counterfactual_analysis()` finding supporting/contradicting chains
- **Confidence decay:** `HOP_DECAY = 0.85` applied multiplicatively per hop in chain
- **Mock fallback:** When Neo4j is unavailable, `_mock_causal_chains()` returns example Diabetes -> Nephropathy -> ESRD chain

**Critical gaps for formal causal inference:**
- No confounder identification or adjustment
- No assumption declaration on causal claims
- Single-point confidence estimates (no intervals)
- Counterfactual reasoning operates without untestable assumption declaration
- `CausalRelationType.CAUSES` and `CausalRelationType.ASSOCIATED_WITH` both treated as chain-traversal relations without distinguishing causal strength of evidence
- `_build_chain_from_record()` applies hop decay but does not propagate uncertainty bounds

### Hybrid Clinical Analyzer Assessment

The analyzer currently provides:
- **Deterministic extraction:** Unified NLP Entity Service with SNOMED-CT normalization, negation detection, section awareness
- **LLM grounded reasoning:** Clinical reasoning constrained to extracted entities via system prompts ("reason ONLY over the provided structured data")
- **Analysis types:** 8 types via `AnalysisType` enum (clinical summary, risk assessment, medication review, differential diagnosis, treatment plan, lab interpretation, question answering, free-form)
- **Graph-augmented context:** Optional patient knowledge graph context via `graph_augmented_rag` (Step 1.5 in `analyze()`)
- **Graceful LLM fallback:** If LLM call fails, returns deterministic extraction with `[LLM analysis unavailable]` prefix

**Extension points for causal reasoning integration (identified):**
1. `StructuredContext.relationships` list (line 132) -- causal claims would extend this structure
2. `AnalysisType` enum (line 107) -- new `CAUSAL_ANALYSIS` type could be added
3. `SYSTEM_PROMPTS` dictionary (line 381) -- causal-specific system prompt with assumption declaration requirements
4. `analyze()` method, Step 1.5 (line 861) -- natural insertion point for causal chain context alongside graph RAG
5. `HybridAnalysisResult` dataclass (line 339) -- extend with causal metadata fields

## Implementation Constraints

### 1. Explicit Assumption Declaration Framework

#### CausalClaim Schema

Every formal causal claim must carry a complete assumption declaration. The proposed `CausalClaim` dataclass extends the existing `CausalLink` with mandatory fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `confounders_considered` | `list[str]` | Yes | Named confounders evaluated (e.g., age, sex, comorbidity count, medication history) |
| `temporal_ordering_evidence` | `list[TemporalFact]` | Yes | Each fact: `{fact_id, description, source_timestamp, target_timestamp, ordering_confidence}` |
| `intervention_assignment_mechanism` | `str` | Yes | How treatment/exposure was assigned (e.g., "physician decision (observational)", "randomized allocation (RCT)", "natural experiment") |
| `study_design_type` | `StudyDesignType` | Yes | RCT, observational_cohort, case_control, cross_sectional, ecological, case_report, expert_opinion, knowledge_base |
| `confidence_point` | `float` | Yes | Point estimate (0.0 - 1.0) |
| `confidence_lower` | `float` | Yes | Lower bound of 95% CI |
| `confidence_upper` | `float` | Yes | Upper bound of 95% CI |
| `confidence_method` | `str` | Yes | How CI was computed (e.g., "bootstrap", "analytical", "bayesian_posterior") |
| `evidence_sources` | `list[str]` | Yes | PMIDs, guideline IDs, KG paths |
| `causal_method_used` | `str` | Yes | Statistical method applied (e.g., "propensity_score_matching") |
| `claim_generated_at` | `datetime` | Yes | Timestamp of claim generation (UTC) |

The `CausalClaim` dataclass inherits all fields from `CausalLink` (source_cui, source_name, target_cui, target_name, relation_type, confidence, evidence_count, temporal_order, mechanism, sources) and adds the above fields. A `CausalLink` without assumption declaration fields populated is treated as a correlation observation, never as a causal claim.

#### StudyDesignType Enum

```
RCT                  -> Randomized controlled trial
OBSERVATIONAL_COHORT -> Prospective or retrospective cohort
CASE_CONTROL         -> Case-control study design
CROSS_SECTIONAL      -> Cross-sectional study
ECOLOGICAL           -> Population-level ecological study
CASE_REPORT          -> Individual case report or series
EXPERT_OPINION       -> Expert panel or guideline-based
KNOWLEDGE_BASE       -> Derived from curated knowledge base (UMLS, OMOP)
```

#### User-Facing Labeling Rules

| Condition | Label Displayed | Visual Treatment |
|-----------|----------------|------------------|
| `CausalClaim` with `study_design_type` = RCT and all 5 trust metrics met | "Causal relationship (supported by RCT evidence)" | Standard display with green evidence badge |
| `CausalClaim` with `study_design_type` in {OBSERVATIONAL_COHORT, CASE_CONTROL} and all 5 trust metrics met | "Causal hypothesis (not validated)" | Amber warning bar, assumption summary expandable |
| `CausalClaim` with any other study design and all 5 trust metrics met | "Causal hypothesis (not validated)" | Amber warning bar, assumption summary expandable |
| `CausalLink` without assumption declaration | "Correlation observed" | Grey informational display |
| `CausalRelationType.ASSOCIATED_WITH` | "Correlation observed" | Grey informational display |
| Any trust metric below threshold | "Correlation observed" (forced downgrade) | Grey informational display, causal features hidden |

**Display logic:** The frontend rendering component checks three conditions in order: (1) Are all 5 trust metrics currently above threshold? If no, force "Correlation observed" regardless of claim quality. (2) Is the output a `CausalClaim` with complete assumption declaration or a `CausalLink`? (3) What is the `study_design_type`? The most restrictive condition determines the label.

### 2. Uncertainty Propagation Design

#### Confidence Interval Propagation Through CausalChain

The existing `CausalChain` computes `total_confidence` as a single point estimate using multiplicative decay (`HOP_DECAY = 0.85`). This must be replaced with interval propagation:

**Propagation rule for chain of length N:**
- Each link `i` has confidence interval `[lower_i, upper_i]` with point estimate `point_i`
- Chain lower bound: `product(lower_i for i in 1..N) * HOP_DECAY^(N-1)`
- Chain upper bound: `product(upper_i for i in 1..N) * HOP_DECAY^(N-1)`
- Chain point estimate: `product(point_i for i in 1..N) * HOP_DECAY^(N-1)`

**No single-point causal estimates allowed in clinical outputs:**
- Every causal confidence in API responses must be expressed as `{point, lower, upper}`
- Every UI display must render confidence as a range (e.g., "65-80% confidence") not a single number
- Exported reports (PDF, FHIR, CDA) must include the full interval

**Interval width warnings:**

| Interval Width (upper - lower) | Warning Label | Clinical Guidance |
|-------------------------------|---------------|-------------------|
| < 0.2 | None | Standard display |
| 0.2 - 0.35 | "Moderate uncertainty" | Display amber indicator |
| 0.35 - 0.5 | "High uncertainty" | Display red indicator, add explanatory text |
| > 0.5 | "Insufficient evidence for clinical use" | Suppress from default view; available on explicit request only |

**Lower bound threshold:** If `confidence_lower < 0.3`, output must include: "Insufficient evidence for clinical use" regardless of point estimate.

#### Display: Confidence Bands

- Confidence bands rendered with width proportional to chain length
- 1-hop chain: narrow band (single link CI width)
- 2-hop chain: wider band (propagated CI, typically 1.5-2x single link width)
- 3+ hop chain: widest band with explicit "long chain -- increased uncertainty" label
- Visual encoding: color gradient from green (narrow CI, high confidence) through amber to red (wide CI, low confidence)
- Hover/click reveals per-link breakdown with individual confidence intervals

#### Monte Carlo Simulation for Complex Chains

For chains with >3 links or where links share confounders (non-independent confidence estimates):

1. Fit Beta distribution to each link's `[lower, upper]` interval
2. Sample each link's confidence from its Beta distribution
3. Run N=10,000 simulations of chain confidence (multiply sampled link confidences with hop decay)
4. Report: median, 2.5th percentile (lower), 97.5th percentile (upper) from simulation distribution
5. Detect multi-modal distributions (may indicate conditional causal relationships); flag for clinical review if bimodal
6. Computational budget: <100ms per chain; pre-compute for known high-frequency pathways and cache results

### 3. Causal Method Constraints

#### Methods Approved for Initial Activation

| Method | Appropriate When | Minimum Sample Size | Key Assumptions | Testable? |
|--------|-----------------|--------------------|-----------------|-----------|
| Propensity Score Matching | Observational data, binary treatment, measured confounders | N >= 200 per arm after matching | No unmeasured confounders, correct propensity model | Partially (balance diagnostics, standardized mean differences) |
| Instrumental Variables | Treatment assignment has natural instrument (e.g., physician preference, distance to facility) | N >= 500 | Instrument relevance, exclusion restriction, independence | Partially (first-stage F-statistic > 10, overidentification test) |
| Difference-in-Differences | Policy or treatment change with pre/post data, control group available | N >= 100 per group, >= 3 time points pre-treatment | Parallel trends in pre-treatment period | Yes (pre-trend test, event study plot) |
| Regression Discontinuity | Treatment assigned by threshold on continuous running variable | N >= 200 within optimal bandwidth of cutoff | Continuity at cutoff, no manipulation of running variable | Yes (McCrary density test, local polynomial estimation) |

#### Methods NOT Approved for Initial Activation

| Method | Reason for Deferral | Prerequisite for Future Activation |
|--------|--------------------|------------------------------------|
| do-Calculus | Requires complete and correct DAG specification; incorrect DAGs produce silently wrong causal estimates with no diagnostic signal | Validated DAG construction pipeline with clinical review board approval; DAG sensitivity analysis tooling; formal completeness checking |
| Counterfactual Reasoning | Requires untestable assumptions about potential outcomes (fundamental problem of causal inference); no empirical validation possible for individual-level counterfactuals | Formal sensitivity analysis framework (e.g., Manski bounds); clinical panel review for each counterfactual type; population-level validation |
| Mendelian Randomization | Requires genetic instrument validity; pleiotropic violations are common and hard to detect | Genomic data integration (not in current scope); validated instrument databases; MR-Egger and MR-PRESSO robustness checks |
| Synthetic Control Methods | Requires donor pool construction with strong pre-treatment fit; sensitive to donor selection | Multi-site deployment with sufficient historical data; donor selection transparency |

#### Minimum Sample Size Enforcement

The system must reject causal analysis requests when available sample size is below the method-specific minimum:
- Error response: `{"error": "insufficient_sample_size", "required": N, "available": M, "method": "...", "fallback": "correlation_only"}`
- Fallback: return correlation-only analysis with explanation of why causal analysis was not performed
- Logging: log every insufficient-sample rejection with method, required N, available N, and query context

### 4. Safety Guardrails for Causal Outputs

#### Mandatory Disclaimer

All causal outputs (API responses, UI displays, exported reports) must include:

```
DISCLAIMER: Causal inference outputs are generated by statistical methods
applied to observational clinical data. They represent hypotheses, not
established causal relationships. Clinical decisions should not be based
solely on these outputs. All causal claims include assumption declarations
that should be reviewed by qualified clinicians.
```

This disclaimer is:
- Appended to every API response containing causal claims (field: `causal_disclaimer`)
- Displayed in a persistent, non-dismissible banner on any UI page showing causal outputs
- Included in any exported report (PDF, FHIR, CDA) containing causal claims
- NOT suppressible by API consumers or UI configuration

#### Risk-Tier Based Visibility

| Risk Tier | Causal Output Behavior | Access Control |
|-----------|----------------------|----------------|
| Critical (drug safety, treatment decisions) | Hidden by default; requires explicit clinician request via "Show causal analysis" button | Clinician role required; request action logged to audit trail with timestamp and user ID |
| High (diagnosis reasoning, prognosis) | Collapsed by default; expandable with single click | Any clinical user; expansion event logged |
| Medium (lab interpretation, risk scoring) | Visible with amber "hypothesis" badge | Any authenticated user |
| Low (general clinical summary) | Visible with grey "correlation" badge | Any authenticated user |

#### Automatic Trust Metric Suppression

When any of the 5 trust metrics drops below its threshold:

1. **Immediate (within current request cycle):** All causal outputs in new requests are replaced with correlation-only equivalents
2. **Within 1 minute:** Active UI sessions receive WebSocket notification: "Causal analysis temporarily unavailable -- quality metrics below threshold"
3. **Logging:** Suppression event logged with: timestamp, which metric(s) failed, threshold values, actual values, number of active sessions affected
4. **Recovery:** Causal outputs restored only after metric returns above threshold for at least 1 hour (hysteresis to prevent flapping on metrics near threshold boundaries)
5. **No manual override:** Trust metric suppression cannot be bypassed by any user role, including admin

#### Clinical Review Requirement for Medication/Treatment Domains

Causal claims involving `CausalRelationType.TREATS`, `PREVENTS`, `ADVERSE_EFFECT_OF`, or `CONTRAINDICATED_BY` require:

1. Automatic flag for clinical pharmacist review before display to end users
2. 24-hour review SLA (claim held in `pending_review` state; not visible to clinical users until reviewed)
3. Reviewer must confirm: (a) assumption declaration is complete, (b) confounders are appropriate for the clinical context, (c) no known contradicting evidence from guidelines
4. Approved claims receive "clinician-reviewed" badge with reviewer identity and timestamp
5. Rejected claims are suppressed with reason logged; rejection triggers review of similar claims

### 5. Integration with Hybrid Clinical Analyzer

#### Extension Points

| Extension Point | Location in `hybrid_clinical_analyzer.py` | Integration Design |
|----------------|-------------------------------------------|-------------------|
| Analysis type enum | `AnalysisType` (line 107) | Add `CAUSAL_ANALYSIS = "causal_analysis"` value |
| System prompts | `SYSTEM_PROMPTS` dict (line 381) | Add causal-specific prompt requiring assumption citation for every causal claim; LLM must reference declared confounders |
| Structured context | `StructuredContext` class (line 120) | Add `causal_claims: list[CausalClaim] = field(default_factory=list)` field |
| Graph context injection | `analyze()` method, Step 1.5 (line 861) | Inject causal chain context from `causal_reasoning_service.py` alongside graph RAG context; causal chains become additional LLM input |
| Result metadata | `HybridAnalysisResult` (line 339) | Add `causal_claims_count: int = 0`, `causal_suppressed: bool = False`, `trust_metric_status: dict = field(default_factory=dict)` |
| Prompt context rendering | `StructuredContext.to_prompt_context()` (line 140) | Add CAUSAL CLAIMS section rendering assumption declarations in structured format for LLM consumption |

#### Fallback Behavior

The integration must degrade gracefully in all failure modes:

| Failure Mode | Behavior | Output Metadata |
|-------------|----------|-----------------|
| Trust metrics below threshold | `causal_claims` field returns empty list; all outputs use correlation-only language | `causal_suppressed: true`, `trust_metric_status: {metric: value}` |
| Neo4j unavailable | Causal chain discovery returns empty; hybrid analyzer proceeds with deterministic extraction + LLM only | `causal_attempted: false`, `causal_unavailable_reason: "graph_db_unreachable"` |
| Causal method fails (insufficient data) | Return correlation-only result | `causal_attempted: true`, `causal_failed_reason: "insufficient_sample_size"` |
| Causal method fails (convergence error) | Return correlation-only result | `causal_attempted: true`, `causal_failed_reason: "convergence_error"` |
| LLM unavailable | Deterministic extraction proceeds; causal claims from chain analysis still available but without LLM explanations | `llm_available: false`, raw causal claims in structured fields |

#### No Causal Features in Degraded Mode

When the system is in any degraded mode (trust metric suppression, Neo4j unavailable, method failure):
- `CausalRelationType.CAUSES`, `MAY_CAUSE`, `LEADS_TO` are remapped to `ASSOCIATED_WITH` in all outputs
- The `CausalClaim` dataclass is not used; outputs use `CausalLink` without assumption declaration
- Frontend renders only "Correlation observed" labels
- API responses include `"causal_mode": "disabled"` in metadata
- No causal-specific system prompt is sent to LLM; standard analysis prompts apply

## Blinded Safety Comparison Plan

### Study Design

| Parameter | Value |
|-----------|-------|
| Study type | Prospective blinded non-inferiority comparison |
| Case count | Minimum 50 cases (target 75 for statistical power) |
| Arms | Arm A: correlation-only output (current `hybrid_clinical_analyzer.py`); Arm B: causal inference output (analyzer + `causal_reasoning_service.py`) |
| Randomization | Cases randomly assigned to Arm A or B presentation order; each case evaluated by all 3 clinicians in both arms |
| Clinician panel | 3 independent board-certified clinicians, no involvement in system development |

### Case Selection

- Stratified sampling across: specialty (internal medicine, cardiology, oncology, neurology), acuity (acute, subacute, chronic), complexity (single-problem, multi-morbidity, polypharmacy)
- Minimum 10 cases per acuity stratum
- At least 20 cases (40%) involving high-risk clinical decisions (medication changes, procedure recommendations, critical diagnoses)
- Cases selected from de-identified production data or synthetic cases reviewed and approved by clinical panel
- Exclusions: duplicate patients, cases used in model training, cases with fewer than 3 clinical facts in KG

### Blinding Protocol

1. Clinicians receive case presentation + system output (either correlation-only or causal-enhanced)
2. Output format is standardized: both arms use identical visual layout, fonts, section structure; only content differs
3. Clinicians do NOT know which arm they are evaluating; arm labels are coded as "Output Version 1" / "Output Version 2" with random assignment per case
4. Case assignment is double-blinded: the evaluator preparing case packets does not know which output version maps to which arm
5. Unblinding occurs only after all evaluations are complete, locked, and exported

### Safety Outcome Measures

| Measure | Definition | Assessment Method |
|---------|-----------|-------------------|
| Primary: Harmful decision change | Would the clinician change a treatment decision based on this output, AND would that change be potentially harmful? | Structured rubric: 5-point scale from "definitely harmful" (1) to "definitely beneficial" (5) |
| Secondary: Appropriate decision support | Does the output provide useful clinical decision support? | 5-point Likert scale |
| Secondary: Information completeness | Does the output provide sufficient information for the clinical question? | 5-point Likert scale |
| Secondary: Reasoning transparency | Are the assumptions and limitations clearly communicated? | 5-point Likert scale |
| Safety signal: Any harmful rating | Binary: did ANY clinician rate ANY case as "definitely harmful" (score = 1) or "potentially harmful" (score = 2)? | If >= 2 clinicians rate same case as harmful, immediate safety review halt |

### Pass Criterion

- **Primary:** Causal outputs (Arm B) must not produce a statistically significantly higher rate of harmful decision changes (scores 1-2) compared to correlation-only outputs (Arm A)
- **Statistical test:** Fisher's exact test, one-sided, alpha = 0.05
- **Non-inferiority margin:** Arm B harmful rate must be <= Arm A harmful rate + 5 percentage points
- **Hard stop:** If any case receives "definitely harmful" (score = 1) from >= 2 clinicians, the study is halted for safety review by Medical Director before resuming

### Statistical Power Calculation Approach

- Expected harmful decision rate in Arm A (correlation-only): 2-5% based on published CDS safety literature
- Detectable difference: 10 percentage points (detect if Arm B harmful rate exceeds 12-15%)
- With N=50 cases, 3 raters, alpha=0.05: power >= 0.80 for detecting 10pp difference
- With N=75 cases, 3 raters, alpha=0.05: power >= 0.90 for detecting 10pp difference
- Inter-rater reliability analysis: Fleiss' kappa target >= 0.6 (substantial agreement)

## Trust Metric Monitoring Dashboard Design

### Dashboard Layout

Five metric panels arranged horizontally, each with:
1. **Metric name** and threshold value
2. **Current value** (large font, bold)
3. **Traffic light indicator:** Green (above threshold by >10%), Amber (within 10% of threshold), Red (below threshold)
4. **30-day rolling trend** sparkline
5. **Days since last threshold crossing** counter

### Metric Panels

| Panel | Metric | Threshold | Data Source | Refresh Interval |
|-------|--------|-----------|-------------|------------------|
| 1 | Extraction precision on P1-010 corpus | >85% | NLP evaluation pipeline (daily batch against acceptance corpus) | Daily |
| 2 | Confidence calibration error (Brier score) | <10% | P3-005 calibration service | Daily |
| 3 | False positive rate (confidence >0.9) | <5% | Confidence threshold analysis on clinician-validated sample | Daily |
| 4 | KG completeness score (per patient avg) | >70% | P2-006 KG scoring model | Daily |
| 5 | Zero SEV-1 AI incidents (consecutive days) | 90 days | Incident management system (real-time event stream) | Real-time |

### Global Status Indicator

- **All 5 green for >= 7 consecutive days:** "CAUSAL INFERENCE: ELIGIBLE FOR ACTIVATION" (green banner)
- **All 5 green but < 7 consecutive days:** "CAUSAL INFERENCE: APPROACHING ELIGIBILITY" (blue banner)
- **Any amber:** "CAUSAL INFERENCE: THRESHOLD WARNING -- MONITOR" (amber banner)
- **Any red:** "CAUSAL INFERENCE: BLOCKED -- [metric name(s)] BELOW THRESHOLD" (red banner)

### Alert Configuration

| Condition | Alert Type | Recipients |
|-----------|-----------|------------|
| Any metric crosses from green to amber | Slack notification | Clinical AI team channel |
| Any metric crosses from green/amber to red | PagerDuty alert (P3 severity) | Clinical AI Lead, CTO |
| SEV-1 AI incident reported | Immediate: reset SEV-1 counter to 0; PagerDuty P1 | Clinical AI Lead, CTO, Medical Director |
| All 5 metrics simultaneously green for 7 consecutive days | Slack notification + calendar invite for activation readiness review | Clinical AI Lead, CTO |

## Activation Criteria Checklist

### Trust Metric Gates (ALL required simultaneously)

- [ ] Extraction precision >85% on P1-010 corpus (30-day rolling average)
- [ ] Confidence calibration error <10% Brier score (30-day rolling average)
- [ ] False positive rate <5% for confidence >0.9 (30-day rolling average)
- [ ] KG completeness score >70% per patient average (30-day rolling average)
- [ ] Zero SEV-1 AI incidents for 90 consecutive days

### Implementation Gates (ALL required)

- [ ] `CausalClaim` dataclass implemented with all required fields (Section 1)
- [ ] Uncertainty propagation implemented with interval arithmetic and Monte Carlo (Section 2)
- [ ] Minimum sample size enforcement operational for all approved methods (Section 3)
- [ ] Mandatory disclaimer rendering in API, UI, and export paths (Section 4)
- [ ] Risk-tier based visibility controls deployed and tested (Section 4)
- [ ] Automatic trust metric suppression tested end-to-end (Section 4)
- [ ] Clinical review workflow for medication/treatment causal claims operational (Section 4)
- [ ] Frontend labeling logic implemented (causal hypothesis vs correlation) (Section 1)
- [ ] Hybrid analyzer extension points integrated and tested (Section 5)
- [ ] Graceful degradation tested for all failure modes (Section 5)
- [ ] Trust metric monitoring dashboard deployed and operational
- [ ] Blinded safety comparison study protocol approved by clinical review board
- [ ] Blinded safety comparison study completed with pass criterion met
- [ ] P4-013 (SaMD) risk classification reviewed for causal inference features
- [ ] Clinical AI Lead and CTO joint approval for production activation

## Cross-Dependencies

| Dependency | Ticket | Impact on P4-010 | Status |
|-----------|--------|-------------------|--------|
| Confidence calibration | P3-005 | Calibration plots provide Brier score baseline for trust metric #2 | Closed |
| KG completeness scoring | P2-006 | Scoring model provides trust metric #4 | Closed |
| NLP extraction acceptance corpus | P1-010 | Corpus provides trust metric #1 evaluation data | Closed |
| Differential diagnosis labeling | P1-015 | Confirmed all outputs labeled as ranking, not causal | Closed |
| SaMD classification | P4-013 | May classify causal features as higher-risk medical device; affects regulatory requirements and approval gates | Monitoring thresholds |
| Canary testing infrastructure | P2-003 | Required for staged rollout of causal features when activated | Closed |
| SLO dashboard | P2-017 | Latency monitoring for causal chain computation overhead | Closed |
| Incident management taxonomy | P1-028 | SEV-1 incident tracking and classification for trust metric #5 | Closed |
| Guideline RAG corpus | P4-009 | Richer guideline coverage improves causal reasoning quality; not blocking | Monitoring |
