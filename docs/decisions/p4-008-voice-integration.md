# P4-008-D: Ambient Voice/Documentation Integration Decision

**Decision ID:** P4-008-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Product + Clinical AI
**Risk Owner:** Product
**Evidence Owner:** Clinical AI

## Context

Voice transcription scaffold exists at `backend/app/services/voice_transcription_service.py` (563 lines):

- `TranscriptionStatus` enum: pending, processing, completed, failed
- `AudioFormat` enum: wav, mp3, m4a, ogg, webm, flac
- `TranscriptionSegment` with timing (start_time, end_time, confidence)
- Designed for Whisper-compatible speech-to-text services

**Current maturity:** Scaffold only. No audio processing pipeline, no STT integration, no clinical note structuring from voice.

## Decision

**Separate product track. Do NOT integrate voice into clinical ontology normalizer pilot.**

### Business Case Analysis

| Factor | Assessment |
|--------|-----------|
| Market demand | High (ambient documentation is top clinician request) |
| Build vs. buy | Buy preferred — Whisper API, Azure Speech, Google STT are commodity |
| PHI handling for audio | Complex — audio recordings are PHI, require additional consent and storage controls |
| Accuracy requirements | Medical WER must be <5% for clinical safety (general Whisper: ~8% WER) |
| Integration complexity | High — requires audio pipeline, speaker diarization, clinical note structuring, review workflow |
| Pilot relevance | None — Ramsey Health pilot focuses on structured data normalization, not dictation |

### Recommended Path (When Activated)

1. **Phase 1 (Month 1-2):** Evaluate STT providers for medical accuracy
   - Benchmark: Whisper large-v3, Azure Speech (medical custom), Google Medical STT
   - Test corpus: 100 clinical encounters (diverse specialties)
   - Target: <5% WER on medical terminology
2. **Phase 2 (Month 3-4):** Build audio ingestion pipeline with consent management
   - Extend `voice_transcription_service.py` with real STT integration
   - Add PHI-specific audio storage and retention policies
3. **Phase 3 (Month 5-6):** Clinical note structuring from transcripts
   - Map transcript segments to structured clinical data
   - Feed into existing NLP extraction pipeline
4. **Phase 4 (Month 7-8):** Clinician review and correction workflow
   - Review UI with segment-level confidence display
   - Correction feedback loop for model improvement

### PHI Handling Strategy for Audio

- Audio files classified as PHI (contain patient identifiers in speech)
- Separate storage tier with encryption-at-rest and access audit
- Retention policy aligned with clinical note retention (7+ years)
- Consent captured at recording initiation (not retrospective)
- No cloud STT without BAA (Business Associate Agreement) with provider

## Consequences

- Voice integration deferred entirely from pilot scope
- `voice_transcription_service.py` maintained as scaffold for future activation
- No audio processing infrastructure required for pilot
- Activation gated on: (a) customer demand signal, (b) medical STT benchmark meeting <5% WER, (c) BAA with STT provider

## Evidence Paths

- Voice service scaffold: `backend/app/services/voice_transcription_service.py`
- NLP extraction pipeline: `backend/app/services/narrative_extractor.py`
- This decision: `docs/decisions/p4-008-voice-integration.md`
