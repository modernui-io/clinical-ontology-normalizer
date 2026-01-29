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
