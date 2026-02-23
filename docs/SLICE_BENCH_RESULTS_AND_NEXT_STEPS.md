# Slice Bench Results & Next Steps

## Latest Run: Med Gemma 27B (2026-02-23)

### Configuration
- **LLM**: alibayram/medgemma:27b (Ollama, local)
- **Judge**: claude-opus-4-6 (Anthropic)
- **Cohort**: 6 patients (2 Tier A, 2 Tier B, 2 Tier C) from MIMIC-IV, 24 questions each = 144 questions
- **Templates**: 18 original (A1-E4) + 6 new hard longitudinal (F1-F6)
- **Conditions**: B0-B4 (720 total evaluations)
- **Runtime**: ~9 hours (local inference)

### Condition Scores (Bootstrap 95% CIs, n=2000, seed=42)
| Condition | Score | 95% CI | Delta vs B0 |
|---|---|---|---|
| B0 LLM Alone | 19.4% | [16.9%, 22.1%] | — |
| B1 Latest Note | 56.2% | [50.6%, 61.8%] | +36.8pp |
| B2 All Notes RAG | 77.1% | [72.2%, 81.9%] | +57.6pp |
| B3 KG-RAG (structured prompts) | 80.6% | [76.5%, 84.6%] | +61.2pp |
| B4 Full System | 80.5% | [76.2%, 84.9%] | +61.1pp |

### Paired Deltas
| Comparison | Delta | CI | Sig |
|---|---|---|---|
| B0→B2 (RAG uplift) | +57.6pp | [+52.6, +62.4] | * |
| B2→B3 (KG layer) | +3.5pp | [-0.3, +7.6] | ns |
| B3→B4 (guidelines+calc) | -0.1pp | [-3.7, +3.3] | ns |
| **B2→B4 (full uplift)** | **+3.5pp** | **[+0.7, +6.6]** | **\*** |

### By Tier
| Condition | Tier A | Tier B | Tier C |
|---|---|---|---|
| B0 LLM Alone | 19.7% | 19.1% | 19.4% |
| B1 Latest Note | 50.1% | 57.7% | 60.6% |
| B2 All Notes RAG | 73.0% | 81.6% | 76.6% |
| B3 KG-RAG | 78.7% | 82.9% | 80.1% |
| B4 Full System | 78.1% | 79.9% | 83.5% |

### B2→B3 and B2→B4 Delta by Tier
| Tier | Encounters | B2→B3 Delta | B2→B4 Delta |
|---|---|---|---|
| A | 1-2 notes | +5.7pp | +5.1pp |
| B | 5-10 notes | +1.3pp | -1.7pp |
| **C** | **15+ notes** | **+3.5pp** | **+6.9pp** |

---

## Sonnet 4.5 Run (2026-02-23, Tier C)

### Configuration
- **LLM**: claude-sonnet-4-5-20250929 (Anthropic)
- **Judge**: claude-opus-4-6 (Anthropic) — separate model via `--judge-model`
- **Cohort**: 6 patients (2 Tier A, 2 Tier B, 2 Tier C) from MIMIC-IV, 24 questions each = 144 questions
- **Templates**: 18 original (A1-E4) + 6 new hard longitudinal (F1-F6)
- **Conditions**: B0-B4 (720 total evaluations)

### Condition Scores (Bootstrap 95% CIs, n=2000, seed=42)
| Condition | Score | 95% CI | Delta vs B0 |
|---|---|---|---|
| B0 LLM Alone | 49.9% | [43.6%, 56.1%] | — |
| B1 Latest Note | 73.4% | [67.8%, 78.7%] | +23.5pp |
| B2 All Notes RAG | 84.7% | [80.2%, 88.8%] | +34.8pp |
| B3 KG-RAG (structured prompts) | 86.9% | [82.8%, 90.8%] | +37.0pp |
| B4 Full System | 87.6% | [83.7%, 91.2%] | +37.8pp |

### Paired Deltas
| Comparison | Delta | CI | Sig |
|---|---|---|---|
| B0→B2 (RAG uplift) | +34.8pp | [+26.8, +42.4] | * |
| B2→B3 (KG layer) | +2.2pp | [-1.5, +5.9] | ns |
| B3→B4 (guidelines+calc) | +0.8pp | [-2.5, +4.2] | ns |
| B2→B4 (full uplift) | +3.0pp | [-0.1, +6.5] | ns |

### By Tier
| Condition | Tier A | Tier B | Tier C |
|---|---|---|---|
| B0 LLM Alone | 51.7% | 49.5% | 48.4% |
| B1 Latest Note | 66.7% | 79.4% | 74.2% |
| B2 All Notes RAG | 81.1% | 86.4% | 86.5% |
| B3 KG-RAG | 81.8% | 87.4% | 91.5% |
| B4 Full System | 82.6% | 90.1% | 90.3% |

### B2→B3 Delta by Tier
| Tier | Encounters | B2→B3 Delta | B2→B4 Delta |
|---|---|---|---|
| A | 1-2 notes | +0.6pp | +1.5pp |
| B | 5-10 notes | +1.0pp | +3.6pp |
| **C** | **15+ notes** | **+5.0pp** | **+3.8pp** |

---

## Sonnet 4.5 Run (2026-02-23, 4 patients)

### Configuration
- **LLM**: claude-sonnet-4-5-20250929 (Anthropic)
- **Judge**: claude-opus-4-6 (Anthropic)
- **Cohort**: 4 patients (2 Tier A, 2 Tier B), 24 questions each = 96 questions
- **Changes**: Structured KG prompts (`to_structured_llm_prompt()`), evidence hierarchy system prompt, multi-model judge

### Condition Scores
| Condition | Score | Delta vs B0 |
|---|---|---|
| B0 LLM Alone | 50.6% | — |
| B1 Latest Note | 73.0% | +22.4pp |
| B2 All Notes RAG | 83.8% | +33.2pp |
| B3 KG-RAG (structured prompts) | 84.6% | +34.0pp |
| B4 Full System | 86.3% | +35.7pp |

---

## Baseline Run (2026-02-22)

### Configuration
- **LLM + Judge**: claude-sonnet-4-5-20250929 (same model for both)
- **Cohort**: 4 patients (2 Tier A, 2 Tier B), 18 questions each = 72 questions
- **Templates**: 18 original (A1-E4), flat KG prompt format

### Condition Scores
| Condition | Mean | 95% CI |
|---|---|---|
| B0 LLM Alone | 46.9% | [38.9%, 55.2%] |
| B1 Latest Note | 81.2% | [74.2%, 87.5%] |
| B2 All Notes RAG | 91.5% | [85.8%, 95.9%] |
| B3 KG-RAG | 91.9% | [86.4%, 96.2%] |
| B4 Full System | 92.2% | [87.2%, 96.2%] |

---

## Cross-Model Comparison

| Metric | Sonnet 4.5 | Med Gemma 27B |
|---|---|---|
| B0 (no context) | 49.9% | 19.4% |
| B2 ceiling | 84.7% | **77.1%** |
| B2→B3 (KG layer) | +2.2pp (ns) | **+3.5pp** (ns) |
| B2→B4 (full uplift) | +3.0pp (ns) | **+3.5pp (*)** |
| B2→B4 significance | ns | **p<0.05** |
| Tier C B2→B4 | +3.8pp | **+6.9pp** |

The smaller answering model (Med Gemma 27B) lowers the B2 ceiling from 84.7% to 77.1%, creating more headroom for the KG layer. This pushes B2→B4 to statistical significance for the first time: **+3.5pp [+0.7, +6.6]**.

## Run-over-Run Progression

| Metric | Baseline | +Structured Prompts | +Tier C | Med Gemma 27B |
|---|---|---|---|---|
| B2→B3 delta | +0.4pp | +0.8pp | +2.2pp | **+3.5pp** |
| B2→B4 delta | +0.7pp | +2.5pp | +3.0pp | **+3.5pp (*)** |
| B2 ceiling | 91.5% | 83.8% | 84.7% | **77.1%** |
| B2→B4 sig? | ns | ns | ns | **yes** |

## Diagnosis

### What works:
1. **Smaller answering model is the biggest lever**: Med Gemma B0=19.4% (vs Sonnet 49.9%). The model knows almost nothing without context, making every context layer critical. RAG uplift is +57.6pp.
2. **Tier C patients amplify KG value**: Tier C B2→B4 = +6.9pp with Med Gemma, the largest single-tier uplift observed.
3. **Structured KG prompts**: Box-drawing assertion tables and evidence hierarchy help both models, but the effect is larger when the model can't compensate with parametric knowledge.
4. **B2→B4 reaches significance with Med Gemma**: +3.5pp [+0.7, +6.6]. The full EpiKG system (structured KG + guidelines + calculators) provides statistically significant uplift over document-only RAG.

### Remaining gaps:
1. **B2→B3 still not individually significant**: +3.5pp [-0.3, +7.6]. Very close — 0.3pp from the threshold. More patients or questions would likely push it over.
2. **B3→B4 is ~0pp with Med Gemma**: The guideline/calculator layer doesn't help (and has code errors). The B2→B4 significance comes entirely from the KG layer.
3. **Med Gemma Tier A outperforms Tier C on B2→B3**: +5.7pp vs +3.5pp. This reversal (opposite of Sonnet) suggests Med Gemma may benefit more from structured context even with few notes.

## Next Steps

### Immediate
1. **Fix calculator/KG errors** — `kg_edges.experiencer` column missing, `CalculatorReasoningService` argument error. These are silently degrading B4.
2. **More Tier C patients** — Increase from 2 to 4-6 Tier C patients. The CI on B2→B3 is [-0.3, +7.6] — very close to significance.
3. **Re-run Sonnet with fixed B4** — The calculator errors affect Sonnet too. Fixing may push Sonnet B2→B4 to significance.

### Follow-up
4. **KG-only questions** — Design questions that literally cannot be answered from raw notes.
5. **Per-question difficulty analysis** — Identify which questions discriminate best between B2 and B3.
6. **Additional models** — Test with Gemma3 27B (non-medical) to isolate whether Med Gemma's medical pretraining helps.

## Key Files
| File | Role |
|---|---|
| `backend/app/services/graph_augmented_rag.py` | `to_llm_prompt()` + `to_structured_llm_prompt()` |
| `backend/app/services/longbench_runner.py:107-135` | System prompts (BASE, NO_CONTEXT, EPISTEMIC with evidence hierarchy) |
| `backend/app/services/longbench_runner.py:345-425` | `_build_prompt()` — uses structured prompt for B3/B4 |
| `backend/app/services/longbench_runner.py:56-100` | CONDITION_CONFIGS — B3/B4 have `structured_prompt: True` |
| `backend/app/services/longbench_runner.py:597-668` | `_CriterionJudge` — supports separate judge model/provider |
| `backend/app/services/longbench_cohort.py` | 24 question templates (A1-F6), criteria functions |
| `backend/scripts/smoke_test_longbench.py` | CLI with `--judge-provider`, `--judge-model`, `--output-dir` |
| `backend/data/benchmarks/results/longbench_smoke/smoke_report.json` | Sonnet 4.5 results |
| `backend/data/benchmarks/results/medgemma_27b/smoke_report.json` | Med Gemma 27B results |
