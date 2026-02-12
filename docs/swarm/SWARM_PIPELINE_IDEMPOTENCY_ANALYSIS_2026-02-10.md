# Pipeline Idempotency and Retry Analysis (2026-02-10)

## Scope
Idempotency and retry behavior analysis for `process_document`:
- `backend/app/jobs/document_processing.py:101`

Supporting model/service anchors:
- `backend/app/models/document.py:22`
- `backend/app/models/mention.py:13`
- `backend/app/models/clinical_fact.py:16`
- `backend/app/services/fact_builder.py:210`
- `backend/app/services/fact_builder_db.py:62`
- `backend/app/services/graph_builder_db.py:330`

## Execution Characteristics
1. Job updates document status to `PROCESSING` and commits early:
- `backend/app/jobs/document_processing.py:121`
- `backend/app/jobs/document_processing.py:127`

2. Mentions are inserted per run with new UUIDs:
- `backend/app/jobs/document_processing.py:158`
- `backend/app/jobs/document_processing.py:160`

3. Concept candidates are inserted per mention (per run):
- `backend/app/jobs/document_processing.py:197`

4. Fact creation uses dedup key at service level:
- Dedup dimensions: `patient_id + concept + assertion + temporality + experiencer`
  - `backend/app/services/fact_builder.py:210`
  - `backend/app/services/fact_builder.py:233`
- DB lookup-based dedup:
  - `backend/app/services/fact_builder_db.py:151`

5. Graph projection reuses dedup behavior for nodes/edges:
- `backend/app/services/graph_builder_db.py:112`
- `backend/app/services/graph_builder_db.py:160`

## Idempotency Assessment
### What is idempotent-ish
- `ClinicalFact` creation is logically deduplicated by fact key, so retries should usually reuse existing fact rows instead of creating duplicates.
- KG node/edge projection has dedup checks before insert, reducing graph duplication risk.

### What is not idempotent
- `Mention` rows are not deduplicated at document-span level (no uniqueness guard on `(document_id, start_offset, end_offset, text)` in model).
- `MentionConceptCandidate` rows are rebuilt per new mention set on every run.
- Fact evidence may still accumulate across retries because each retry creates new mention IDs, and evidence dedup checks `(fact_id, source_id, source_table)` only.

## Concurrency / Retry Risks
1. Duplicate processing race:
- No optimistic or pessimistic lock guard to prevent concurrent workers from processing the same document simultaneously.
- Status update to `PROCESSING` does not enforce single-consumer execution.

2. Data amplification risk:
- Reprocessing the same document can increase mention/candidate volume without increasing semantic fact count.
- This can bloat storage and provenance tables over time.

3. Partial-failure consistency:
- Graph build failure is tolerated and processing still completes (`document_processing.py:291`), creating temporary divergence between fact tables and graph mirrors.

4. Queue failure asymmetry:
- Upload can persist document even when enqueue fails (`documents_core.py:163` from pipeline trace), creating queued-but-never-processed rows unless remediated.

## Existing Test Coverage Signal
- Job tests exist (`backend/tests/test_jobs.py`), but explicit idempotency/retry-contract tests were not detected for duplicate execution semantics.

## Recommendations
1. Add idempotency key strategy for mention extraction outputs:
- Use deterministic mention identity (e.g., hash of `document_id + span + normalized_text + assertion/temporality/experiencer`).

2. Add processing lock/guard:
- Use status transition precondition (`QUEUED -> PROCESSING`) with affected-row check, or advisory lock per `document_id`.

3. Add retry-safe cleanup strategy:
- On reprocess, either soft-delete prior mentions/candidates for document or version them explicitly.

4. Add contract tests:
- Re-run `process_document` twice on same input and assert bounded growth of mentions/candidates/facts/edges under chosen policy.

5. Add drift telemetry:
- Emit counters for “reprocessed document”, “mentions added on retry”, “facts merged vs created”, “graph sync skipped/failed”.
