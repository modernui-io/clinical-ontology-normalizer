# Ontology-Based Entity Relationships - Implementation Plan

**Branch:** `feature/ontology-relationships`
**Base:** `master` @ commit `5c5ba23`
**Created:** 2026-02-04

## Overview

Replace hardcoded drug→condition mappings with systematic ontology-based relationships using OMOP/UMLS vocabularies. This enables any medical entity to be connected based on 5.36M concepts and 67K+ relationships.

## Current State (main branch)

- ✅ Entity-to-entity edges working (hardcoded mappings)
- ✅ Connections panel shows related entities
- ✅ Provenance shows extraction method/confidence
- ⚠️ Relationships based on ~100 hardcoded drug→condition rules
- ❌ No OMOP concept_id mapping on entities (all NULL)
- ❌ No ontology relationship lookup
- ❌ No temporal date extraction from text

## Target State

- Entity extraction maps text → OMOP concept_id
- Relationships come from OMOP concept_relationships table
- 67K+ "May treat" relationships available
- Temporal dates extracted from clinical context
- Feature flags for gradual rollout

---

## Phase 1: Load OMOP Relationships (Data Layer) ✅ COMPLETE

**Goal:** Populate concept_relationships table with clinical relationships

### Tasks

- [x] **1.1** Run relationship loader script ✅ (2026-02-04)
  - Loaded 260,018 clinical relationships
  - Added 417,986 mapping relationships (Maps to/Mapped from)

- [x] **1.2** Verify relationship counts ✅
  ```
  May treat: 67,463
  May be treated by: 67,463
  CI to: 40,884
  CI by: 40,884
  Drug-drug inter for: 21,662
  Has drug-drug inter: 21,662
  Maps to: 208,993
  Mapped from: 208,993
  TOTAL: 678,004 relationships
  ```

- [x] **1.3** Indexes already exist from migration 014 ✅

- [x] **1.4** Migration 014 already includes indexes ✅

### Success Criteria
- [x] concept_relationships table has >100K rows (678K) ✅
- [x] Query performance <10ms (measured 0.258ms) ✅

### Rollback
- DELETE FROM concept_relationships; (data only, no code changes)

---

## Phase 2: Entity-to-Concept Mapping (NLP Layer) ✅ COMPLETE

**Goal:** Extract entities with OMOP concept_ids populated

### Tasks

- [x] **2.1** Add feature flags to config.py ✅ (2026-02-04)
  - ENABLE_CONCEPT_MAPPING, USE_ONTOLOGY_EDGES, ENABLE_TEMPORAL_EXTRACTION
  - Added to docker-compose.yml backend environment

- [x] **2.2** Create concept lookup service ✅
  - Created `app/services/concept_lookup.py`
  - Exact match lookup with vocabulary prioritization
  - NDFRT prioritized for drugs (contains "May treat" relationships)
      """Find best matching OMOP concept_id for extracted text."""
      # 1. Exact match on concept_name
      # 2. Fuzzy match on concept_synonyms
      # 3. Semantic similarity (embeddings) if needed
  ```

- [x] **2.3** Integrate into graph builder ✅
  - Added concept lookup in `clinical_agent.py` `_build_patient_knowledge_graph()`
  - Uses savepoints to isolate lookup errors from main transaction

- [ ] **2.4** Add caching layer (Redis) - DEFERRED
  - Currently using simple in-memory cache in concept_lookup.py
  - Redis integration can be added for production scale

- [ ] **2.5** Add UI indicator - DEFERRED
  - Backend populates omop_concept_id on nodes
  - Frontend can show indicator (future task)

### Success Criteria
- [x] Entities with exact NDFRT matches get concept_id ✅
  - "Metformin" → 4274535 (NDFRT)
  - "Diabetes Mellitus, Type 2" → 4341452 (NDFRT)
- [x] OMOP relationship edges created from concept_relationships ✅
  - drug_treats edge with source=omop_concept_relationship

### Rollback
- Set `ENABLE_CONCEPT_MAPPING=false`

---

## Phase 3: Ontology-Based Edge Creation (Graph Layer)

**Goal:** Create entity-to-entity edges from ontology relationships

### Tasks

- [ ] **3.1** Add feature flag
  ```python
  USE_ONTOLOGY_EDGES = os.getenv("USE_ONTOLOGY_EDGES", "false") == "true"
  ```

- [ ] **3.2** Enhance `_query_omop_relationships()` function
  - Current: Basic query (already implemented)
  - Add: Batch lookups for performance
  - Add: Cache frequently accessed relationships

- [ ] **3.3** Update graph builder logic
  ```python
  if settings.USE_ONTOLOGY_EDGES and entity_concept_ids:
      edges = await _query_omop_relationships(db, entity_concept_ids)
  else:
      edges = _apply_hardcoded_treatment_map(entities)  # Fallback
  ```

- [ ] **3.4** Map OMOP relationship_id to EdgeType
  ```python
  OMOP_TO_EDGE_TYPE = {
      "May treat": EdgeType.DRUG_TREATS,
      "May be treated by": EdgeType.CONDITION_TREATED_BY,
      "CI to": EdgeType.CONTRAINDICATED_WITH,
      "Has drug-drug inter": EdgeType.DRUG_INTERACTION,
  }
  ```

- [ ] **3.5** Add edge metadata
  - `source: "omop"` vs `source: "heuristic"`
  - `relationship_id: "May treat"`
  - `omop_concept_id_1`, `omop_concept_id_2`

- [ ] **3.6** Remove/deprecate hardcoded treatment_map
  - Keep as fallback initially
  - Remove after validation

### Success Criteria
- [ ] Edges show `source: "omop"` in properties
- [ ] Edge count comparable to hardcoded (within 20%)
- [ ] No regression in existing connections

### Rollback
- Set `USE_ONTOLOGY_EDGES=false` (uses hardcoded mappings)

---

## Phase 4: Temporal Extraction (NLP Layer)

**Goal:** Extract dates from clinical context and populate event_date

### Tasks

- [ ] **4.1** Add feature flag
  ```python
  ENABLE_TEMPORAL_EXTRACTION = os.getenv("ENABLE_TEMPORAL_EXTRACTION", "false") == "true"
  ```

- [ ] **4.2** Create temporal extraction patterns
  ```python
  TEMPORAL_PATTERNS = [
      r"started (\w+) on (\d{1,2}/\d{1,2}/\d{4})",
      r"diagnosed with (\w+) in (\d{4})",
      r"(\w+) since (\w+ \d{4})",
      # ... more patterns
  ]
  ```

- [ ] **4.3** Integrate into NLP extraction
  - Extract dates in context window around entity
  - Associate date with entity as `event_date`

- [ ] **4.4** Update graph builder
  - Populate `event_date` on edges
  - Calculate `temporal_order` between related entities

- [ ] **4.5** Update UI
  - Show temporal slider with actual dates
  - Display "started after diagnosis" on drug→condition edges

### Success Criteria
- [ ] >30% of entities have event_date populated
- [ ] Temporal slider shows date range from data
- [ ] Drug→Condition edges show temporal ordering

### Rollback
- Set `ENABLE_TEMPORAL_EXTRACTION=false`

---

## Testing Strategy

### Baseline Metrics (capture before changes)
```bash
# Run on current main branch
curl -s "http://localhost:8080/api/v1/clinical-agent/graph/TEST55555" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Nodes: {len(d[\"nodes\"])}, Edges: {len(d[\"edges\"])}')"
```

### Comparison Testing
- [ ] Create `test_ontology_relationships.py`
- [ ] Compare edge counts: hardcoded vs ontology
- [ ] Validate specific relationships (metformin→diabetes should exist)
- [ ] Performance benchmarks (graph build time)

### Validation Endpoint
- [ ] Add `/api/v1/clinical-agent/validate-graph/{patient_id}`
  - Returns comparison: hardcoded edges vs ontology edges
  - Flags discrepancies for review

---

## Configuration

```bash
# .env additions for feature flags
ENABLE_CONCEPT_MAPPING=false
USE_ONTOLOGY_EDGES=false
ENABLE_TEMPORAL_EXTRACTION=false

# Enable progressively:
# Phase 2: ENABLE_CONCEPT_MAPPING=true
# Phase 3: USE_ONTOLOGY_EDGES=true
# Phase 4: ENABLE_TEMPORAL_EXTRACTION=true
```

---

## Branch Management

### To demo current state (hardcoded mappings):
```bash
git checkout master
docker compose restart backend
# Visit http://localhost:3000/nlp
```

### To work on ontology features:
```bash
git checkout feature/ontology-relationships
docker compose restart backend
```

### To merge when ready:
```bash
git checkout master
git merge feature/ontology-relationships
```

---

## Files to Modify

| Phase | File | Changes |
|-------|------|---------|
| 1 | `backend/app/scripts/load_concept_relationships.py` | Already exists, just run |
| 1 | `backend/alembic/versions/035_*.py` | New migration for indexes |
| 2 | `backend/app/core/settings.py` | Add feature flags |
| 2 | `backend/app/services/concept_lookup.py` | New service |
| 2 | `backend/app/services/nlp_rule_based.py` | Integrate concept lookup |
| 2 | `backend/app/services/nlp_ensemble.py` | Integrate concept lookup |
| 3 | `backend/app/api/clinical_agent.py` | Enhance graph builder |
| 4 | `backend/app/services/temporal_extractor.py` | New service |
| 4 | `backend/app/services/nlp_rule_based.py` | Integrate temporal |

---

## Estimated Effort

| Phase | Complexity | Estimate |
|-------|------------|----------|
| Phase 1 | Low | 1-2 hours (mostly running scripts) |
| Phase 2 | Medium | 4-6 hours (concept lookup + caching) |
| Phase 3 | Medium | 2-4 hours (mostly wiring) |
| Phase 4 | High | 6-8 hours (NLP pattern matching) |

---

## Notes

- Phase 1 can merge to main immediately (no behavior change, just data)
- Phases 2-4 stay on feature branch until validated
- Each phase independently shippable with feature flags
- Keep hardcoded mappings as fallback until Phase 3 is validated
