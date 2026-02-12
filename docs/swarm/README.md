# Swarm Audit Workspace

Persistent workspace for the 12-hour code-understanding swarm.

## Files

- `SWARM_CHARTER_2026-02-10.md`: mission, scope, workstreams, success criteria.
- `SWARM_LOC_BASELINE_2026-02-10.md`: LOC and endpoint baseline snapshot.
- `SWARM_AUTH_SEMANTICS_2026-02-10.md`: endpoint auth semantic audit.
- `SWARM_SERVICE_TAXONOMY_2026-02-10.md`: service-layer classification and hotspots.
- `SWARM_PIPELINE_TRACE_2026-02-10.md`: document->fact->graph execution trace.
- `SWARM_PHARMA_MODULE_QUALITY_MATRIX_2026-02-10.md`: batch 28-32 module quality matrix.
- `SWARM_UNAUTH_MODULES_DEEPDIVE_2026-02-10.md`: deep read of high-exposure unauth modules.
- `SWARM_PIPELINE_IDEMPOTENCY_ANALYSIS_2026-02-10.md`: retry/idempotency analysis for document pipeline.
- `SWARM_BILLION_DOLLAR_ORG_REVIEW_2026-02-10.md`: executive + engineering multi-role operating review.
- `SWARM_FINDINGS.md`: consolidated findings and risk hypotheses.
- `SWARM_PROGRESS_LOG.md`: timestamped execution checkpoints.
- `SWARM_MEMORY.md`: concise handoff/resume memory.
- `SWARM_STATE_2026-02-10.json`: machine-readable project state.
- `data/`: raw snapshot artifacts (TSV/JSON).

## Resume Protocol

1. Read `SWARM_MEMORY.md`.
2. Read latest entry in `SWARM_PROGRESS_LOG.md`.
3. Open `SWARM_LOC_BASELINE_2026-02-10.md` and `SWARM_FINDINGS.md`.
4. Continue pending items from `SWARM_CHARTER_2026-02-10.md`.
