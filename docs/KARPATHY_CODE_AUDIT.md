# Karpathy-Style Code Audit Plan

## Codebase Statistics

| Category | Lines of Code | Files |
|----------|---------------|-------|
| Backend Python | 307,447 | 539 |
| Frontend TS/TSX | 118,232 | 198 |
| **Total** | **425,679** | **737** |

### Backend Breakdown by Directory
| Directory | Lines |
|-----------|-------|
| services/ | 131,135 |
| api/ | 64,223 |
| connectors/ | 5,675 |
| etl/ | 5,196 |
| models/ | 5,531 |
| schemas/ | 2,800 |
| scripts/ | 2,624 |
| core/ | 1,536 |
| cli/ | 321 |
| jobs/ | 315 |

---

## Andrej Karpathy's Code Quality Principles

Based on research from his projects (nanoGPT, nanochat, llm.c, micrograd) and recent X posts:

### 1. **Simplicity Over Complexity**
- nanoGPT: ~300 lines for train.py, ~300 for model.py
- llm.c: 1,000 lines for complete LLM training in one file
- "The simplest, fastest repository" philosophy

### 2. **Readability & Hackability**
- Code should be easy to understand and modify
- Clean, understandable codebase that allows learning
- "Easy to hack to your needs"

### 3. **Minimal Dependencies**
- llm.c: No PyTorch (245MB) or cPython (107MB)
- "Dependency-minimal codebase"

### 4. **Single-File When Possible**
- Prefer cohesive, minimal, readable, maximally forkable repos
- One file > many files if it makes sense

### 5. **Step-by-Step Commits**
- Git history should show gradual building
- Each commit is a clean, understandable step

### 6. **AI-Assisted Coding Workflow** (2025-2026)
- Stuff everything relevant into context
- Describe single concrete incremental changes
- Ask for high-level approaches first (LLM judgment varies)
- "Vibe coding" for prototypes vs careful review for production

### 7. **Context Engineering**
- "Filling the context window with just the right information"
- Too little = poor performance, too much = increased costs

---

## Audit Categories (100 Spots)

### Phase 1: Services Layer (50 spots) - 131,135 lines
**⚠️ CAUTION: knowledge_graph area has another agent working - coordinate before changes**

| # | Area | Est. Lines | Focus |
|---|------|------------|-------|
| 1-5 | services/agents/ | ~10,000 | Agent orchestration complexity |
| 6-10 | services/nlp/ | ~15,000 | NLP processing pipelines |
| 11-15 | services/fhir/ | ~12,000 | FHIR integration |
| 16-20 | services/auth/ | ~5,000 | Authentication/RBAC |
| 21-25 | services/pipeline/ | ~8,000 | Data pipeline services |
| 26-30 | services/export/ | ~3,000 | Export functionality |
| 31-35 | services/analytics/ | ~10,000 | Analytics services |
| 36-40 | services/search/ | ~8,000 | Search functionality |
| 41-45 | services/clinical/ | ~15,000 | Clinical services |
| 46-50 | services/* (misc) | ~45,000 | Remaining services |

### Phase 2: API Layer (25 spots) - 64,223 lines

| # | Area | Est. Lines | Focus |
|---|------|------------|-------|
| 51-55 | api/middleware/ | ~5,000 | Middleware complexity |
| 56-60 | api/graphql/ | ~10,000 | GraphQL endpoints |
| 61-70 | api/*.py (REST) | ~40,000 | REST API endpoints |
| 71-75 | api/validation | ~9,000 | Input validation |

### Phase 3: Models & Schemas (10 spots) - 8,331 lines

| # | Area | Est. Lines | Focus |
|---|------|------------|-------|
| 76-80 | models/ | ~5,531 | Data models |
| 81-85 | schemas/ | ~2,800 | Pydantic schemas |

### Phase 4: Infrastructure (5 spots) - 7,847 lines

| # | Area | Est. Lines | Focus |
|---|------|------------|-------|
| 86-87 | core/ | ~1,536 | Core config |
| 88-89 | connectors/ | ~5,675 | External connectors |
| 90 | etl/ | ~636 | ETL pipelines |

### Phase 5: Frontend (10 spots) - 118,232 lines

| # | Area | Est. Lines | Focus |
|---|------|------------|-------|
| 91-93 | components/ | ~40,000 | React components |
| 94-96 | app/ | ~50,000 | Next.js pages |
| 97-98 | hooks/ | ~15,000 | Custom hooks |
| 99-100 | types/ & utils/ | ~13,000 | Types and utilities |

---

## Audit Checklist Per Spot

For each spot, evaluate against Karpathy principles:

### Simplicity Check
- [ ] Could this be done in fewer lines?
- [ ] Are there unnecessary abstractions?
- [ ] Is there dead code that can be removed?

### Readability Check
- [ ] Can a new developer understand this in 5 minutes?
- [ ] Are variable/function names self-documenting?
- [ ] Is the control flow clear?

### Dependency Check
- [ ] Are all imports necessary?
- [ ] Could we use standard library instead of third-party?
- [ ] Are there circular dependencies?

### Cohesion Check
- [ ] Does this file/module do one thing well?
- [ ] Is related code grouped together?
- [ ] Should this be split or merged?

### Documentation Check
- [ ] Is the purpose clear without excessive comments?
- [ ] Are edge cases documented?
- [ ] Is the API surface intuitive?

---

## Execution Strategy

### Sub-Agent Orchestration

```
Main Agent (Orchestrator)
├── Agent 1: Services Audit (spots 1-50)
│   └── ⚠️ Skip knowledge_graph - coordinate first
├── Agent 2: API Audit (spots 51-75)
├── Agent 3: Models/Schemas Audit (spots 76-85)
├── Agent 4: Infrastructure Audit (spots 86-90)
└── Agent 5: Frontend Audit (spots 91-100)
```

### Progress Tracking
- Use GitHub Issues for each major phase
- Create PR with findings for each phase
- Document decisions in this file

---

## Findings Log

### Phase 1 Findings
_(To be filled during audit)_

### Phase 2 Findings
_(To be filled during audit)_

### Phase 3 Findings
_(To be filled during audit)_

### Phase 4 Findings
_(To be filled during audit)_

### Phase 5 Findings
_(To be filled during audit)_

---

## Sources

- [nanoGPT - GitHub](https://github.com/karpathy/nanoGPT)
- [llm.c - GitHub](https://github.com/karpathy/llm.c)
- [Karpathy X Post on AI Coding Workflow](https://x.com/karpathy/status/1915581920022585597)
- [Karpathy "Never felt this behind" Post](https://x.com/karpathy/status/2004607146781278521)
- [Software 3.0 Keynote](https://www.latent.space/p/s3)
- [Context Engineering Discussion](https://pureai.com/articles/2025/09/23/karpathy-puts-context-at-the-core-of-ai-coding.aspx)

---

## Phase 2 Findings: API Layer Audit (COMPLETED)

**Overall Score: 2.8/5** (Below Target of 4/5)

### Critical Files Needing Work

| File | Lines | Routes | Complexity | Status |
|------|-------|--------|------------|--------|
| documents.py | 3,165 | 29 | 4/5 | 🔴 CRITICAL |
| etl.py | 1,986 | 22 | 3/5 | 🟡 IMPROVABLE |
| graph.py | 1,938 | 12 | 3/5 | 🟡 IMPROVABLE |
| quality.py | 1,480 | 13 | 3/5 | 🟡 IMPROVABLE |
| nlp.py | 1,422 | 10 | 2/5 | 🟢 GOOD |

### Critical Issues Found

1. **Dependency Injection Anti-Pattern** - Every endpoint repeats `Depends(get_db), Depends(get_current_user), Depends(get_logger)` - should use single `RequestContext`

2. **Error Handling Inconsistency** - Mix of custom exceptions and HTTPException, no centralized error mapping

3. **Response Model Explosion** - 200+ response models, many near-duplicates

4. **documents.py is 3,165 lines** - Should split into: core.py, fhir.py, bulk.py, search.py, tags.py

### Priority Actions

| Priority | Action | Impact | Effort |
|----------|--------|--------|--------|
| 🔴 HIGH | Split documents.py into 4 routers | Complexity 4→2 | 4h |
| 🔴 HIGH | Create RequestContext dependency | -300 lines | 2h |
| 🔴 HIGH | Extract shared error handling | Consistency | 1h |
| 🟡 MED | Split quality.py into two routers | Clarity | 2h |
| 🟡 MED | Parameterize Neo4j queries | Security | 2h |


---

## Phase 3 Findings: Models & Schemas Audit (COMPLETED)

**Overall Score: 3.2/5** (Needs consolidation)

### Key Statistics
- **Total Model Files:** 18
- **Total SQLAlchemy Models:** 88
- **Total Pydantic Schemas:** 100+
- **Total Enums:** 31 (should be ~15)

### Complexity by File

| File | Lines | Models | Complexity | Status |
|------|-------|--------|------------|--------|
| omop.py | 901 | 24 | 5/5 | 🔴 CRITICAL |
| x12.py | 710 | 30 | 4/5 | 🔴 CRITICAL |
| policy_kg.py | 471 | 3 | 3/5 | 🟡 REDUNDANT |
| kg_requests.py | 786 | 25 | 4/5 | 🟡 TOO LARGE |
| kg_responses.py | 536 | 20 | 4/5 | 🟡 TOO LARGE |
| clinical_fact.py | 160 | 2 | 1/5 | 🟢 EXCELLENT |
| document.py | 118 | 2 | 1/5 | 🟢 EXCELLENT |

### Critical Issues Found

1. **OMOP Source Field Duplication** - Every table repeats `concept_id + source_value + source_concept_id` pattern
   - Example: `gender_concept_id`, `gender_source_value`, `gender_source_concept_id`
   - **Fix:** Create generic `ConceptReference` model or use JSONB

2. **X12 Provider Type Proliferation** - 5 near-identical provider schemas
   - `X12Provider`, `X12RenderingProvider`, `X12ReferringProvider`, etc.
   - **Fix:** Single `X12Entity(role: Enum)` model

3. **PolicyRule is Redundant** - Duplicates PolicyKGNode with `if_conditions`, `then_actions`
   - **Fix:** Delete PolicyRule, compute denormalized views on demand

4. **Schema Create/Response Duplication** - 90% identical pairs everywhere
   - **Fix:** Single model with optional `id` field

5. **Enum Proliferation** - 31 enums, many should be lookup tables (especially X12's 13 enums)

### Priority Actions

| Priority | Action | Impact |
|----------|--------|--------|
| 🔴 CRITICAL | Remove OMOP source duplication | -301 lines |
| 🔴 CRITICAL | Consolidate X12 provider types | -210 lines |
| 🔴 CRITICAL | Eliminate PolicyRule redundancy | -100 lines |
| 🟡 HIGH | Merge Create/Response schemas | -40% schema lines |
| 🟡 HIGH | Split kg_requests/responses | Maintainability |


---

## Phase 5 Findings: Frontend Audit (COMPLETED)

**Overall Score: 2.4/5** (Needs significant refactoring)

### Top 10 Largest Components

| Component | Lines | Complexity | Status |
|-----------|-------|------------|--------|
| KnowledgeGraph.tsx | 2,365 | 5/5 | 🔴 CRITICAL |
| ClinicalSearch.tsx | 565 | 4/5 | 🔴 HIGH |
| AssistantWidget.tsx | 508 | 4/5 | 🔴 HIGH |
| Header.tsx | 453 | 4/5 | 🔴 HIGH |
| use-api.ts | 886 | 4/5 | 🔴 CRITICAL |
| use-auth.tsx | 603 | 4/5 | 🔴 HIGH |

### Critical Issues Found

1. **KnowledgeGraph.tsx is 2,365 lines** - D3 logic mixed with React state
   - ~40 useState calls, monolithic structure
   - **Fix:** Split into 5 files: orchestrator, GraphNode, GraphEdge, useD3Simulation, useGraphInteraction

2. **use-api.ts exports 50+ hooks in one file** (886 lines)
   - Should split into domain-specific files: useDocuments.ts, usePatients.ts, etc.

3. **use-auth.tsx mixes 6 concerns** (603 lines)
   - Auth state, token storage, API calls, password validation all in one file
   - **Fix:** Split into auth context, authStorage, authApi, usePasswordStrength

4. **Notifications.tsx has 150 lines of duplicated code**
   - Same handlers duplicated between component and hook versions

5. **5 components exceed 400 lines** - All violate single responsibility

### Karpathy Principles Scorecard

| Principle | Score | Status |
|-----------|-------|--------|
| Simplicity | 2/5 | ❌ FAIL |
| Modularity | 3/5 | ⚠️ PARTIAL |
| Reusability | 2/5 | ❌ FAIL |
| Testability | 2/5 | ⚠️ POOR |
| Prop Drilling | 4/5 | ✅ GOOD |

### Priority Actions

| Priority | Action | Impact |
|----------|--------|--------|
| 🔴 P0 | Split KnowledgeGraph.tsx (2365→5 files) | CRITICAL |
| 🔴 P0 | De-duplicate Notifications.tsx | -150 lines |
| 🔴 P0 | Split use-auth.tsx (603→4 files) | Testability |
| 🟡 P1 | Split ClinicalSearch.tsx (565→4 files) | HIGH |
| 🟡 P1 | Refactor use-api.ts (886→8+ domain files) | HIGH |


---

## Phase 4 Findings: Infrastructure Audit (COMPLETED)

**Overall Assessment:** Good foundation but significant duplication

### Core Config (Excellent ✓)
- config.py: 61 lines, Complexity 1/5 - **KEEP AS-IS**
- database.py: 102 lines, Complexity 1/5 - **KEEP AS-IS**
- redis.py: 49 lines, Complexity 1/5 - **KEEP AS-IS**

### Critical Duplications Found

1. **auth.py + security.py + tenant.py OVERLAP** (~450 lines → 150 lines)
   - All three implement overlapping access control
   - `verify_api_key()` defined in BOTH auth.py and security.py
   - `TenantContext` defined in BOTH security.py and tenant.py
   - **Fix:** Merge into single security.py

2. **Connector Concept Maps Duplicated** (~200 lines wasted)
   - Each connector (FHIR, HL7, CCDA, CSV, DB) redefines same OMOP mappings
   - GENDER_CONCEPT_MAP, ROUTE_CONCEPT_MAP, etc.
   - **Fix:** Create connectors/concept_mappings.py

3. **ETL Concept Maps Duplicated** (~600 lines wasted)
   - 10 ETL modules each redefine OMOP concept mappings
   - Same pattern: CONDITION_TYPE_CONCEPT_MAP, MEASUREMENT_TYPE_CONCEPT_MAP
   - **Fix:** Create etl/concept_mappings.py

4. **ETLConfig/ETLResult Classes Duplicated** (~200 lines)
   - Identical dataclasses in every ETL module
   - **Fix:** Create BaseETLConfig and BaseETLResult

### Connector Sizes

| Connector | Lines |
|-----------|-------|
| CCDA | 1,156 |
| Database | 1,071 |
| Base | 946 |
| FHIR | 858 |
| HL7v2 | 803 |
| CSV | 753 |

### ETL Sizes

| ETL Module | Lines |
|------------|-------|
| device_etl | 730 |
| specimen_etl | 694 |
| person_etl | 577 |
| condition_etl | 531 |
| measurement_etl | 512 |

### Priority Actions

| Priority | Action | Savings |
|----------|--------|---------|
| 🔴 CRITICAL | Merge auth+security+tenant | -300 lines |
| 🔴 CRITICAL | Extract ETL concept mappings | -600 lines |
| 🔴 CRITICAL | Create BaseETL class | -400 lines |
| 🟡 HIGH | Extract connector concept mappings | -200 lines |
| 🟡 HIGH | Create ETLPipeline orchestrator | Better arch |

**Total Potential Savings: ~1,500 lines**

