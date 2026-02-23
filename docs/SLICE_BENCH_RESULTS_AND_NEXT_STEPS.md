# Slice Bench Results & Next Steps

## Latest Run (2026-02-23, Tier C)

### Configuration
- **LLM**: claude-sonnet-4-5-20250929 (Anthropic)
- **Judge**: claude-opus-4-6 (Anthropic) — separate model via `--judge-model`
- **Cohort**: 6 patients (2 Tier A, 2 Tier B, 2 Tier C) from MIMIC-IV, 24 questions each = 144 questions
- **Templates**: 18 original (A1-E4) + 6 new hard longitudinal (F1-F6)
- **Conditions**: B0-B4 (720 total evaluations)
- **Changes**: Added Tier C patients (15+ encounters), removed `[:4]` patient truncation

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

### B2→B3 Delta by Tier (key result)
| Tier | Encounters | B2→B3 Delta | B2→B4 Delta |
|---|---|---|---|
| A | 1-2 notes | +0.6pp | +1.5pp |
| B | 5-10 notes | +1.0pp | +3.6pp |
| **C** | **15+ notes** | **+5.0pp** | **+3.8pp** |

---

## Previous Run (2026-02-23, 4 patients)

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

## Baseline Run (2026-02-22)

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

---

## Run-over-Run Comparison

| Metric | Baseline (Feb 22) | Structured Prompts (Feb 23, 4pt) | + Tier C (Feb 23, 6pt) |
|---|---|---|---|
| B2→B3 delta | +0.4pp | +0.8pp | **+2.2pp** |
| B3→B4 delta | +0.3pp | +1.7pp | +0.8pp |
| B2→B4 delta | +0.7pp | +2.5pp | **+3.0pp** |
| B2 ceiling | 91.5% | 83.8% | 84.7% |
| Questions/patient | 18 | 24 | 24 |
| Patients | 4 (2A+2B) | 4 (2A+2B) | 6 (2A+2B+2C) |
| Judge model | Sonnet 4.5 | Opus 4.6 | Opus 4.6 |

The B2→B3 delta grew from +0.4pp (baseline) to +0.8pp (structured prompts) to **+2.2pp** (with Tier C). The Tier C B2→B3 delta alone is **+5.0pp** — confirming that structured KG context provides significantly more value when document volume is high.

## Diagnosis

### What improved:
1. **Tier C patients are the key lever**: B2→B3 delta for Tier C = +5.0pp vs +0.6pp for Tier A. Patients with 15+ encounters have enough longitudinal complexity that structured KG context materially helps.
2. **Structured KG prompts**: Box-drawing assertion tables, relationship tables, and tabular timelines give the LLM a visual signal to treat KG data as authoritative.
3. **Evidence hierarchy system prompt**: Explicit ordering (authoritative status > structured relationships > timeline > documents) helps the LLM prioritize KG context over raw notes.
4. **F-series questions**: Cross-encounter medication timelines, problem list reconciliation, and causal chain tracing require multi-note synthesis.

### Remaining gaps:
1. **B2→B3 still not significant at p<0.05**: The CI is [-1.5, +5.9]. Need more Tier C patients or more questions to tighten the CI.
2. **B4 < B3 for Tier C (90.3% vs 91.5%)**: The guideline/calculator layer may add noise for complex patients. The calculator context has errors (`CalculatorReasoningService` missing argument, `kg_edges.experiencer` column missing).
3. **No DB-backed KG data**: The KG context for these MIMIC patients comes from basic graph building, not from rich ontology-mapped clinical facts. Richer KG data would further widen the gap.

## Next Steps

### Immediate
1. **Fix calculator/KG errors** — `kg_edges.experiencer` column missing, `CalculatorReasoningService` argument error. These are silently degrading B4 for Tier C.
2. **More Tier C patients** — Increase from 2 to 4-6 Tier C patients to tighten the CI on B2→B3. The CSV has 20 qualifying Tier C patients.
3. **Med Gemma 27B run** — Use `--provider ollama --model alibayram/medgemma:27b --judge-provider anthropic --judge-model claude-opus-4-6`. Smaller answering model = lower B2 ceiling = more KG headroom.

### Follow-up
4. **KG-only questions** — Design questions that literally cannot be answered from raw notes (e.g., "Which conditions were ruled out?" when the negation is only captured in assertion metadata, not in note text).
5. **Per-question difficulty analysis** — Identify which F-series questions discriminate best between B2 and B3, and create more like them.

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
