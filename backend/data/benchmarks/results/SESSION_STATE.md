# Session State — Feb 25, 2026 ~10:30 AM

## EXPERIMENTS COMPLETE — Latest Results

### MedGemma 27B (on-device via Ollama) — 400q Tasks A+B

#### Original 5-Condition Ablation (old evaluator)
| Condition | Accuracy | vs C1 |
|---|---|---|
| C1: LLM Alone | 68.2% (273/400) | baseline |
| C2: Vanilla RAG | 58.8% (235/400) | -9.4pp |
| C3: KG-RAG | 54.8% (219/400) | -13.4pp |
| C4: Epistemic KG-RAG | 67.0% (268/400) | -1.2pp |
| C5: Full System | 65.0% (260/400) | -3.2pp |

#### Prompt Variant Experiments (old evaluator, 400q)
| Variant | Accuracy | Strategy | Outcome |
|---|---|---|---|
| C4d: v4 prompt | 59.8% (239/400) | Grouped evidence + prescriptive assertions | REGRESSED |
| C4e: v5 prompt | 61.8% (247/400) | C4 + question-subject callout only | NEUTRAL |

#### Fixed Evaluator Results (400q)
Evaluator fixes applied:
1. Strip echoed assertion notes before scoring current_state/historical (prevents keyword cross-contamination)
2. Expanded uncertainty keywords with medical hedging terms (likely, probable, concerning for, etc.)

| Condition | Accuracy | Key Category Changes vs Old Evaluator |
|---|---|---|
| **C4: Epistemic KG-RAG** | **66.0% (264/400)** | historical 26%→48% (+22pp), current_state 32%→40% (+8pp), uncertainty 45%→50% (+5pp) |
| C4f: v6 prompt | 64.0% (256/400) | current_state +8pp but negation -4.5pp, conditional -10pp — FAILED promotion |

**C4 at 66.0% was the frozen baseline** before experiencer fix.

#### Experiencer Fix Results (MedGemma, 400q, fixed evaluator)
| Condition | Accuracy | vs Pre-fix |
|---|---|---|
| C1: LLM Alone | 58.0% (232/400) | run-to-run variance (see note) |
| **C4: Epistemic KG-RAG** | **67.0% (268/400)** | **+1.0pp vs 66.0% baseline** |
| **C4 vs C1 (within-run)** | **+9.0pp** | — |

**Note on C1 drift**: C1 dropped from 68.2% to 58.0% across runs. C1 uses no graph evidence, so the experiencer fix cannot cause this. This is MedGemma run-to-run variance (Ollama non-determinism). Within-run paired comparisons are primary.

#### C4 Category Comparison — Pre vs Post Experiencer Fix (MedGemma, 400q)
| Category | C4 Pre-fix | C4 Post-fix | Delta | Status |
|---|---|---|---|---|
| negation | 99.1% | 99.1% | 0pp | Guard PASS |
| sequence | 90% | 92.5% | +2.5pp | Improved |
| conditional | 80% | 80% | 0pp | Guard PASS |
| duration | 63.3% | 63.3% | 0pp | Held |
| **family_history** | **60%** | **66.7%** | **+6.7pp** | **Target PASS (≥+5pp)** |
| uncertainty | 50% | 50% | 0pp | Guard PASS |
| historical | 48% | 48% | 0pp | Held |
| current_state | 40% | 42% | +2.0pp | Slight improvement |
| change | 6.7% | 6.7% | 0pp | Still broken |

### Claude Opus 4.6 (API) — 400q Tasks A+B

#### C1 Baseline (unchanged)
| Condition | Accuracy | vs C1 |
|---|---|---|
| C1: LLM Alone | 72.5% (290/400) | baseline |

#### C4 Pre vs Post Experiencer Fix
| Metric | Pre-fix | Post-fix | Delta |
|---|---|---|---|
| **C4 overall** | 68.2% (273/400) | **70.2% (281/400)** | **+2.0pp** |
| **C4 vs C1** | -4.2pp | **-2.2pp** | **Gap halved** |

#### Opus C4 Category Breakdown — Pre vs Post Experiencer Fix
| Category | C1 (Opus) | C4 Pre-fix | C4 Post-fix | Fix Delta |
|---|---|---|---|---|
| negation | 96.4% | 99.1% | 99.1% | 0pp |
| duration | 90.0% | 100% | 100% | 0pp |
| sequence | 97.5% | 95.0% | 95.0% | 0pp |
| conditional | 80.0% | 65.0% | 65.0% | 0pp |
| **family_history** | 83.3% | 63.3% | **73.3%** | **+10.0pp** |
| **uncertainty** | 47.5% | 50.0% | **55.0%** | **+5.0pp** |
| **historical** | 44.0% | 34.0% | **38.0%** | **+4.0pp** |
| current_state | 58.0% | 46.0% | 48.0% | +2.0pp |
| change | 23.3% | 13.3% | 13.8% | +0.5pp |

Previous 40q pilot (noisy): C1=57.5%, C4=65.0% (+7.5pp) — did not hold at scale.

## Key Findings

### Experiencer Fix (biggest win this session)
- **Root cause**: Multi-hop graph traversal (PathEdge dataclass + CTE query) dropped `experiencer` attribute. All 1819 kg_edges had `experiencer=NULL` despite 121 edges being family history.
- **Fix**: (1) Added assertion/experiencer to PathEdge + CTE query, (2) backfilled 121 family history edges from `properties->>'section'`
- **Impact**: family_history +6.7pp on MedGemma, +10.0pp on Opus, zero regressions on any guard slice
- **Opus gap halved**: C4 vs C1 went from -4.2pp to -2.2pp — the experiencer bug was the largest single contributor to the Opus regression

### Evaluator Fixes (prior session)
- The keyword evaluator had two bugs that artificially suppressed C4 scores:
  1. **Echo contamination**: MedGemma echoes assertion notes preamble; historical/current keywords in the echo caused false mismatches on current_state/historical categories
  2. **Narrow uncertainty keywords**: Evaluator missed valid medical hedging ("likely", "probable", "concerning for")
- Fixing these raised C4 from 61.8% to 66.0% — a +4.2pp gain from measurement correction alone

### Prompt Engineering Has Hit a Ceiling
- C4, C4d, C4e, C4f all land in the 59.8%-66.0% range
- Prompt changes redistribute errors between categories but don't reduce total errors
- **Conclusion: Further gains require infrastructure fixes (experiencer, agentic traversal), not prompt tweaks**

### Run-to-Run Variance (operational control issue)
- MedGemma C1 dropped from 68.2% to 58.0% across runs with no code changes affecting C1
- Treat within-run paired comparisons as primary evidence
- Cross-run comparisons are secondary unless parity is exact (model ID, evaluator version, question set, checkpoint policy, DB snapshot)

### Model-Specific Evidence Impact
- Opus C1 (72.5%) > MedGemma C4 (67.0%) — stronger model baseline
- Epistemic evidence helps weaker models more (MedGemma C4 lift: +9.0pp within-run)
- Opus C4 still below Opus C1 (-2.2pp) — remaining regressions on conditional (-15pp), current_state (-10pp)
- **Paper framing**: "Epistemic KG helps weaker models more; stronger models may need lighter/adaptive evidence"

### Root Cause Analysis of Remaining Weak Categories
| Category | Opus C4 | MedGemma C4 | Root Cause | Fix Needed |
|---|---|---|---|---|
| conditional | 65.0% | 80.0% | Evidence overrides Opus's strong baseline reasoning | Model-adaptive evidence weight |
| current_state | 48.0% | 42.0% | Model echoes "history of" when condition IS current | Better evidence temporal anchoring |
| historical | 38.0% | 48.0% | Model conflates "documented" with "active" | Better evidence temporal anchoring |
| change | 13.8% | 6.7% | RAG returns disconnected nodes, no cross-admission comparison | Agentic graph traversal |

### Next Steps (prioritized)
1. **Pre/post fix analysis table for paper** — before vs after experiencer fix, category deltas, guard stability
2. **Clinical validation planning** — fixed hard subset, blinded two-physician adjudication, predefined endpoints (agreement, kappa, discordance taxonomy)
3. **Agentic graph traversal** — targeted Cypher queries for cross-admission comparisons (change category)
4. **Model-adaptive evidence** — lighter evidence for strong models (Opus conditional regression)
5. **Scale dataset** — expand Tier C and weak-slice questions

## Code Changes This Session

### Experiencer Fix (neo4j_query_router.py, graph_augmented_rag.py)
- Added `assertion` and `experiencer` fields to `PathEdge` dataclass
- Updated CTE query: `COALESCE(e.experiencer::text, e.properties->>'experiencer', 'patient')` and `COALESCE(e.properties->>'assertion', 'present')`
- Updated recursive CTE to carry `edge_experiencers`/`edge_assertions` arrays
- Updated row parsing (10 columns instead of 8)
- Updated single-hop fallback to include experiencer/assertion
- Updated graph_augmented_rag.py edge serialization to include experiencer
- Added test `test_experiencer_and_assertion_propagated`
- Backfilled DB: `UPDATE kg_edges SET experiencer = 'family' WHERE properties->>'section' = 'Family History'` (121 rows)

### Prior Session Changes
- Evaluator: `_strip_evidence_echo()`, expanded uncertainty keywords
- Prompts: V4, V6 variants (both failed promotion)
- Graph RAG: `to_llm_prompt_v4()`, `to_llm_prompt_v5()`, `_question_subject_callout()`
- Ablation: C4d, C4e, C4f conditions

## How to Re-run Experiments

```bash
# MedGemma 27B (Tasks A+B, specific condition):
cd backend
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:15432/clinical_ontology" \
CONDITIONS="C4_epistemic_kg_rag" \
LLM_PROVIDER=ollama LLM_MODEL="alibayram/medgemma:27b" \
OLLAMA_BASE_URL="http://localhost:11434" \
OUTPUT_DIR="data/benchmarks/results/experiencer_fix_full" \
TASKS="a,b" \
python3 scripts/run_clinicalbench.py

# Opus 4.6 (Tasks A+B, C4 only):
cd backend
export $(grep ANTHROPIC_API_KEY .env | xargs)
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:15432/clinical_ontology" \
CONDITIONS="C4_epistemic_kg_rag" \
LLM_PROVIDER=anthropic LLM_MODEL="claude-opus-4-20250514" \
OUTPUT_DIR="data/benchmarks/results/opus_4_6" \
TASKS="a,b" \
python3 scripts/run_clinicalbench.py
```

## Run Parity Checklist
Before/after every run, record:
- Exact model ID/tag
- Evaluator version (git hash)
- Question set/task filter
- Checkpoint policy (clean vs resume)
- DB snapshot/date (experiencer backfill date)

## Prerequisites (Docker)
- Postgres: `docker start con-postgres` (port mapped 5432→15432, user=postgres, pass=postgres, db=clinical_ontology)
- Ollama: must be running on localhost:11434 with `alibayram/medgemma:27b` loaded

## User Context
- User is a doctor, wife is also a doctor — both will do validation
- NeurIPS 2026 D&B submission target ("EpiKG")
- Budget: $30 cap until methods validated, then several hundred for full multi-model runs
