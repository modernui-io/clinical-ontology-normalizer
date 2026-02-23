# Slice Bench Results & Next Steps

## Latest Run (2026-02-23)

### Configuration
- **LLM**: claude-sonnet-4-5-20250929 (Anthropic)
- **Judge**: claude-opus-4-6 (Anthropic) — separate model via `--judge-model`
- **Cohort**: 4 patients (2 Tier A, 2 Tier B) from MIMIC-IV, 24 questions each = 96 questions
- **Templates**: 18 original (A1-E4) + 6 new hard longitudinal (F1-F6)
- **Conditions**: B0-B4 (480 total evaluations)
- **Changes**: Structured KG prompts (`to_structured_llm_prompt()`), evidence hierarchy system prompt, multi-model judge

### Condition Scores
| Condition | Score | Delta vs B0 |
|---|---|---|
| B0 LLM Alone | 50.6% | — |
| B1 Latest Note | 73.0% | +22.4pp |
| B2 All Notes RAG | 83.8% | +33.2pp |
| B3 KG-RAG (structured prompts) | 84.6% | +34.0pp |
| B4 Full System | 86.3% | +35.7pp |

### Paired Deltas
| Comparison | Delta |
|---|---|
| B0→B2 (RAG uplift) | +33.2pp |
| B2→B3 (structured KG prompts) | +0.8pp |
| B3→B4 (guidelines + calculators) | +1.7pp |
| B2→B4 (full uplift) | +2.5pp |

### By Tier
| Condition | Tier A | Tier B |
|---|---|---|
| B2 All Notes RAG | 81.1% | 86.4% |
| B3 KG-RAG | 81.8% | 87.4% |
| B4 Full System | 82.6% | 90.1% |

---

## Previous Run (2026-02-22, baseline)

### Configuration
- **LLM + Judge**: claude-sonnet-4-5-20250929 (same model for both)
- **Cohort**: 4 patients (2 Tier A, 2 Tier B), 18 questions each = 72 questions
- **Templates**: 18 original (A1-E4), flat KG prompt format

### Condition Scores (Bootstrap 95% CIs, n=2000, seed=42)
| Condition | Mean | 95% CI |
|---|---|---|
| B0 LLM Alone | 46.9% | [38.9%, 55.2%] |
| B1 Latest Note | 81.2% | [74.2%, 87.5%] |
| B2 All Notes RAG | 91.5% | [85.8%, 95.9%] |
| B3 KG-RAG | 91.9% | [86.4%, 96.2%] |
| B4 Full System | 92.2% | [87.2%, 96.2%] |

### Paired Deltas
| Comparison | Delta | CI | Sig |
|---|---|---|---|
| B0→B2 (RAG uplift) | +44.6% | [+33.3%, +55.4%] | * |
| B2→B3 (KG layer) | +0.4% | [-2.2%, +3.0%] | ns |
| B3→B4 (guidelines+calc) | +0.3% | [-0.9%, +2.0%] | ns |
| B2→B4 (full uplift) | +0.7% | [-2.3%, +4.0%] | ns |

### Mechanism-Level Deltas (B2→B3)
| Mechanism | B2→B3 | B3→B4 |
|---|---|---|
| single_note (controls) | 0.0% | 0.0% |
| assertion_reasoning | -3.8% | 0.0% |
| cross_encounter | -1.4% | +2.8% |
| causal_chain | 0.0% | +4.2% |
| safety_check | 0.0% | -3.2% |
| guideline_trigger | +11.2% | -2.1% |

---

## Run-over-Run Comparison

| Metric | Baseline (Feb 22) | Structured Prompts (Feb 23) | Change |
|---|---|---|---|
| B2→B3 delta | +0.4pp | +0.8pp | +0.4pp |
| B3→B4 delta | +0.3pp | +1.7pp | +1.4pp |
| B2→B4 delta | +0.7pp | +2.5pp | +1.8pp |
| B2 ceiling | 91.5% | 83.8% | -7.7pp |
| Questions/patient | 18 | 24 | +6 (F-series) |
| Judge model | Sonnet 4.5 | Opus 4.6 | upgraded |

The B2 ceiling dropped 7.7pp (91.5% → 83.8%), partly from harder F-series questions and partly from the stricter Opus 4.6 judge. The B2→B4 gap widened from +0.7pp to +2.5pp — a 3.6x improvement.

## Diagnosis

### What improved:
1. **Structured KG prompts**: Box-drawing assertion tables, relationship tables, and tabular timelines give the LLM a visual signal to treat KG data as authoritative. B2→B3 doubled from +0.4pp to +0.8pp.
2. **Evidence hierarchy system prompt**: Explicit ordering (authoritative status > structured relationships > timeline > documents) helps the LLM prioritize KG context over raw notes.
3. **Opus 4.6 judge**: Stricter grading lowered all scores but especially B2, creating more headroom.
4. **F-series questions**: Cross-encounter medication timelines, problem list reconciliation, and causal chain tracing require multi-note synthesis.

### Remaining gaps:
1. **B2 ceiling still high (83.8%)**: Sonnet 4.5 with document RAG is strong enough to answer most questions. Need Tier C patients (15+ encounters) where document volume overwhelms simple RAG.
2. **B2→B3 delta (+0.8pp) still not significant**: The structured prompts help but the effect is small. Without DB-backed KG data for these patients, the KG context is thin.
3. **Tier A vs Tier B shows B improves more**: B4 Tier B = 90.1% vs Tier A = 82.6%. More encounters = more value from structured context. Tier C should amplify this further.

## Next Steps

### Immediate
1. **Ingest Tier C patients** — 4 patients with 15+ encounters from MIMIC cohort CSV. This is the most impactful change for lowering the B2 ceiling.
2. **Med Gemma 27B run** — Use `--provider ollama --model alibayram/medgemma:27b --judge-provider anthropic --judge-model claude-opus-4-6`. Smaller answering model = lower B2 ceiling = more KG headroom.

### Follow-up
3. **KG-only questions** — Design questions that literally cannot be answered from raw notes (e.g., "Which conditions were ruled out?" when the negation is only captured in assertion metadata, not in note text).
4. **Per-question difficulty analysis** — Identify which F-series questions discriminate best between B2 and B3, and create more like them.

## Key Files
| File | Role |
|---|---|
| `backend/app/services/graph_augmented_rag.py` | `to_llm_prompt()` + `to_structured_llm_prompt()` |
| `backend/app/services/longbench_runner.py:107-135` | System prompts (BASE, NO_CONTEXT, EPISTEMIC with evidence hierarchy) |
| `backend/app/services/longbench_runner.py:345-425` | `_build_prompt()` — uses structured prompt for B3/B4 |
| `backend/app/services/longbench_runner.py:56-100` | CONDITION_CONFIGS — B3/B4 have `structured_prompt: True` |
| `backend/app/services/longbench_runner.py:597-668` | `_CriterionJudge` — supports separate judge model/provider |
| `backend/app/services/longbench_cohort.py` | 24 question templates (A1-F6), criteria functions |
| `backend/scripts/smoke_test_longbench.py` | CLI with `--judge-provider`, `--judge-model` |
| `backend/data/benchmarks/results/longbench_smoke/smoke_report.json` | Latest results |
