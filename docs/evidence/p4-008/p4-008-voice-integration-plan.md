# P4-008-I: Ambient Voice/Documentation Integration Plan

**Task:** P4-008-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Implementation plan complete (deferred per ADR)
**ADR Reference:** `docs/decisions/p4-008-voice-integration.md`

## Summary

This document defines the comprehensive implementation plan for ambient voice/documentation integration as a separate product track within the Clinical Ontology Normalizer ecosystem. Per the ADR decision (P4-008-D), voice integration is deferred entirely from the pilot scope. This plan codifies the activation roadmap, PHI handling requirements, STT provider evaluation framework, WER benchmark specification, audio pipeline architecture, clinical note structuring design, and clinician review workflow so that activation can proceed without re-planning when gate criteria are met.

## Current State Assessment

### Voice Transcription Service Scaffold

| Component | File | Lines | Maturity | Notes |
|-----------|------|-------|----------|-------|
| `VoiceTranscriptionService` class | `backend/app/services/voice_transcription_service.py` | 563 | Scaffold | Simulated transcription only |
| `TranscriptionStatus` enum | Same file | L22-28 | Production-ready | pending, processing, completed, failed |
| `AudioFormat` enum | Same file | L31-39 | Production-ready | wav, mp3, m4a, ogg, webm, flac |
| `TranscriptionSegment` dataclass | Same file | L42-61 | Production-ready | id, start_time, end_time, text, confidence, speaker |
| `TranscriptionResult` dataclass | Same file | L64-91 | Production-ready | job_id, status, text, segments, language, duration, model |
| `ExtractedClinicalData` dataclass | Same file | L94-125 | Scaffold | chief_complaint, HPI, ROS, PE, assessment, plan, medications, diagnoses, procedures, labs, follow_up |
| Section marker dictionary | Same file | L132-180 | Scaffold | Rule-based section detection (CC, HPI, ROS, PE, Assessment, Plan, Medications, Follow-up) |
| ROS category list | Same file | L183-200 | Scaffold | 16 organ system categories |
| Clinical data extraction | Same file | L337-397 | Scaffold | Rule-based parsing, no ML |
| Medication extraction | Same file | L512-547 | Scaffold | Hardcoded 20-medication dictionary |
| Singleton pattern | Same file | L550-563 | Production-ready | Thread-safe double-checked locking |

### Key Observations

1. **No real STT integration** -- `_simulate_transcription()` returns hardcoded text (L278-324)
2. **No audio storage** -- Audio bytes processed in-memory only, no persistence
3. **No consent management** -- No consent capture or verification before processing
4. **No speaker diarization** -- `speaker` field exists on `TranscriptionSegment` but is never populated
5. **No PHI detection in audio** -- No mechanism to detect or redact PHI in audio streams
6. **Section detection is rule-based** -- Simple string matching against `SECTION_MARKERS` dictionary
7. **Medication list is static** -- Only 20 hardcoded medication names, no OMOP/RxNorm integration
8. **No API endpoints exposed** -- Service exists but no router registers voice endpoints

### What Can Be Reused

- `TranscriptionStatus`, `AudioFormat` enums (stable, well-defined)
- `TranscriptionSegment`, `TranscriptionResult` dataclasses (correct interface for any STT provider)
- `ExtractedClinicalData` dataclass (good starting schema, needs extension)
- Section marker dictionary (useful baseline, needs ML augmentation)
- Singleton service pattern (thread-safe, follows codebase conventions)

## PHI Handling Decision Matrix for Audio

### Audio PHI Classification

Audio recordings of clinical encounters are PHI under HIPAA (45 CFR 160.103). Audio may contain all 18 HIPAA identifiers in spoken form: patient names, dates, MRNs, SSNs, addresses, phone numbers, email addresses, provider names, facility names, and more.

### Decision Matrix

| Dimension | Decision | Rationale | Reference |
|-----------|----------|-----------|-----------|
| **Consent model** | Explicit opt-in at recording initiation | Audio recording is inherently more invasive than text entry; retrospective consent inadequate for audio | HIPAA Privacy Rule, state wiretapping laws |
| **Consent granularity** | Three-tier: (1) record, (2) store, (3) process via external STT | Cloud STT transmits PHI to third party; separate consent required | BAA requirements |
| **Storage tier** | Dedicated audio PHI store, separate from primary PostgreSQL | Audio files are large (10-50 MB/encounter), binary, require streaming access patterns | Infrastructure cost management |
| **Encryption at rest** | AES-256 with FIPS 140-2 validated module | Aligns with existing PHI encryption standard (P0-012) | HIPAA Security Rule 164.312(a)(2)(iv) |
| **Encryption in transit** | TLS 1.3 minimum | Aligns with existing transport encryption standard | HIPAA Security Rule 164.312(e)(1) |
| **Key management** | Separate encryption keys from primary PHI store | Compromise isolation: audio key rotation independent of database keys | Defense in depth |
| **Access control** | Role-based: recording clinician, authorized reviewer, system admin only | Minimum necessary principle; no broad clinical staff access to audio | HIPAA Minimum Necessary Rule |
| **Audit logging** | Every access event logged: play, download, delete, process | Extends P0-014 worker audit pattern to audio operations | HIPAA Security Rule 164.312(b) |
| **Retention period** | 7 years minimum (aligned with clinical note retention) | Audio is part of clinical record when used to generate notes | P1-028 retention policy |
| **Disposal method** | Secure deletion with cryptographic verification (overwrite + verify) | Audio files on disk/object storage require explicit overwrite, not just pointer deletion | NIST SP 800-88 |
| **BAA requirements** | Required before any cloud STT processes audio containing PHI | No exceptions; self-hosted STT avoids BAA requirement for processing | HIPAA Business Associate Rule |
| **BAA scope** | Must cover: audio transmission, processing, temporary storage, breach notification | Provider must not retain audio beyond processing window | Standard BAA terms |
| **Breach notification** | Provider must notify within 24 hours of suspected breach | More aggressive than HIPAA 60-day window; contractual requirement | Risk management |
| **Data residency** | Same region as primary PHI (per P4-005 multi-region decisions) | Consistent compliance posture; no cross-border audio transfer | Data sovereignty |

## STT Provider Evaluation Framework

### Candidate Providers

| Provider | Model | Deployment | Medical Specialization | BAA | Estimated Cost | PHI Risk |
|----------|-------|-----------|----------------------|-----|---------------|----------|
| OpenAI Whisper large-v3 | whisper-large-v3 | Self-hosted (GPU) | General-purpose, no medical fine-tuning | N/A (self-hosted) | ~$0.05-0.10/min (compute) | Full control |
| OpenAI Whisper large-v3 (fine-tuned) | Custom fine-tune | Self-hosted (GPU) | Medical fine-tuning on clinical corpus | N/A (self-hosted) | Compute + fine-tuning dataset cost | Full control |
| Azure Speech Medical | Custom Speech (medical domain) | Azure Cloud | Medical-adapted acoustic and language models | Yes (Microsoft BAA) | $0.016/min std, $0.030/min custom | Azure HIPAA-compliant infra |
| Google Medical STT | Medical Dictation API | Google Cloud | Medical-optimized, 80+ medical specialties | Yes (Google BAA) | $0.024/min medical tier | Google HIPAA-compliant infra |
| AWS Transcribe Medical | Amazon Transcribe Medical | AWS | Medical-specialized, drug names + anatomical terms | Yes (AWS BAA) | $0.0125/min | AWS HIPAA-compliant infra |

### Evaluation Criteria (Weighted Scoring)

| Criterion | Weight | Threshold | Measurement Method |
|-----------|--------|-----------|-------------------|
| Medical WER (overall) | 30% | <5% | Standard WER on 100-encounter test corpus |
| Medical terminology accuracy | 20% | >95% on OMOP-matched terms | WER restricted to tokens matching OMOP concept dictionary |
| Speaker diarization accuracy | 15% | >90% correct speaker attribution | DER (Diarization Error Rate) on multi-speaker encounters |
| Real-time factor (latency) | 10% | <0.5x (faster than real-time) | Processing time / audio duration |
| BAA / HIPAA compliance | 15% | BAA signed before any PHI test | Binary: BAA executed or not |
| Cost per minute at scale | 10% | <$0.05/min at 10K encounters/month | Provider pricing at projected volume |

### Provider Selection Decision Tree

```
1. Does provider offer BAA covering audio PHI?
   No  -> Self-hosted only (Whisper)
   Yes -> Continue

2. Medical WER <5% on evaluation corpus?
   No  -> Eliminate
   Yes -> Continue

3. Medical terminology WER <3%?
   No  -> Flag for medical fine-tuning evaluation
   Yes -> Continue

4. Speaker diarization >90%?
   No  -> Evaluate with external diarization post-processing
   Yes -> Continue

5. Cost <$0.05/min at scale?
   No  -> Negotiate volume pricing or evaluate self-hosted
   Yes -> Candidate passes

6. If multiple candidates pass:
   Prefer self-hosted (Whisper fine-tuned) for PHI control
   If self-hosted WER matches cloud: select self-hosted
   If self-hosted WER >1% worse: select cloud with BAA
```

## WER Benchmark Specification

### Test Corpus

| Parameter | Specification |
|-----------|---------------|
| **Total encounters** | 100 clinical encounters |
| **Specialty distribution** | 20 encounters each: General Internal Medicine, Cardiology, Oncology, Nephrology, Endocrinology |
| **Encounter types** | 60 outpatient visits, 20 inpatient rounds, 10 ED encounters, 10 procedure notes |
| **Speaker count** | 1-3 speakers per encounter (clinician, patient, interpreter) |
| **Audio duration** | 5-30 minutes per encounter (total ~20 hours) |
| **Audio quality** | Clinical environment recordings (background noise, equipment sounds) |
| **Accent diversity** | Minimum 30% non-native English speakers in patient population |
| **Ground truth** | Manual transcription by 2 certified medical transcriptionists per encounter |
| **Inter-annotator agreement** | >98% word-level agreement required (adjudication for disagreements) |
| **Terminology density** | Encounters selected to cover >500 unique OMOP-mapped medical terms |

### WER Computation Methodology

```
Standard WER:
  WER = (S + I + D) / N
  Where:
    S = Substitutions (wrong word)
    I = Insertions (extra word)
    D = Deletions (missing word)
    N = Total words in reference transcript

Medical WER:
  Same formula, restricted to tokens identified as medical terminology
  Medical token identification: token matches OMOP concept synonym table
  OR token matches RxNorm ingredient/brand name
  OR token matches anatomical term dictionary (SNOMED body structures)

Combined Clinical Accuracy:
  CCA = (1 - Medical WER) * Section Detection Accuracy * Entity Extraction F1
  Target: CCA > 0.85 (85%)
```

### Per-Specialty Acceptance Criteria

| Specialty | Max Overall WER | Max Medical WER | Rationale |
|-----------|----------------|-----------------|-----------|
| General Internal Medicine | 5% | 3% | Baseline |
| Cardiology | 5% | 4% | Complex hemodynamic terminology |
| Oncology | 5% | 4% | Drug regimen terminology (FOLFOX, pembrolizumab) |
| Nephrology | 5% | 4% | Laboratory value heavy (eGFR, BUN, creatinine clearance) |
| Endocrinology | 5% | 4% | Insulin regimen complexity (basal-bolus, sliding scale) |

### Benchmark Execution Protocol

1. **Corpus preparation** (2 weeks): Record or acquire 100 encounters with consent, produce ground truth transcripts
2. **Provider setup** (1 week): Configure each provider with identical audio format (WAV 16kHz mono)
3. **Blind evaluation** (2 weeks): Each provider transcribes same corpus independently; no tuning between runs
4. **Scoring** (1 week): Automated WER computation using `jiwer` library with medical token filter
5. **Error analysis** (1 week): Categorize errors by type (terminology, speaker attribution, noise artifact, abbreviation)
6. **Decision report** (1 week): Comparative analysis with recommendation

## Audio Ingestion Pipeline Design

### Format Handling

| Input Format | Handling | Output |
|-------------|---------|--------|
| WAV (16-bit PCM) | Pass through (preferred format) | WAV 16kHz mono |
| MP3 | Transcode via ffmpeg | WAV 16kHz mono |
| M4A/AAC | Transcode via ffmpeg | WAV 16kHz mono |
| OGG/Opus | Transcode via ffmpeg | WAV 16kHz mono |
| WebM | Extract audio track via ffmpeg | WAV 16kHz mono |
| FLAC | Decompress | WAV 16kHz mono |

All audio normalized to 16kHz mono WAV before STT processing for consistent evaluation and provider compatibility.

### Audio Chunking Strategy

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Chunk duration | 30 seconds | Balance between context window and processing latency |
| Overlap | 5 seconds | Prevent word boundary splits at chunk edges |
| Max encounter duration | 60 minutes | Hard limit to prevent runaway processing |
| Silence detection | >3 seconds silence = chunk boundary candidate | Natural pause points preserve sentence boundaries |
| VAD (Voice Activity Detection) | WebRTC VAD or Silero VAD | Filter non-speech segments before STT |

### Speaker Diarization

```
Audio -> VAD -> Speech Segments -> Speaker Embedding -> Clustering -> Speaker Labels

Speaker Identification:
  - Clinician: identified by initial speaker in encounter (convention)
  - Patient: second speaker
  - Other: interpreter, family member, nurse (labeled speaker_3, speaker_4, etc.)

Diarization Approaches (by provider):
  - Azure Speech: Built-in diarization (up to 20 speakers)
  - Google STT: Speaker diarization API
  - Whisper (self-hosted): pyannote.audio post-processing
  - AWS Transcribe Medical: Built-in speaker identification
```

### PHI Detection in Audio

| PHI Type | Detection Method | Action |
|----------|-----------------|--------|
| Patient name | NER on transcript (post-STT) | Flag segment, do not expose in review UI without auth |
| MRN/SSN | Regex on transcript + acoustic pattern (digit sequences) | Flag segment, mask in display |
| Date of birth | NER + date pattern matching on transcript | Flag segment |
| Address | NER on transcript | Flag segment |
| Phone number | Regex on transcript | Flag segment |
| All 18 HIPAA identifiers | Comprehensive NER pipeline post-transcription | Flag, log, apply access controls |

PHI detection occurs on the transcript (post-STT), not on raw audio. Raw audio is always treated as PHI regardless of content detection results.

### Pipeline Sequence

```
1. Audio Upload (with consent token)
2. Format Validation (AudioFormat enum check)
3. Transcode to WAV 16kHz mono (if needed)
4. Store encrypted audio in PHI audio store
5. Voice Activity Detection (filter silence)
6. Chunk audio (30s chunks, 5s overlap)
7. Submit chunks to STT provider (with BAA)
8. Receive transcript segments with timing
9. Merge overlapping chunks (de-duplicate overlap regions)
10. Speaker diarization (label speakers)
11. PHI detection on transcript (flag segments)
12. Store transcript in PHI-protected transcript store
13. Emit event for downstream NLP processing
```

## Clinical Note Structuring

### Transcript to NLP Extraction Pipeline

```
Transcript Segments (with speaker labels, timing)
        |
        v
Section Detection (rule-based + ML)
  - Map segments to clinical note sections
  - Uses existing SECTION_MARKERS as baseline
  - ML model trained on labeled clinical transcripts for improved accuracy
        |
        v
Section Text Assembly
  - Concatenate segments per section
  - Filter patient speech from clinician documentation speech
  - Resolve coreferences across segments
        |
        v
NLP Extraction (narrative_extractor.py integration)
  - Feed section text as if it were typed clinical note
  - Extract Mentions (conditions, medications, procedures, labs)
  - Apply assertion detection (present, absent, conditional, hypothetical)
  - Apply temporality detection (current, historical, future)
  - Apply experiencer detection (patient, family member)
        |
        v
OMOP Mapping (existing mapping pipeline)
  - MentionConceptCandidate generation
  - Best-match selection with confidence scoring
        |
        v
ClinicalFact Creation (existing fact builder)
  - Provenance: source_type = "voice_transcription"
  - Links to: audio_file_id, transcript_segment_ids, encounter_id
  - Confidence: compound of STT confidence * NLP extraction confidence * mapping confidence
        |
        v
Clinical Note Assembly
  - Structure ClinicalFacts into note format (HPI, ROS, Assessment, Plan)
  - Apply note template for specialty
  - Generate draft note for clinician review
```

### Integration Points with Existing Pipeline

| Integration Point | Existing Service | Adaptation Required |
|-------------------|-----------------|-------------------|
| NLP extraction | `narrative_extractor.py` | Add `source_type` parameter to track voice origin |
| OMOP mapping | `mapping_service.py` / `mapping_pipeline.py` | None (text input is format-agnostic) |
| Fact building | `fact_builder_service.py` | Add voice provenance fields (audio_id, segment_ids) |
| Knowledge graph | `graph_builder_service.py` | Add voice-sourced node/edge properties |
| Data lineage | P2-022 lineage tracking | Add voice pipeline as lineage source type |

## Clinician Review Workflow

### Review UI Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Side-by-side view | Audio playback alongside generated note | P0 |
| Segment highlighting | Click note section to jump to corresponding audio segment | P0 |
| Confidence display | Per-segment confidence bars (green >90%, yellow 70-90%, red <70%) | P0 |
| Inline editing | Edit any section of the generated note | P0 |
| Track changes | Visual diff between original generated note and clinician edits | P1 |
| Approval button | Clinician sign-off to finalize note (irreversible) | P0 |
| Reject/re-process | Request re-transcription with different STT settings | P1 |
| Audio speed control | 0.5x, 1x, 1.5x, 2x playback speed | P1 |

### Confidence Scoring

```
Segment Confidence = STT_confidence (from provider)
Section Confidence = mean(segment_confidences in section)
Extraction Confidence = NLP_model_confidence * STT_segment_confidence
Note Confidence = min(section_confidences) -- weakest link determines overall

Display Rules:
  >= 0.90: Green  (high confidence, likely correct)
  0.70-0.89: Yellow (moderate confidence, review recommended)
  < 0.70: Red     (low confidence, correction likely needed)

Red segments auto-flagged for clinician attention.
```

### Correction and Feedback Loop

```
Clinician Correction Flow:
1. Clinician identifies error in generated note
2. Clinician edits text directly in review UI
3. System records:
   - Original text (STT + NLP output)
   - Corrected text (clinician edit)
   - Audio segment reference (for re-training)
   - Error category (STT error, NLP error, section misattribution, other)
4. Correction stored in feedback table

Feedback Loop (Batch):
  - Weekly: aggregate corrections by error category
  - Monthly: if >100 corrections accumulated:
    - STT errors -> fine-tuning dataset for Whisper (if self-hosted)
    - NLP errors -> retraining signal for narrative_extractor.py
    - Section errors -> update section detection model/rules
  - Quarterly: re-run WER benchmark with updated model to measure improvement
```

## 8-Month Phased Timeline

### Phase 1: STT Provider Evaluation (Month 1-2)

| Week | Activity | Deliverable | Owner |
|------|----------|-------------|-------|
| 1-2 | Prepare evaluation corpus (100 encounters, 5 specialties) | Annotated audio files + ground truth transcripts | Clinical AI + Medical Transcription |
| 3-4 | Benchmark Whisper large-v3 self-hosted | WER report with per-specialty breakdown | ML Engineering |
| 5-6 | Benchmark Azure Speech Medical Custom | WER report + BAA negotiation status | ML Engineering + Legal |
| 7-8 | Benchmark Google/AWS Medical STT | WER report + cost analysis | ML Engineering + Finance |
| 8 | Provider selection decision | Signed evaluation report with recommendation | Clinical AI Lead |

**Gate 1 -> Phase 2:** Selected provider achieves <5% overall WER and <4% medical WER. BAA confirmed if cloud provider selected. Budget approved.

### Phase 2: Audio Ingestion Pipeline (Month 3-4)

| Week | Activity | Deliverable | Owner |
|------|----------|-------------|-------|
| 9-10 | Audio storage infrastructure (PHI-compliant, encrypted) | Deployed audio store with encryption and audit | Infrastructure |
| 11-12 | STT integration into `voice_transcription_service.py` | Real transcription via selected provider | ML Engineering |
| 13-14 | Consent management UI and API | Consent capture + verification before processing | Frontend + Backend |
| 15-16 | Audio chunking + VAD + format normalization | End-to-end audio ingestion pipeline | ML Engineering |

**Gate 2 -> Phase 3:** Audio recorded, stored (encrypted), transcribed with consent tracking. End-to-end latency <2x real-time. PHI compliance audit passed.

### Phase 3: Clinical Note Structuring (Month 5-6)

| Week | Activity | Deliverable | Owner |
|------|----------|-------------|-------|
| 17-18 | Speaker diarization integration | Labeled speaker segments with >90% accuracy | ML Engineering |
| 19-20 | Section detection model (rule-based + ML hybrid) | Transcript sections mapped to clinical note structure | ML Engineering |
| 21-22 | NLP extraction integration (`narrative_extractor.py`) | Mentions extracted from voice-sourced text | Clinical AI |
| 23-24 | Clinical note assembly + OMOP mapping | Structured notes with OMOP-mapped concepts | Clinical AI |

**Gate 3 -> Phase 4:** Clinical notes generated from voice with >90% section detection accuracy. NLP extraction quality on voice-sourced text within 5% of typed note extraction quality. Provenance tracking operational.

### Phase 4: Clinician Review Workflow (Month 7-8)

| Week | Activity | Deliverable | Owner |
|------|----------|-------------|-------|
| 25-26 | Review UI (side-by-side audio + note, confidence display) | Functional review interface | Frontend |
| 27-28 | Correction interface + track changes | Edit tracking with error categorization | Frontend + Backend |
| 29-30 | Approval workflow + feedback loop pipeline | Clinician sign-off + correction aggregation | Backend |
| 31-32 | End-to-end testing + clinician usability study | Acceptance test results + UX feedback | QA + Clinical Users |

**Gate 4 (Production readiness):** Clinician can review, correct, and approve voice-generated note within 2 minutes average. Correction rate <10% after 30 days. All PHI compliance checks passed. WER remains <5% on production traffic sample.

## Integration Test Evidence Template

When activated, the following test suite must be executed and results recorded:

### Audio Pipeline Tests

| Test ID | Description | Input | Expected Output | Pass Criteria |
|---------|-------------|-------|----------------|---------------|
| VT-INT-001 | Audio upload with valid consent | WAV file + consent token | Audio stored, consent recorded, job_id returned | HTTP 201, consent audit event logged |
| VT-INT-002 | Audio upload without consent | WAV file, no consent | Processing rejected | HTTP 403, no audio stored |
| VT-INT-003 | Format transcoding | MP3 file | Transcoded to WAV 16kHz mono | Output format verified |
| VT-INT-004 | STT transcription | 60s clinical audio | Transcript with timing | Non-empty text, segments with timestamps |
| VT-INT-005 | Speaker diarization | 2-speaker encounter | Speaker-labeled segments | >=2 distinct speaker labels |
| VT-INT-006 | Audio chunking | 15-minute encounter | ~30 chunks with 5s overlap | Chunk count within expected range |

### NLP Integration Tests

| Test ID | Description | Input | Expected Output | Pass Criteria |
|---------|-------------|-------|----------------|---------------|
| VT-INT-007 | Section detection | Clinical encounter transcript | HPI, ROS, Assessment, Plan sections | All 4 major sections identified |
| VT-INT-008 | NLP extraction from voice text | Section-labeled transcript | Mentions with concept candidates | Mentions extracted, OMOP candidates generated |
| VT-INT-009 | Clinical fact creation | Voice-sourced mentions | ClinicalFacts with voice provenance | source_type = "voice_transcription" |
| VT-INT-010 | End-to-end pipeline | 10-min encounter audio | Structured clinical note | Note generated within 5 minutes |

### PHI Compliance Tests

| Test ID | Description | Expected | Pass Criteria |
|---------|-------------|----------|---------------|
| VT-PHI-001 | Encryption at rest | Audio encrypted AES-256 | Verified via storage inspection |
| VT-PHI-002 | Encryption in transit | TLS 1.3 | Verified via network capture |
| VT-PHI-003 | Access audit | Every access event logged | Audit log contains all access events |
| VT-PHI-004 | Consent enforcement | No processing without consent | Blocked requests logged |
| VT-PHI-005 | Retention enforcement | Audio retention = 7 years | Retention metadata set correctly |
| VT-PHI-006 | BAA verification | BAA executed before PHI test | BAA document on file |

## Activation Criteria Checklist

- [ ] Customer demand signal confirmed (Ramsey Health or other pilot customer explicitly requests voice integration)
- [ ] Medical STT benchmark completed with <5% overall WER on 100-encounter evaluation corpus
- [ ] Medical terminology WER <4% across all evaluated specialties
- [ ] BAA signed with selected STT provider (if cloud-based; N/A if self-hosted)
- [ ] Audio PHI storage infrastructure provisioned with AES-256 encryption and audit logging
- [ ] Consent management UI reviewed and approved by Compliance team
- [ ] Budget approved for STT processing costs (estimated $X/month at projected volume)
- [ ] `voice_transcription_service.py` extended with real STT integration (replacing `_simulate_transcription`)
- [ ] Speaker diarization accuracy >90% on evaluation corpus
- [ ] NLP extraction quality on voice-sourced text within 5% of typed note quality
- [ ] Clinician review UI usability tested with >=5 clinicians
- [ ] End-to-end latency <5 minutes for 10-minute encounter
- [ ] P4-013 (SaMD) assessment completed if voice features affect clinical decisions

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P0-012 (Encryption at rest) | Audio storage must follow same encryption standard (AES-256) | Closed |
| P0-014 (Worker audit) | Audio processing workers must produce audit events | Closed |
| P0-015 (Graph audit) | Voice-sourced graph nodes must be auditable | Closed |
| P1-027 (Consent metadata) | Consent capture pattern reusable for voice recording consent | Closed |
| P1-028 (Retention policy) | Audio retention aligned with clinical note retention (7 years) | Closed |
| P2-003 (Canary tests) | Used for voice pipeline rollout verification | Closed |
| P2-016 (Backup schedule) | Audio included in PHI backup schedule | Closed |
| P2-022 (Data lineage) | Voice-sourced extractions tracked as lineage source type | Closed |
| P4-005 (Multi-region) | Audio stored in same region as primary PHI | Monitoring |
| P4-013 (SaMD) | Voice features affecting clinical decisions may trigger SaMD classification | Not yet assessed |
| Existing NLP pipeline (`narrative_extractor.py`) | Voice-sourced text feeds into existing extraction pipeline | Available (no changes needed for text input) |
| Existing OMOP mapping pipeline | Voice-extracted mentions mapped through standard pipeline | Available |
| Existing fact builder | Voice-sourced ClinicalFacts created through standard builder | Available (provenance extension needed) |
