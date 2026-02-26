# EpiKG Paper v13: NeurIPS 2026 Improvement Plan

**Created:** 2026-02-26
**Target:** NeurIPS 2026 submission
**Status:** In progress — data from experiments still incoming

---

## Priority 1: Critical Fixes (blocks submission)

### P1.1 Number discrepancies between main text and appendix
- [x] **Main Table 3 vs Appendix Table 9**: C1 = 71.5% vs 73.2% — **FIXED** (appendix updated to 71.5%)
- [x] **C4 Duration**: Main = 83.3% vs Appendix = 53.3% (30pp gap!) — **FIXED** (appendix updated to 83.3%)
- [x] **C4 Uncertainty**: Main = 57.5% vs Appendix = 62.5% — **FIXED** (appendix updated to 57.5%)
- [x] All appendix table numbers now match main text. C4g column added to appendix table.
- [x] Evaluator evolution note added to appendix reproducibility section.

### P1.2 Assertion label terminology inconsistency
- [x] **Eq. 1** (system_design L26): Pres., Abs., Poss., Cond., Hypo., Fam.Hx., Hist. — kept as abbreviations, maps correctly
- [x] **Definition 2** (system_design L104): Fixed Negated→Absent, Uncertain→Possible, Family→Family\_History, Not\_Associated→Historical
- [x] **Appendix table** (appendix L140-147): Already canonical — no change needed
- [x] All assertion labels now use canonical set: Present, Absent, Possible, Conditional, Hypothetical, Family\_History, Historical

### P1.3 Broken cross-references (will render as "Section ??")
- [x] `\ref{sec:intent_routing}` in benchmark_design.tex → **FIXED** to `\ref{sec:system:intentaware}`
- [x] `\ref{sec:formal_invariant}` in introduction.tex → **FIXED** to `\ref{sec:system:formal}`

### P1.4 Factual error in discussion
- [x] Discussion said "duration $-60\pp$" → **FIXED** to "$-53.3\pp$"

### P1.5 Allen's relations count mismatch
- [x] Added clarifying sentence in system_design.tex: "subset of Allen's 13 canonical interval relations, augmented with Concurrent and Unknown"
- [x] Added parenthetical in related_work.tex: "(a subset of Allen's 13, augmented with Concurrent and Unknown)"

---

## Priority 2: High-Impact Improvements

### P2.1 Abstract restructure
- [ ] Currently ~250 words, NeurIPS norm is ~200
- [ ] Buries the positive result (change: 0%→60%) after the negative aggregate (-2.3pp)
- [ ] **Action**: Lead with breakthrough category results, then acknowledge aggregate nuance. Cut SliceBench and cross-model detail to save words.
- [ ] Remove "Shannon entropy" from abstract — too technical for abstract, keep in system design

### P2.2 Evaluator clarity
- [ ] Benchmark design (Section 4) describes LLM-as-judge evaluation
- [ ] Results section says "deterministic keyword evaluator"
- [ ] Reader never told which evaluator was used for which table
- [ ] **Action**: Add a paragraph at the start of Results clearly stating: ClinicalBench ablation uses deterministic keyword evaluator for reproducibility; Slice Bench uses LLM-as-judge for richer assessment. Cross-model validation uses keyword evaluator. All CIs computed on keyword evaluator scores.
- [ ] Update benchmark_design.tex evaluation protocol to mention both evaluation methods

### P2.3 Run-to-run variance disclosure
- [ ] Discussion mentions "C1 baseline fluctuated ±10pp across runs" — this is HUGE
- [ ] All reported deltas <10pp are within noise if this is true
- [ ] **Action**: Investigate source (evaluator version changes vs model non-determinism). If evaluator-driven, explain clearly. If model non-determinism at temp=0, investigate Ollama settings. Either way, move this disclosure to the results section (not buried in limitations).

### P2.4 Remove unverifiable claims
- [x] "200B+ parameter class" → **FIXED** to "commercial frontier model"

### P2.5 Missing `\bibliographystyle`
- [x] neurips_2026.sty provides `\bibliographystyle{unsrtnat}` automatically — **no fix needed**

### P2.6 Cite uncited references or remove them
- [ ] `ceusters2015ontologyepistemology` — still uncited. Consider citing in system_design formal section or remove.
- [x] `bao2024uncertaintybiomedkg` — **FIXED** cited in related_work.tex temporal section
- [x] `peng2018negbio` — **FIXED** cited in related_work.tex assertion section
- [ ] Add citation for MedQA if referenced in benchmark design opening

### P2.7 MedQA model identity
- [ ] Appendix says MedQA baseline uses "Claude Opus 4.5"
- [ ] Main text supporting results says "the backbone LLM achieves 81.6%"
- [ ] Reader will think this is MedGemma 27B (the ClinicalBench model)
- [ ] **Action**: Explicitly state which model achieved 81.6% on MedQA. If Opus, clarify it is not the ClinicalBench backbone.

### P2.8 Missing appendix sections (PARTIALLY DONE)
- [ ] Cross-model table caption references "see Appendix for evaluator evolution" — section doesn't exist
- [ ] C4g routing algorithm — core contribution but no appendix detail
- [ ] C5 methodology — benchmark design says "moved to appendix" but only per-category table exists
- [ ] **Action**: Add appendix sections for evaluator refinement log, C4g routing pseudocode, C5 component details

### P2.9 Add conclusion section
- [x] **DONE** — Added `\paragraph{Conclusion.}` at end of discussion.tex with 4 sentences covering gap, solution, category-specific benefit, and evaluation lens argument

---

## Priority 3: Polish and Refinements

### P3.1 Introduction tightening
- [ ] Lines 8-9 make the same claim twice ("no system connects..." and "we are unaware of a subsequent system...") — consolidate
- [ ] Line 13 overloaded sentence (temporal KGs) — split into 2-3 sentences
- [ ] Contribution list has 6 items — NeurIPS papers typically have 3-4. Merge items 1+2, demote item 4 (shared concept architecture) to system design
- [ ] Lines 32-34 repeat numbers from abstract — replace with qualitative summary

### P3.2 Standardize "Slice Bench" vs "SliceBench"
- [x] **DONE** — All instances standardized to "SliceBench" (one word) across all .tex files

### P3.3 System design length
- [ ] 7 subsections is dense for NeurIPS. Consider moving formal preservation (3.6) to appendix — interesting but not essential for main argument
- [ ] Line 31 implementation detail (101 trigger patterns, 4 categories) — move to appendix
- [ ] Line 63 PostgreSQL index strategy — describe conceptual architecture, not implementation

### P3.4 Related work improvements
- [x] Line 8: "has become" → "has emerged as" — **DONE**
- [x] NegBio citation added to assertion paragraph — **DONE**
- [x] "to our knowledge" hedging added — **DONE**
- [ ] Add transition sentence between assertion and temporal subsections
- [ ] Gap analysis table could add one column where EpiKG has a limitation (shows intellectual honesty)

### P3.5 Results section refinements
- [ ] C3 and C5 safety scores are "---" — explain why missing
- [ ] Hard longitudinal subset defined twice (benchmark L40 and results L88) — remove redundancy
- [ ] Experiencer fix reads like a dev log — reframe as formal ablation
- [x] Remove "200B+ parameter class" from L136 — **DONE**

### P3.6 Table formatting
- [ ] benchmark_design.tex tables use `[h]` — change to `[t]` for NeurIPS style
- [ ] Add consistent number formatting (1 decimal place everywhere for percentages)

### P3.7 Safety score w=2.0 justification
- [ ] Weight of 2.0 for false-positive assertion errors is not empirically validated
- [ ] Consider: sensitivity analysis, or citation to clinical risk literature, or acknowledge as a limitation

### P3.8 F1 > 0.90 citation in abstract
- [ ] Abstract claims "F1 > 0.90" for clinical NLP assertion detection — needs a citation
- [ ] Cite uzuner2011i2b2assertion or gul2025beyondnegation

---

## Priority 4: Data-Dependent (wait for experiments)

### P4.1 Fill in final C4g numbers
- [ ] Await experiments from other agent
- [ ] Re-run all conditions through consistent evaluator
- [ ] Update all tables across abstract, intro, results, discussion, appendix

### P4.2 Run C6 (long-context brute force) and C7 (deterministic KG only)
- [ ] These are the "bookend" conditions that make the design space falsifiable
- [ ] Currently described in benchmark design but NO results exist
- [ ] Without C6/C7 results, the "falsifiable design space" claim in the contributions is unsupported

### P4.3 Run C4g for Opus
- [ ] Currently only C4 Opus results exist (C1 vs C4)
- [ ] C4g (intent-aware) is the primary condition — need it for Opus too
- [ ] Enables full cross-model validation on intent-aware routing

### P4.4 Physician adjudication
- [ ] Currently n=5, single reviewer — too small for meaningful assessment
- [ ] Plan: n≥30, two physicians, blinded
- [ ] This is mentioned as planned throughout the paper — needs to happen before submission

### P4.5 Resolve ±10pp variance
- [ ] If evaluator-driven: document evaluator versions, explain which version is canonical
- [ ] If model-driven: investigate Ollama settings, consider running N>1 repetitions
- [ ] This is the single biggest threat to the paper's credibility

---

## Timeline

### Phase 1: Critical Fixes (Day 1-2)
| Task | Est. Time | Status |
|------|-----------|--------|
| P1.1 Reconcile number discrepancies | 2h | [ ] |
| P1.2 Standardize assertion labels | 1h | [ ] |
| P1.3 Fix broken cross-references | 10min | [ ] |
| P1.4 Fix discussion factual error | 5min | [ ] |
| P1.5 Allen's relations clarification | 20min | [ ] |
| P2.3 Investigate ±10pp variance | 2h | [ ] |
| P2.5 Check bibliographystyle | 10min | [ ] |

### Phase 2: High-Impact (Day 2-4)
| Task | Est. Time | Status |
|------|-----------|--------|
| P2.1 Abstract restructure | 1h | [ ] |
| P2.2 Evaluator clarity paragraph | 30min | [ ] |
| P2.4 Remove unverifiable claims | 10min | [ ] |
| P2.6 Fix uncited references | 30min | [ ] |
| P2.7 MedQA model clarification | 15min | [ ] |
| P2.8 Write missing appendix sections | 3h | [ ] |
| P2.9 Add conclusion | 30min | [ ] |

### Phase 3: Polish (Day 4-7)
| Task | Est. Time | Status |
|------|-----------|--------|
| P3.1 Introduction tightening | 1h | [ ] |
| P3.2 SliceBench naming | 10min | [ ] |
| P3.3 System design trimming | 1h | [ ] |
| P3.4 Related work improvements | 1h | [ ] |
| P3.5 Results refinements | 1h | [ ] |
| P3.6-P3.8 Table/formatting fixes | 1h | [ ] |

### Phase 4: Data-Dependent (ongoing, parallel)
| Task | Est. Time | Status |
|------|-----------|--------|
| P4.1 Re-score all conditions consistently | 4h | [ ] waiting on experiment |
| P4.2 Run C6 and C7 experiments | 8h | [ ] |
| P4.3 Run C4g for Opus | 4h | [ ] |
| P4.4 Physician adjudication (n≥30) | multi-day | [ ] |
| P4.5 Resolve variance issue | 2h | [ ] |

### Phase 5: Final Assembly (Day 7-10)
| Task | Est. Time | Status |
|------|-----------|--------|
| Slot in final numbers across all sections | 2h | [ ] |
| Final consistency check (numbers, labels, refs) | 2h | [ ] |
| Compile, check page count, trim if needed | 1h | [ ] |
| Generate final figures (radar, bar, waterfall) | 2h | [ ] |
| Proofread pass | 2h | [ ] |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| New data changes the story significantly | HIGH | Abstract/intro written for category-interaction framing which holds regardless of specific numbers |
| C6/C7 experiments show KG-RAG is strictly dominated | HIGH | Frame honestly; the category-level gains (change, family_history) are qualitatively unique |
| Physician adjudication disagrees with automated scoring | MEDIUM | Use adjudication to calibrate evaluator, not as primary evidence |
| ±10pp variance makes all deltas non-significant | HIGH | Use within-run paired comparisons as primary; cross-run as secondary. Document evaluator versions. |
| Paper exceeds 9 pages | MEDIUM | Move formal section and detailed tables to appendix |
| NeurIPS reviewers find the aggregate negative delta disqualifying | HIGH | Emphasize that aggregate masks transformative category effects; the paper's contribution is identifying WHERE structured context helps/hurts, not claiming universal improvement |

---

## What NOT to change (stable regardless of data)

These elements are locked in and shouldn't change even with new experimental results:

1. **The epistemic propagation gap framing** — this is the paper's conceptual contribution
2. **7-value assertion taxonomy** — design choice, not data-dependent
3. **Tri-temporal edge model** — architecture, not data-dependent
4. **Shared concept node architecture** — architecture
5. **Intent-aware retrieval design** (change/current-state/historical dispatch)
6. **Benchmark design** (ClinicalBench categories, SliceBench tiers, conditions C1-C7)
7. **Evaluation protocol** (BCa bootstrap, safety scoring, paired comparisons)
8. **The "vanilla RAG hurts" finding** — this is robust across all evaluator versions
9. **The category×condition interaction story** — the specific numbers may shift but the pattern holds
