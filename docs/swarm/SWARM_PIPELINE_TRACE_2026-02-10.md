# Document -> Fact -> Graph Pipeline Trace (2026-02-10)

## Purpose
Trace the primary clinical document processing path end-to-end with concrete code anchors.

## Entry Path (API)
1. Upload endpoint creates document + queued status:
- `backend/app/api/documents/documents_core.py:111`
- `backend/app/api/documents/documents_core.py:118`
- `backend/app/api/documents/documents_core.py:137`

2. Upload endpoint enqueues background job:
- `backend/app/api/documents/documents_core.py:149`
- `backend/app/api/documents/documents_core.py:151`
- Queue name sourced from `QUEUE_NAMES["document"]`:
  - `backend/app/core/queue.py:145`
  - `backend/app/core/queue.py:146`

3. Async DB transaction auto-commit behavior for API dependency:
- `backend/app/core/database.py:218`
- `backend/app/core/database.py:231`

Operational implication:
- Endpoint only flushes (`await db.flush()`), and commit is finalized by `get_db()` dependency after request completion.

## Background Job Path
1. Job function:
- `backend/app/jobs/document_processing.py:101`

2. Job marks document `PROCESSING`:
- `backend/app/jobs/document_processing.py:121`
- `backend/app/jobs/document_processing.py:127`

3. NLP mention extraction:
- Service acquisition: `backend/app/jobs/document_processing.py:144`
- Extraction call: `backend/app/jobs/document_processing.py:145`
- NLP service implementation entry:
  - `backend/app/services/nlp_rule_based.py:46`
  - `backend/app/services/nlp_rule_based.py:274`

4. Mention persistence and direct concept capture:
- Mention creation loop: `backend/app/jobs/document_processing.py:158`
- Direct concept shortcut map: `backend/app/jobs/document_processing.py:177`

5. SQL concept mapping fallback:
- Mapping service creation: `backend/app/jobs/document_processing.py:194`
- Fallback mapping call: `backend/app/jobs/document_processing.py:218`
- SQL mapper core:
  - `backend/app/services/mapping_sql.py:27`
  - `backend/app/services/mapping_sql.py:88`

6. Fact creation from top-ranked concept candidate:
- Fact builder init: `backend/app/jobs/document_processing.py:244`
- Per-mention top candidate query: `backend/app/jobs/document_processing.py:249`
- Fact creation call: `backend/app/jobs/document_processing.py:263`
- Fact builder core:
  - `backend/app/services/fact_builder_db.py:31`
  - `backend/app/services/fact_builder_db.py:62`

7. Graph projection from facts:
- Graph builder init + patient graph build call:
  - `backend/app/jobs/document_processing.py:283`
  - `backend/app/jobs/document_processing.py:284`
- Graph build pipeline:
  - `backend/app/services/graph_builder_db.py:330`
  - Fact iteration/project: `backend/app/services/graph_builder_db.py:359`
  - Neo4j sync call: `backend/app/services/graph_builder_db.py:401`
  - Neo4j graceful-degrade check: `backend/app/services/graph_builder_db.py:433`

8. Completion and cache invalidation:
- Status `COMPLETED`: `backend/app/jobs/document_processing.py:297`
- Commit: `backend/app/jobs/document_processing.py:306`
- KG cache invalidation: `backend/app/jobs/document_processing.py:308`

9. Failure path:
- Exception handler: `backend/app/jobs/document_processing.py:339`
- Status `FAILED` best-effort update: `backend/app/jobs/document_processing.py:343`

## Data Shape Evolution
1. `Document` row (`QUEUED`) at upload.
2. `Mention` rows produced from NLP extraction.
3. `MentionConceptCandidate` rows from direct concept or SQL mapping.
4. `ClinicalFact` + `FactEvidence` via deduplicating fact builder.
5. `KGNode` + `KGEdge` projection.
6. Optional Neo4j mirror update.

## Transaction and Consistency Notes
- API write and queue enqueue happen in same request path but queue enqueue failure does not fail upload (`documents_core.py:158` onward), so documents may persist unprocessed.
- Job performs multiple writes in one sync session with explicit commits at phase boundaries (`document_processing.py:127`, `document_processing.py:306`).
- Graph sync failure does not fail document processing (`document_processing.py:291`), favoring availability over strict downstream consistency.

## High-Risk Boundaries
1. Queue enqueue failure path:
- Document remains `QUEUED` but worker never runs if enqueue fails (`documents_core.py:163`).

2. Mention-to-concept mapping quality:
- Top candidate only is used for fact creation (`document_processing.py:248`), so ranking quality directly controls fact quality.

3. Fact-to-graph partial degradation:
- Neo4j unavailability is tolerated (`graph_builder_db.py:433`), creating split-brain risk between PostgreSQL graph and Neo4j graph consumers.

4. Mixed async/sync DB contexts:
- API uses async sessions; jobs use sync engine/session (`document_processing.py:120`), requiring careful parity in transaction and model behavior.

## Existing Test Anchors
- Job behavior tests: `backend/tests/test_jobs.py`
- API upload/queue tests: `backend/tests/test_api_documents.py`
- Queue utility tests: `backend/tests/test_queue.py`

## Next Deep-Dive Steps
1. Add event-level observability map (timings and counters per phase).
2. Validate idempotency behavior for duplicate `process_document` executions.
3. Trace fact dedup key behavior against realistic negation/temporality edge cases.
