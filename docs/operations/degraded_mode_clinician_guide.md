# Degraded Mode Operations Guide for Clinicians

**Document ID**: USR-P3-022
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Product + Clinical Operations
**Classification**: Internal — User Documentation

## What Is Degraded Mode?

The platform enters degraded mode when one or more backend services are unavailable or performing below normal. During degraded mode, some features may be limited or unavailable to protect clinical accuracy.

## How You'll Know

An amber banner appears at the top of the screen:

> **System Operating in Degraded Mode** — Some features may be unavailable or show reduced accuracy. Clinical decisions should be verified through standard clinical processes.

## What Changes in Degraded Mode

### Available with Limitations

| Feature | Normal Mode | Degraded Mode |
|---|---|---|
| Patient chart view | Full | Read-only, may be stale |
| Problem list | Auto-extracted + coded | Static (last successful extraction) |
| Medication list | Auto-extracted + coded | Static |
| Clinical Q&A | AI-powered with citations | Unavailable or limited to stored results |
| Drug interactions | Real-time check | May show "check unavailable" |
| Clinical calculators | Full functionality | May use cached inputs |

### Unavailable in Degraded Mode

- New document ingestion
- New NLP extractions
- Knowledge graph queries
- GraphRAG-powered answers
- Export to FHIR/OpenEHR (real-time)

### Always Available

- Previously extracted clinical facts
- Static patient demographics
- Audit trail viewing
- Document viewing (already uploaded)
- Support contact

## What You Should Do

### During Degraded Mode

1. **Do not** rely on automated clinical decision support for new decisions
2. **Do** verify any AI-generated content through standard clinical processes
3. **Do** check medication interactions through your facility's standard process
4. **Do** document any clinical decisions made during degraded mode
5. **Do** report any suspicious results to your supervisor

### When You See "Low Confidence" Badges

Results marked with a low confidence badge should be treated as suggestions only:
- Verify against source documentation
- Cross-reference with patient history
- Use clinical judgment as primary guide
- Report any apparent errors via feedback button

### When Drug Interaction Check Is Unavailable

If the drug interaction checker shows "check unavailable":
- Use your facility's standard drug reference (e.g., Lexicomp, Micromedex)
- Do not assume absence of warning means no interaction
- Report the outage to your supervisor if it persists

## When Does Degraded Mode End?

Degraded mode resolves automatically when backend services recover. The amber banner will disappear and you'll see a green notification:

> **System Fully Operational** — All features have been restored.

You do not need to refresh the page — the system updates automatically.

## Getting Help

| Need | Action |
|---|---|
| Technical support | Slack #clinical-support or email support@sulci.ai |
| Urgent clinical concern | Call Clinical Safety Lead directly |
| Report an error | Use the feedback button on any result card |
| System status | Check the status page (link in footer) |

## Training

All clinicians using the platform receive training on:
- Recognizing degraded mode indicators
- Understanding confidence badges and their meaning
- Standard fallback procedures when AI features are unavailable
- How and when to escalate concerns
