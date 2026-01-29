# Karpathy Refactoring Master Todo List

**Created**: 2026-01-28
**Target**: Reduce complexity while maintaining 100% test pass rate
**Strategy**: Safe incremental changes, test after each step

---

## 🟢 TIER 1: Low-Risk File Splits (No behavior change)

### Backend API Splits
- [ ] **1.1** Split `documents.py` (3,165 lines → 5 files)
  - [ ] documents_core.py (CRUD operations)
  - [ ] documents_fhir.py (FHIR export/import)
  - [ ] documents_bulk.py (bulk operations)
  - [ ] documents_search.py (search endpoints)
  - [ ] documents_tags.py (tagging)
  - **Test**: Run `pytest tests/test_documents*.py`

- [ ] **1.2** Split `etl.py` (1,986 lines → 3 files)
  - [ ] etl_core.py (base operations)
  - [ ] etl_connectors.py (data source connectors)
  - [ ] etl_mappings.py (code mapping endpoints)
  - **Test**: Run `pytest tests/test_etl*.py`

- [ ] **1.3** Split `quality.py` (1,480 lines → 2 files)
  - [ ] quality_checks.py (quality checking)
  - [ ] quality_reports.py (reporting)
  - **Test**: Run `pytest tests/test_quality*.py`

### Backend Service Splits
- [ ] **1.4** Split `nlp_entity_service.py` (5,563 lines → 4 files)
  - [ ] nlp_entity_core.py (main service)
  - [ ] nlp_entity_extractors.py (entity extractors)
  - [ ] nlp_entity_linkers.py (linking logic)
  - [ ] nlp_entity_normalizers.py (normalization)
  - **Test**: Run `pytest tests/test_nlp*.py`

- [ ] **1.5** Split `auth_service.py` (845 lines → 3 files)
  - [ ] auth_core.py (main auth logic)
  - [ ] auth_tokens.py (JWT handling)
  - [ ] auth_password.py (password utilities)
  - **Test**: Run `pytest tests/test_auth*.py`

### Frontend Component Splits
- [ ] **1.6** Split `KnowledgeGraph.tsx` (2,365 lines → 5 files)
  - [ ] KnowledgeGraph/index.tsx (orchestrator)
  - [ ] KnowledgeGraph/GraphCanvas.tsx (D3 rendering)
  - [ ] KnowledgeGraph/GraphNode.tsx (node component)
  - [ ] KnowledgeGraph/GraphEdge.tsx (edge component)
  - [ ] KnowledgeGraph/useGraphState.ts (state hook)
  - **Test**: Run `npm test -- KnowledgeGraph`

- [ ] **1.7** Split `use-api.ts` (886 lines → 8 files)
  - [ ] hooks/useDocuments.ts
  - [ ] hooks/usePatients.ts
  - [ ] hooks/usePipelines.ts
  - [ ] hooks/useAnalytics.ts
  - [ ] hooks/useSearch.ts
  - [ ] hooks/useAdmin.ts
  - [ ] hooks/useNLP.ts
  - [ ] hooks/api-base.ts (shared utilities)
  - **Test**: Run `npm test -- api`

- [ ] **1.8** Split `use-auth.tsx` (603 lines → 4 files)
  - [ ] auth/AuthContext.tsx (context provider)
  - [ ] auth/authStorage.ts (token storage)
  - [ ] auth/authApi.ts (API calls)
  - [ ] auth/usePasswordStrength.ts (validation)
  - **Test**: Run `npm test -- auth`

---

## 🟡 TIER 2: Medium-Risk Consolidations

### Extract Shared Dependencies
- [ ] **2.1** Create `RequestContext` dependency (saves ~300 lines)
  - Create `app/core/dependencies.py`
  - Consolidate repeated `Depends(get_db), Depends(get_current_user), Depends(get_logger)`
  - **Test**: Run full API test suite

- [ ] **2.2** Extract ETL concept mappings (saves ~600 lines)
  - Create `app/etl/concept_mappings.py`
  - Move all OMOP concept maps from individual ETL modules
  - **Test**: Run `pytest tests/test_etl*.py`

- [ ] **2.3** Extract connector concept mappings (saves ~200 lines)
  - Create `app/connectors/concept_mappings.py`
  - Move shared FHIR/HL7/CCDA mappings
  - **Test**: Run `pytest tests/test_connectors*.py`

- [ ] **2.4** Merge auth overlaps (saves ~300 lines)
  - Consolidate `auth.py`, `security.py`, `tenant.py`
  - Single `app/core/security.py`
  - **Test**: Run `pytest tests/test_auth*.py tests/test_security*.py`

### Schema Consolidation
- [ ] **2.5** Merge Create/Response schema duplicates (saves ~40% schema lines)
  - Use single models with optional `id` field
  - **Test**: Run full test suite

- [ ] **2.6** Consolidate X12 provider types (saves ~210 lines)
  - Create single `X12Entity(role: Enum)` model
  - **Test**: Run `pytest tests/test_x12*.py`

- [ ] **2.7** Remove PolicyRule redundancy (saves ~100 lines)
  - Delete PolicyRule, compute views on demand
  - **Test**: Run `pytest tests/test_policy*.py`

---

## 🔴 TIER 3: High-Risk Logic Restructures

### Data-Driven Refactors
- [ ] **3.1** Convert `clinical_calculators.py` to data-driven (5,068 → ~800 lines)
  - Create `calculators.json` for all calculator definitions
  - Generic `Calculator` class that reads from JSON
  - Preserve all 445 formulas as data
  - **Test**: Run `pytest tests/test_calculators*.py` + manual QA

- [ ] **3.2** Create generic OMOP `ConceptReference` (saves ~300 lines)
  - Replace repeated `concept_id + source_value + source_concept_id` pattern
  - **Test**: Run `pytest tests/test_omop*.py`

- [ ] **3.3** Consolidate duplicate Input classes in calculator service (saves ~200 lines)
  - Create generic `CalculatorInput` with optional fields
  - **Test**: Run `pytest tests/test_calculator*.py`

---

## Progress Tracking

| Tier | Tasks | Completed | Lines Saved |
|------|-------|-----------|-------------|
| 🟢 Tier 1 | 8 | 0 | 0 |
| 🟡 Tier 2 | 7 | 0 | 0 |
| 🔴 Tier 3 | 3 | 0 | 0 |
| **Total** | **18** | **0** | **0** |

**Estimated Total Savings**: ~12,000+ lines

---

## Execution Order

1. Run baseline tests, record pass count
2. Execute Tier 1 (1.1 → 1.8) sequentially
3. Run tests after each task
4. Execute Tier 2 (2.1 → 2.7) sequentially
5. Run tests after each task
6. Execute Tier 3 (3.1 → 3.3) with extra caution
7. Final test run + manual QA

---

## Test Commands

```bash
# Full backend test
cd backend && python3 -m pytest tests/ --ignore=tests/test_neo4j_temporal_service.py -q

# Full frontend test
cd frontend && npm test -- --watchAll=false

# Specific module test
python3 -m pytest tests/test_documents*.py -v

# Quick smoke test
python3 -m pytest tests/ -m "unit or smoke" -q --tb=line
```

---

## Notes

- Another agent is working on knowledge_graph - coordinate before touching those files
- Commit after each successful task
- If tests fail, revert immediately
