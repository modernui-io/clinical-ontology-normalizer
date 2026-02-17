# P4-008-I: Ambient Voice Path Feasibility Plan

**Task:** P4-008-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Feasibility plan complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-008-voice-integration.md`

## Summary

This document defines the implementation plan for ambient voice/documentation integration as a separate product track. Activation is gated on customer demand signal, medical STT benchmark meeting <5% WER, and BAA with STT provider.

## PHI Handling Decision for Audio

### Classification
- **Audio recordings containing patient speech are PHI** under HIPAA (45 CFR 160.103)
- Audio may contain: patient names, dates of birth, medical record numbers, condition descriptions, medication names, provider names
- Classification applies regardless of whether audio is transcribed

### Consent Requirements
| Consent Type | When Required | Mechanism |
|-------------|--------------|-----------|
| Recording consent | Before any audio capture begins | Explicit opt-in UI with clear disclosure |
| Storage consent | At recording initiation | Bundled with recording consent |
| Processing consent | Before STT processing | Included in recording consent (process description) |
| Sharing consent | Before any external STT provider | Separate consent if cloud STT used |

### Storage Architecture
```
Audio Storage Tier (Separate from primary PHI stores):
  - Encryption at rest: AES-256 (FIPS 140-2 validated)
  - Encryption in transit: TLS 1.3
  - Access control: Role-based, clinician + authorized reviewer only
  - Storage location: Same region as primary PHI (ap-southeast-2 per P4-005)
  - Backup: Included in PHI backup schedule (P2-016)
  - Audit: All access logged (P0-014 worker audit + P0-015 graph audit patterns)
```

### Retention Policy
| Data Type | Retention Period | Disposal Method |
|-----------|-----------------|-----------------|
| Raw audio | 7 years (aligned with clinical note retention per P1-028) | Secure deletion with verification |
| Transcripts | 7 years (same as clinical notes) | Standard PHI disposal |
| STT metadata | 7 years | Standard PHI disposal |
| Processing logs | 3 years (operational data) | Standard log rotation |

## STT Provider Evaluation Path

### Candidate Providers

| Provider | Deployment | Medical Accuracy | BAA Available | Cost Estimate | PHI Handling |
|----------|-----------|-----------------|--------------|--------------|-------------|
| OpenAI Whisper (self-hosted) | On-premises / private cloud | ~8% general WER, unknown medical | N/A (self-hosted) | Compute cost only ($0.05-0.10/min) | Full control |
| Whisper large-v3 (fine-tuned) | On-premises / private cloud | Potentially <5% with medical fine-tuning | N/A (self-hosted) | Compute + fine-tuning cost | Full control |
| Azure Speech (Medical Custom) | Azure cloud | <5% with custom medical model | Yes (Microsoft BAA) | $0.016/min standard, $0.030/min custom | Azure HIPAA compliance |
| Google Medical STT | Google Cloud | Medical-optimized, <5% claimed | Yes (Google BAA) | $0.024/min medical | Google HIPAA compliance |
| AWS Transcribe Medical | AWS | Medical-optimized, <5% claimed | Yes (AWS BAA) | $0.0125/min | AWS HIPAA compliance |

### Evaluation Criteria
| Criterion | Weight | Threshold |
|-----------|--------|-----------|
| Medical WER | 30% | <5% on test corpus |
| Specialty terminology accuracy | 20% | >95% on specialty terms |
| Speaker diarization accuracy | 15% | >90% speaker identification |
| Latency (real-time factor) | 10% | <0.5x (faster than real-time) |
| BAA / HIPAA compliance | 15% | BAA signed before any PHI processing |
| Cost per minute | 10% | <$0.05/min at scale |

### Evaluation Protocol
1. **Corpus preparation:** 100 clinical encounters across 5 specialties (20 each)
2. **Ground truth:** Manual transcription by medical transcriptionist (gold standard)
3. **Blind evaluation:** Each provider transcribes same corpus independently
4. **Metrics computed:** WER, medical term accuracy, speaker diarization accuracy, latency
5. **Decision:** Provider meeting all thresholds selected; self-hosted preferred if accuracy matches cloud

## 4-Phase Activation Roadmap

### Phase 1: STT Provider Evaluation (Month 1-2)
**Objective:** Select STT provider meeting <5% medical WER

| Week | Activity | Deliverable |
|------|----------|-------------|
| 1-2 | Prepare evaluation corpus (100 encounters) | Annotated audio + ground truth transcripts |
| 3-4 | Benchmark Whisper large-v3 (self-hosted) | WER report + per-specialty breakdown |
| 5-6 | Benchmark Azure Speech Medical Custom | WER report + BAA status |
| 7-8 | Benchmark Google/AWS Medical STT | WER report + cost comparison |
| 8 | Provider selection decision | Signed evaluation report |

**Exit criteria:** Selected provider <5% medical WER, BAA confirmed (if cloud), cost within budget

### Phase 2: Audio Ingestion Pipeline (Month 3-4)
**Objective:** Build end-to-end audio capture, storage, and transcription pipeline

| Component | Description | Reference |
|-----------|------------|-----------|
| Audio capture service | Record clinical encounters with consent UI | New service |
| Audio storage adapter | PHI-compliant storage with encryption + audit | Extends P0-012 patterns |
| STT integration | Connect selected provider to `voice_transcription_service.py` | Extends existing scaffold (563 lines) |
| Consent management | Record and verify consent before processing | Extends P1-027 consent patterns |
| Transcript store | Store structured transcripts with timing metadata | New PostgreSQL tables |

**Exit criteria:** Audio recorded, stored, transcribed with consent tracking. End-to-end latency <2x real-time.

### Phase 3: Clinical Note Structuring (Month 5-6)
**Objective:** Transform transcripts into structured clinical data

```
Audio -> STT -> Transcript -> Speaker Diarization -> Section Detection -> NLP Extraction -> Clinical Note

Integration Points:
  - Transcript segments feed into narrative_extractor.py (existing NLP pipeline)
  - Extracted mentions mapped to OMOP (existing mapping pipeline)
  - ClinicalFacts built from voice-sourced extractions (existing fact builder)
  - Provenance tracks source as "voice_transcription" (data lineage per P2-022)
```

| Component | Description | Reference |
|-----------|------------|-----------|
| Speaker diarization | Identify clinician vs patient speech | STT provider feature or post-processing |
| Section detection | Map transcript to clinical note sections (HPI, ROS, Assessment, Plan) | New ML model or rule-based |
| NLP integration | Feed transcript text into `narrative_extractor.py` | Existing service |
| Note assembly | Combine structured extractions into clinical note format | New service |

**Exit criteria:** Clinical notes generated from voice with >90% section accuracy. NLP extraction quality comparable to typed notes.

### Phase 4: Clinician Review Workflow (Month 7-8)
**Objective:** Enable clinician review, correction, and approval of voice-generated notes

| Feature | Description |
|---------|------------|
| Review UI | Side-by-side audio playback + generated note with segment highlighting |
| Confidence display | Per-segment and per-extraction confidence scores |
| Correction interface | Edit note with corrections tracked for model improvement |
| Approval workflow | Clinician sign-off required before note enters patient record |
| Feedback loop | Corrections feed back to improve STT and NLP models |

**Exit criteria:** Clinician can review, correct, and approve voice-generated note within 2 minutes average. Correction rate <10% after 30 days of feedback-loop improvement.

## Integration Architecture

```
                    +-----------------+
                    |  Audio Capture   |
                    |  (with consent)  |
                    +--------+--------+
                             |
                    +--------v--------+
                    |  PHI Audio Store |
                    |  (encrypted)     |
                    +--------+--------+
                             |
                    +--------v--------+
                    |  STT Provider    |
                    |  (BAA required)  |
                    +--------+--------+
                             |
                    +--------v--------+
                    |  Transcript      |
                    |  + Diarization   |
                    +--------+--------+
                             |
                    +--------v--------+
                    |  Section Detect  |
                    |  (HPI/ROS/A/P)   |
                    +--------+--------+
                             |
                    +--------v-----------+
                    |  NLP Extraction     |
                    |  (narrative_        |
                    |   extractor.py)     |
                    +--------+-----------+
                             |
                    +--------v--------+
                    |  Clinical Note   |
                    |  + OMOP Mapping   |
                    +--------+--------+
                             |
                    +--------v--------+
                    |  Clinician       |
                    |  Review + Approve |
                    +-----------------+
```

## BAA Requirements

| Requirement | Details |
|-------------|---------|
| BAA scope | Audio PHI processing, storage (if cloud), transmission |
| BAA parties | Clinical Ontology Normalizer entity + STT provider |
| Data handling | Provider must not retain audio after processing (or retention within BAA terms) |
| Breach notification | Provider must notify within 24 hours of suspected breach |
| Audit rights | We retain right to audit provider's PHI handling |
| Subcontractors | Provider must disclose all subcontractors handling PHI |
| Termination | Data destruction within 30 days of BAA termination |

**Note:** Self-hosted Whisper avoids BAA requirement for STT processing but still requires PHI-compliant infrastructure.

## Activation Criteria Checklist

- [ ] Customer demand signal confirmed (Ramsey Health or other pilot customer requests voice integration)
- [ ] Medical STT benchmark completed with <5% WER on evaluation corpus
- [ ] BAA signed with selected STT provider (if cloud-based)
- [ ] Audio PHI storage infrastructure provisioned with encryption and audit
- [ ] Consent management UI reviewed and approved by Compliance
- [ ] Budget approved for STT processing costs
- [ ] `voice_transcription_service.py` extended with real STT integration

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P0-012 (Encryption at rest) | Audio storage must follow same encryption standard | Closed |
| P0-014 (Worker audit) | Audio processing workers must produce audit events | Closed |
| P1-027 (Consent metadata) | Consent capture pattern reusable for voice consent | Closed |
| P1-028 (Retention policy) | Audio retention aligned with clinical note retention | Closed |
| P2-022 (Data lineage) | Voice-sourced extractions tracked in lineage chain | Closed |
| P4-005 (Multi-region) | Audio stored in same region as primary PHI | Monitoring |
