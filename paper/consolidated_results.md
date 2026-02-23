# Consolidated Results for Paper Writers

## ClinicalBench (400 questions, MedGemma 27B, LLM-judged)

### Overall Accuracy & Safety
| Condition | Label | Accuracy | Safety Score |
|---|---|---|---|
| C1 | LLM Alone | 71.5% | 0.752 |
| C2 | LLM + Vanilla RAG | 62.5% | 0.643 |
| C3 | LLM + KG-RAG | 59.3% | 0.562 |
| C4 | LLM + Epistemic KG-RAG | 71.5% | 0.775 |
| C5 | Full System | 68.3% | 0.734 |

### Key Deltas
- C1→C2: -9.0pp (vanilla RAG HURTS)
- C2→C4: +9.0pp (epistemic KG-RAG recovers)
- C1 vs C4: tie at 71.5%, but different accuracy profiles
- C4→C5: -3.2pp (full system adds noise from calculator errors)

### Per-Category Accuracy (9 categories)
| Category | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| negation | 100.0% | 93.6% | 81.8% | 100.0% | 98.2% |
| conditional | 100.0% | 90.0% | 55.0% | 70.0% | 75.0% |
| uncertainty | 37.5% | 2.5% | 7.5% | 57.5% | 40.0% |
| family_history | 0.0% | 0.0% | 53.3% | 70.0% | 56.7% |
| sequence | 80.0% | 80.0% | 80.0% | 87.5% | 77.5% |
| current_state | 64.0% | 54.0% | 50.0% | 54.0% | 58.0% |
| duration | 100.0% | 100.0% | 83.3% | 83.3% | 73.3% |
| historical | 94.0% | 78.0% | 68.0% | 60.0% | 68.0% |
| change | 0.0% | 0.0% | 3.3% | 3.3% | 3.3% |

### Key Category Findings
- **Uncertainty**: C4 (57.5%) >> C1 (37.5%) >> C2 (2.5%) — +20pp C4 vs C1, +55pp C4 vs C2
- **Family History**: C4 (70.0%) >> C1 (0.0%) = C2 (0.0%) — epistemic KG enables family history queries
- **Negation**: C1=C4=100%, C2=93.6% — vanilla RAG slightly degrades negation handling
- **Historical**: C1 (94.0%) > C2 (78.0%) > C4 (60.0%) — trade-off: C4 loses historical accuracy

### Safety Scores
C4 (0.775) > C1 (0.752) > C5 (0.734) > C2 (0.643) > C3 (0.562)

---

## Slice Bench (144 questions, 6 patients, Claude Sonnet 4.5, Opus 4.6 judge)

### Overall Results (Bootstrap 95% CIs, n=2000, seed=42)
| Condition | Score | 95% CI | Delta vs B0 |
|---|---|---|---|
| B0 LLM Alone | 49.9% | [43.6%, 56.1%] | — |
| B1 Latest Note | 73.4% | [67.8%, 78.7%] | +23.5pp |
| B2 All Notes RAG | 84.7% | [80.2%, 88.8%] | +34.8pp |
| B3 KG-RAG | 86.9% | [82.8%, 90.8%] | +37.0pp |
| B4 Full System | 87.6% | [83.7%, 91.2%] | +37.8pp |

### Paired Deltas
| Comparison | Delta | CI | Sig |
|---|---|---|---|
| B0→B2 (RAG uplift) | +34.8pp | [+26.8, +42.4] | * |
| B2→B3 (KG layer) | +2.2pp | [-1.5, +5.9] | ns |
| B3→B4 (guidelines+calc) | +0.8pp | [-2.5, +4.2] | ns |
| B2→B4 (full uplift) | +3.0pp | [-0.1, +6.5] | ns |

### By Tier (KEY RESULT)
| Condition | Tier A (1-2 notes) | Tier B (5-10 notes) | Tier C (15+ notes) |
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

Key: B2→B3 delta is 8x larger for Tier C than Tier A

### B4 < B3 for Tier C
- B3 = 91.5%, B4 = 90.3% for Tier C
- Calculator/guideline integration adds noise (known bugs: missing experiencer column, CalculatorReasoningService arg error)

---

## MedQA-USMLE Results (LLM-alone baseline)
| Model | Accuracy | N |
|---|---|---|
| EpiKG (Claude Opus 4.5, LLM alone) | 81.6% | 965 |
| GPT-4 (2023) | 86.7% | 1,273 |
| Med-PaLM 2 (2023) | 86.5% | 1,273 |
| Claude-3 Opus (2024) | 78.0% | 1,273 |

## DR.KNOWS KG Reasoning
| Metric | Score |
|---|---|
| Overall | 0.420 (49.7% of baseline) |
| 1-hop traversal | 50.0% |
| 2-hop traversal | 25.0% |
| 3-hop traversal | 0.0% |
Note: PostgreSQL CTE traversal limitation; intentional tradeoff for ACID compliance

## Scalability
| Metric | Value |
|---|---|
| Documents | 145 |
| Patients | 85 |
| KG nodes | 3,100 |
| KG edges | 8,803 |
| 1-hop latency | 0.57ms |
| 2-hop latency | 0.75ms |

## Human Validations (5 reviews by Alex Stinard, MD)
- Small sample; too few for statistical analysis
- Reviews cover MedGemma C1 condition
- Found auto-scoring too harsh on uncertainty/sequence questions

## System Scale
| Component | Scale |
|---|---|
| Clinical calculators | 201 |
| Guideline sections | 1,202 |
| OMOP vocabulary relationships | 20M+ |
| NLP ensemble models | 3 |
| Assertion trigger patterns | 101 |
| Edge types | 24 |
| Node types | 13 |
| Assertion classes | 7 |
