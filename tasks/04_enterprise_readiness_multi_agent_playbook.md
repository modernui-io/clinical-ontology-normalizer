# Enterprise Readiness Multi-Agent Playbook

Purpose
- Create a deterministic, resumable review workflow for the one-on-one leadership readiness review before pilot go-live.
- Focus: Ramsey Health / Australia, Meditech migration to OpenEHR, with first-mover emphasis on ingestion, ontology normalization, hybrid reasoner, knowledge graph, and Q&A.
- Constraint: this pass is analysis-only. No code changes in this run.

Date Anchors
- Start date for this plan: Friday, February 13, 2026.
- Review date format in output should always be absolute dates (e.g., `2026-02-13`) when talking about timelines.

Use This File as the Canonical Runbook
- Read this file top-to-bottom before starting each execution pass.
- After each role pass, paste the output into the corresponding artifact path.
- Update `SESSION CHECKPOINT` at the end after each step.

## Session Checkpoint (Resume Here)

```yaml
run_id: enterprise-readiness-openehr-pilot-v1
goal: production-readiness_assessment
phase: 4
status: in_progress
current_stage: sprint_1_closed
started_utc: "2026-02-13T00:00:00Z"
last_updated_utc: "2026-02-21T22:00:00Z"
next_stage: staging_provisioning
completed_roles:
  - cto
  - ciso
  - cio
  - vp_product
  - operations
  - clinical_ai
blocked_on: []
open_questions:
  - "What is the target date for OpenEHR adapter contract sign-off by platform and governance leads?"
required_artifacts:
  - tasks/01_audit_plan.md
  - tasks/02_agent_findings.md
  - exec-review/cto-review.md
  - exec-review/cio-review.md
  - exec-review/ciso-review.md
  - exec-review/vp-product-review.md
  - exec-review/operations-review.md
  - tasks/06_clinical_ai_todo_list.md
  - tasks/07_one_on_one_role_pack.md
  - tasks/08_autonomous_execution_board.md
  - tasks/09_master_change_backlog_p0_p4.md
  - tasks/10_execution_roadmap_2026.md
  - tasks/11_p0_p1_sprint_plan_2026_q1.md
  - tasks/12_ticket_seed_backlog_399.csv
  - tasks/12_ticket_seed_backlog_399_README.md
  - tasks/13_roadmap_kpi_operating_scorecard.md
  - tasks/14_risk_dependency_register.md
  - tasks/15_waveA_day_by_day_plan.md
  - tasks/16_sprint1_execution_board.md
  - tasks/17_sprint2_to_sprint6_lists.md
  - tasks/18_waveD_execution_board.md
  - tasks/19_waveE_execution_board.md
  - tasks/20_waveF_execution_board.md
  - tasks/21_waveG_post_wave_closeout_plan.md
  - tasks/22_waveG_execution_board.md
  - tasks/23_waveG_week_by_week_board.md
  - tasks/24_waveG_daily_owner_tracker.csv
  - docs/agent_context_health_graph.md
  - CODEBASE_MAP.md
  - AGENT_PROMPT_TEMPLATE.md
```

## Run Log (Update)
- 2026-02-13: CTO pass completed in `exec-review/cto-review.md`.
- 2026-02-13: CISO pass completed in `exec-review/ciso-review.md`.
- 2026-02-13: CIO pass completed in `exec-review/cio-review.md`.
- 2026-02-13: Pilot readiness TODO list created in `tasks/05_pilot_todo_list.md`.
- 2026-02-13: VP Product pass completed in `exec-review/vp-product-review.md`.
- 2026-02-13: Operations pass completed in `exec-review/operations-review.md`.
- 2026-02-13: Clinical AI TODO list created in `tasks/06_clinical_ai_todo_list.md`.
- 2026-02-13: One-on-one rapid role answer pack created in `tasks/07_one_on_one_role_pack.md`.
- 2026-02-13: Autonomous execution board created in `tasks/08_autonomous_execution_board.md`.
- 2026-02-13: Master P0-P4 change backlog created in `tasks/09_master_change_backlog_p0_p4.md`.
- 2026-02-13: Execution roadmap with milestone calendar created in `tasks/10_execution_roadmap_2026.md`.
- 2026-02-13: P0/P1 sprint-level execution plan created in `tasks/11_p0_p1_sprint_plan_2026_q1.md`.
- 2026-02-13: Ticket seed backlog (399 subtasks) created in `tasks/12_ticket_seed_backlog_399.csv`.
- 2026-02-13: KPI scorecard created in `tasks/13_roadmap_kpi_operating_scorecard.md`.
- 2026-02-13: Risk/dependency register created in `tasks/14_risk_dependency_register.md`.
- 2026-02-13: Wave A day-by-day execution plan created in `tasks/15_waveA_day_by_day_plan.md`.
- 2026-02-13: Sprint 1 execution board generated from ticket seed in `tasks/16_sprint1_execution_board.md`.
- 2026-02-13: Sprint 2-6 execution lists generated in `tasks/17_sprint2_to_sprint6_lists.md`.
- 2026-02-13: Wave D execution board generated in `tasks/18_waveD_execution_board.md`.
- 2026-02-13: Wave E execution board generated in `tasks/19_waveE_execution_board.md`.
- 2026-02-13: Wave F execution board generated in `tasks/20_waveF_execution_board.md`.
- 2026-02-14: Wave G post-wave closeout plan generated in `tasks/21_waveG_post_wave_closeout_plan.md`.
- 2026-02-14: Wave G execution board generated in `tasks/22_waveG_execution_board.md`.
- 2026-02-14: Wave G week-by-week board generated in `tasks/23_waveG_week_by_week_board.md`.
- 2026-02-14: Wave G daily owner tracker generated in `tasks/24_waveG_daily_owner_tracker.csv`.
- 2026-02-13: Clinical AI closure snapshot completed; next stage is implementation gating pending approval.

Execution Rules
- No code edits in this phase.
- No external vendor/product decisions. Only evidence from repository and this environment.
- Keep all outputs non-cookie-cutter: include concrete file references and explicit tradeoffs.
- Every finding must include severity and owner role.
- Every finding should include an exit condition for pilot readiness.

Output Artifact Map
- `tasks/04_enterprise_readiness_multi_agent_playbook_run.md` (full stitched report)
- `exec-review/cto-review.md` (CTO pass)
- `exec-review/cio-review.md` (CIO pass)
- `exec-review/ciso-review.md` (CISO pass)
- `exec-review/vp-product-review.md` (VP Product pass)
- `exec-review/clinical-ai-review.md` (Clinical AI / model pass)
- `exec-review/operations-review.md` (SRE / Ops pass)

## Master Prompts (Copy/Paste Style)

### 1) Orchestrator Prompt

You are the orchestrator for a leadership-level production-readiness review.

Primary objective
- Build a go/no-go recommendation for a Ramsey Health Australia pilot using OpenEHR as the canonical exchange format.
- Confirm whether the current system should proceed to pilot under controlled conditions.

Scope
- Ingestion and source connectors
- Clinical ontology normalizer and normalization confidence
- Hybrid reasoner and knowledge graph
- Q&A workflow and grounding behavior
- UMLS/OMOP fidelity
- Authentication, authorization, audit, and operational safety

Context
- Use repository evidence first from these paths:
  - `docs/agent_context_health_graph.md`
  - `CODEBASE_MAP.md`
  - `backend/app/api/`
  - `backend/app/services/`
  - `backend/app/core/`
  - `backend/app/models/`
  - `backend/tests/`
  - `exec-review/`

Constraints
- Do not propose code changes in this phase.
- Do not rewrite architecture.
- Avoid speculation. Mark each assumption and the confidence level (high/med/low).

What to produce
1. Executive verdict: proceed, controlled proceed, or hold.
2. Hard blockers (P0/P1) by owner.
3. A ranked risks list with severity and likelihood.
4. 30/60/90 day fix roadmap with explicit owners.
5. Pilot go/no-go checklist with evidence-ready acceptance thresholds.

### 2) CTO Prompt

You are the CTO conducting a production-readiness audit focused on architecture, platform stability, and integrability.

Task
- Review codebase evidence for technical feasibility and risk before pilot sign-off.

Scope
- Ingestion APIs/connectors, pipeline orchestration, service topology, scaling path, observability, DR/backup assumptions.
- OpenEHR transition assumptions for routing and FHIR parity from Meditech context.

Requirements
- Keep findings scoped to what is actually implemented now.
- Produce findings with:
  - Evidence file and symbol (exact file path and function/class name)
  - Severity (P0/P1/P2/P3)
  - Likelihood (high/med/low)
  - Clinical impact
  - Pilot risk statement
  - Dependency or blocker to OpenEHR execution
- Output format must include:
  1) top 10 risks
  2) quick wins (1-4) that can be done before pilot
  3) what must be tested before opening to clinical users

### 3) CIO Prompt

You are the CIO assessing governance, enterprise readiness, workflow adoption, and data strategy.

Task
- Evaluate how this system will operate inside a health system with governance and operational expectations.

Scope
- Integration with enterprise data domains, onboarding, operating model, support model, SLAs, and value signals.

Requirements
- Focus on pilot success criteria and enterprise adoption risk.
- Include only evidence-backed statements.
- For each finding, provide:
  - Evidence reference
  - Severity (P0/P1/P2/P3)
  - Clinical/operational impact
  - Required decision owner (Leadership, Product, Clinical, Operations)
- Produce:
  1) pilot acceptance thresholds for workflow
  2) staffing and support model assumptions
  3) escalation and incident ownership path
  4) data governance and retention controls checklist

### 4) CISO Prompt

You are the CISO running a pre-pilot cyber-risk and compliance pass.

Task
- Identify security and compliance blockers against healthcare-grade launch.

Scope
- AuthN/AuthZ, secrets, PHI boundary, least privilege, encryption, auditability, logging, secrets lifecycle.
- LLM/model/data provider trust boundaries, especially around inference and external dependency chains.

Requirements
- Include explicit mapping to controls where possible (HIPAA-like expectations, NIST/ISO-aligned control language, local AUS healthcare expectation language if known).
- For each finding include:
  - Severity (P0/P1/P2/P3)
  - Affected data/asset
  - Exploitability / likelihood
  - Evidence path
  - Required control gap and owner
- Distinguish between:
  - Hard stop blockers
  - Hardening items that can proceed in parallel

### 5) VP Product Prompt

You are the VP Product defining go/no-go boundaries for pilot usability, reliability, and value communication.

Task
- Convert technical findings into pilot-safe product outcomes and user-level risk controls.

Scope
- UI path quality, missing workflows, hallucination/reliability guardrails, explainability, fallback to clinician behavior.

Requirements
- Build a matrix of user journeys where `77%` accuracy can be acceptable versus where it is unacceptable.
- For each critical workflow produce:
  - Success condition for pilot
  - Confidence threshold behavior
  - Escalation-to-human rule
  - UX warning strategy when confidence is low

### 6) Clinical AI Prompt

You are Clinical AI Lead evaluating model and reasoning reliability.

Task
- Evaluate the inference stack from ontology normalization to Q&A with safety-first perspective.

Scope
- UMLS / OMOP mapping quality, ontology coverage, hybrid reasoner quality, evidence grounding, and clinical safety boundaries.

Requirements
- Provide per-module reliability rating: extraction, normalization, graphing, reasoning, QA output.
- Identify exact failure modes where wrongness is high but confidence may be falsely high.
- For each risk, map to a concrete workflow control (e.g., auto-block, warning, clinician review).

### 7) SRE/Operations Prompt

You are the SRE leadership representative assessing operational reliability.

Task
- Verify operational resilience for pilot launch readiness.

Scope
- Uptime targets, backup/recovery assumptions, queue behavior, monitoring coverage, deployment and rollback controls.

Requirements
- Use explicit SLO language with metrics and acceptance thresholds:
  - Ingestion latency
  - KG freshness
  - QA response time
  - Error rate
  - Escalation time-to-response
- Return:
  1) minimal viable operational runbook (day 0, day 7, day 30)
  2) readiness checklist for one-on-one review.

## Shared Output Schema (for every role)

### Required fields per finding
1. Finding ID
2. Severity (P0/P1/P2/P3)
3. Likelihood (High/Med/Low)
4. Evidence (file path, function/class, and line anchor if available)
5. Business/clinical impact
6. Risk (what can go wrong)
7. Recommendation (no code changes in this pass)
8. Owner role
9. Pilot impact (go / controlled go / hold)

### Required final sections
1. Role-specific go/no-go summary
2. Top 3 blockers
3. Top 3 “can ship with guardrails” items
4. Explicit assumptions list
5. Open questions to resolve before final decision

## Monthly Orchestration Plan

### Week 1
- Run Orchestrator, CTO, CISO, and Clinical AI passes.
- Consolidate cross-cutting blockers and resolve factual inconsistencies.
- Produce week-1 checkpoint artifact: `exec-review/cto-review.md` and `exec-review/ciso-review.md`.

### Week 2
- Run CIO, VP Product, and SRE/Operations passes.
- Build user/workflow pilot-risk matrix.
- Produce one consolidated blocker register in `tasks/04_enterprise_readiness_multi_agent_playbook_run.md`.

### Week 3
- Run adversarial pass:
  - challenge each owner to prove critical assumptions with evidence or mark as unresolved risk.
- Resolve conflicts, duplicate findings, and priority mismatches.
- Draft pilot-ready thresholds by module.

### Week 4
- Final arbitration pass: output single decision packet.
- Provide 90-day roadmap in the same packet:
  - month 1 must-fix
  - month 2 confidence hardening
  - month 3 scale/sustainability
- Finalize go/no-go with clear sign-off criteria and required owners.

Conflict Resolution Rule
- If two roles disagree on severity, keep the highest severity unless explicitly contradicted by strong evidence.
- Any unresolved conflict moves to P1 by default until validated by explicit owner.

Acceptance Rule for this review cycle
- Pilot goes to constrained clinical rollout only if:
  - No unresolved P0 issues
  - All P1 issues have mitigation owners and measurable controls
  - Fallback path is explicitly documented for every 77% confidence surface
  - Evidence trail exists for all major claims

## Pause and Resume Checklist

Before switching session:
- Save role artifacts.
- Update `SESSION CHECKPOINT`:
  - `status`
  - `current_stage`
  - `completed_roles`
  - `blocked_on`
  - `last_updated_utc`
- Add one-line summary of what is done and what is unresolved at the end of the run file.

When resuming:
- Open `tasks/04_enterprise_readiness_multi_agent_playbook.md`.
- Read `SESSION CHECKPOINT` and continue at `current_stage`.
- Verify artifacts in `required_artifacts` before continuing.
