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

## Phase 1: Load OMOP Relationships (Data Layer)

**Goal:** Populate concept_relationships table with clinical relationships

### Tasks

- [ ] **1.1** Run relationship loader script
  ```bash
  python -m app.scripts.load_concept_relationships \
    --path backend/data/athena_vocab/ \
    --relationships "May treat,May be treated by,CI to,CI by,Has drug-drug inter"
  ```

- [ ] **1.2** Verify relationship counts
  ```sql
  SELECT relationship_id, COUNT(*)
  FROM concept_relationships
  GROUP BY relationship_id;
  ```
  Expected: ~67K "May treat", ~40K "CI to", ~21K "Drug-drug inter"

- [ ] **1.3** Add database indexes for fast lookup
  ```sql
  CREATE INDEX idx_concept_rel_lookup
  ON concept_relationships(concept_id_1, concept_id_2);
  ```

- [ ] **1.4** Create migration for indexes (035_add_relationship_indexes.py)

### Success Criteria
- [ ] concept_relationships table has >100K rows
- [ ] Query `WHERE concept_id_1=X AND concept_id_2=Y` returns in <10ms

### Rollback
- DELETE FROM concept_relationships; (data only, no code changes)

---

## Phase 2: Entity-to-Concept Mapping (NLP Layer)

**Goal:** Extract entities with OMOP concept_ids populated

### Tasks

- [ ] **2.1** Add feature flag
  ```python
  # settings.py
  ENABLE_CONCEPT_MAPPING = os.getenv("ENABLE_CONCEPT_MAPPING", "false") == "true"
  ```

- [ ] **2.2** Create concept lookup service
  ```python
  # app/services/concept_lookup.py
  async def lookup_concept(text: str, domain: str) -> int | None:
      """Find best matching OMOP concept_id for extracted text."""
      # 1. Exact match on concept_name
      # 2. Fuzzy match on concept_synonyms
      # 3. Semantic similarity (embeddings) if needed
  ```

- [ ] **2.3** Integrate into NLP extraction
  - Modify `nlp_rule_based.py` to call concept_lookup
  - Modify `nlp_ensemble.py` (hybrid) to call concept_lookup

- [ ] **2.4** Add caching layer (Redis)
  - Cache concept lookups: `concept:metformin` → `1503297`
  - TTL: 24 hours (concepts don't change often)

- [ ] **2.5** Add UI indicator
  - Show "OMOP Mapped: ✓" in entity details when concept_id present

### Success Criteria
- [ ] >80% of extracted entities have non-null omop_concept_id
- [ ] Lookup latency <50ms per entity (with caching)

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
