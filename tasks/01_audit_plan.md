# Audit Plan 01: NLP Workbench → Hybrid Reasoner → KG → QA

## Goal (MVP)
Make the NLP Workbench extraction achieve near-complete word coverage and flow into the Hybrid Reasoner → Knowledge Graph → Q&A path.

## Scope
- Primary UI: NLP Workbench (clinical extraction)
- Backend pipeline: Document → Mention → Mapping → ClinicalFact → KG → QA
- Focus on the *actual* paths used by the UI today

## Coverage Metric (MVP)
- Define coverage as: extracted token/word count ÷ total token/word count
- Target: 95–100% coverage OR explicit “skipped” classes with reasons
- Output must include “missing span” list + reason category (e.g., boilerplate, stopword, formatting noise, non-medical)

## Deliverables
1) Canonical extraction entrypoint(s) used by the UI
2) Coverage gap analysis (what is missed and why)
3) Wiring audit (what connects end‑to‑end vs what is orphaned)
4) Prioritized fix list (max 8 items)

## Success Criteria
- One clear, canonical pipeline for the NLP Workbench
- Measurable extraction coverage with gap explanations
- Verified path from Mentions to KG to QA

## Constraints
- None (refactors and schema changes allowed)

## Phases
1) Inventory: locate UI entry, API endpoints, and services used
2) Coverage: measure where extraction fails or filters content
3) Coherence: check mapping → facts → KG → QA flow
4) Unify: recommend canonical path and deprecate/merge alternates
