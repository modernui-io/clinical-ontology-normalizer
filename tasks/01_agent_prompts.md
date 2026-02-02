# Agent Prompt Pack 01

These prompts are designed for Codex/Claude multi‑agent runs to audit and unify the NLP Workbench pipeline.

---

## Coordinator Prompt

Task
You are the coordinator for the Clinical Ontology Normalizer audit + unification.
Primary goal: make the NLP Workbench’s extraction pipeline achieve near‑complete word coverage and feed the Hybrid Reasoner → KG → QA path.

Context
- Start with repo maps in CODEBASE_MAP.md and IMPLEMENTATION_PLAN.md.
- Focus on the actual UI route used by the NLP workbench.
- The target pipeline is: Document → Mention → Mapping → ClinicalFact → KG → QA.

Requirements
- Produce a short audit report with:
  1) canonical extraction entrypoint(s)
  2) coverage metric definition + current gaps
  3) what’s wired vs what’s orphaned
  4) prioritized fix list (max 8 items)
- Spawn sub‑agents only for specific slices; avoid full code rewrite.

Success Criteria
- Clear plan to make UI extraction cover most words, and show gaps.
- Clear plan to route extraction results into KG and QA path.

---

## Sub‑Agent: NLP Workbench UI → API Wiring

Task
Trace the NLP workbench UI to the backend endpoints it calls and the pipeline it triggers.

Context
- Look in frontend for NLP workbench route and its API hooks.
- Identify the backend route(s) that process the request and which services are used.

Requirements
- List the UI entry file and the API hook path.
- List the backend endpoint and service functions called.
- Identify any alternate code paths or feature flags.

Success Criteria
- A single, direct mapping from UI action to backend pipeline.

---

## Sub‑Agent: Extraction Coverage Analysis

Task
Find the current NLP extraction pipeline(s) and explain why coverage is low.

Context
- Identify rule‑based vs model‑based extractors in backend/app/services/.
- Determine which extractor(s) are actually used by the UI pipeline.

Requirements
- Describe how mentions are extracted and filtered.
- Identify which tokens/words are skipped, and why.
- Propose a coverage measurement (tokenization method).

Success Criteria
- A concrete list of coverage gap causes + most likely fixes.

---

## Sub‑Agent: Mapping → Facts → KG

Task
Confirm that the pipeline from Mentions to KG is executed for the NLP workbench path.

Context
- Find how MentionConceptCandidate, ClinicalFact, and KG nodes are created.
- Check for missing hooks or short‑circuits.

Requirements
- Trace which service functions are called after extraction.
- Identify which data structures are persisted and where.
- Note any missing edges or incomplete mapping.

Success Criteria
- A clear path showing how extracted text becomes KG nodes for QA.

---

## Sub‑Agent: QA / Hybrid Reasoner Integration

Task
Identify the QA/hybrid reasoner endpoint(s) and required inputs.

Context
- Find QA agent / hybrid reasoning services and their expected inputs.
- Confirm if they use KG, SQL, or both.

Requirements
- List the APIs and dependencies.
- Identify if KG inputs are required but missing in current pipeline.

Success Criteria
- A list of integration steps to enable QA using newly extracted KG facts.

---

## Sub‑Agent: Dead Code / Redundancy Sweep

Task
Identify extraction‑related services or pipelines that are unused or redundant.

Context
- Focus on services in backend/app/services/ that look like extraction or mapping.

Requirements
- List unused or duplicate components.
- Recommend which path to keep as canonical.

Success Criteria
- A short “keep / merge / deprecate” table.
