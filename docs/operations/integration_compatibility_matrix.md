# Versioned Integration Compatibility Matrix

**Document ID**: IO-P3-023
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Interoperability
**Classification**: Internal — Technical

## Purpose

Maintain a versioned compatibility matrix for all supported EHR integrations (Meditech, OpenEHR, FHIR), tracking which versions/variants are validated and supported.

## Meditech Compatibility

| Meditech Version | Connector Version | Contract Version | Status | Last Validated |
|---|---|---|---|---|
| Meditech Expanse (6.x) | 1.0.0 | P0-018 v1.0.0 | Validated | 2026-02-15 |
| Meditech MAGIC | Not supported | — | Planned | — |
| Meditech Client/Server | Not supported | — | Planned | — |

### Meditech Data Format Support

| Format | Status | Notes |
|---|---|---|
| ADT (admit/discharge/transfer) | Supported | Via HL7v2 connector |
| Orders | Supported | Via HL7v2 connector |
| Results | Supported | Via HL7v2 connector |
| Clinical notes (free text) | Supported | Via document import |
| Structured compositions | Supported | Via OpenEHR connector |

## OpenEHR Compatibility

| OpenEHR Standard | Version | Status | Archetypes Supported |
|---|---|---|---|
| OpenEHR RM | 1.0.4+ | Supported | 12 standard archetypes |
| OpenEHR REST API | 1.0.0+ | Supported | COMPOSITION CRUD |
| AQL | 1.0+ | Not supported | Planned |

### Supported Archetypes

| Archetype | Version | Domain | Import | Export |
|---|---|---|---|---|
| COMPOSITION.encounter.v1 | v1 | Wrapper | Yes | Yes |
| EVALUATION.problem_diagnosis | v1 | Condition | Yes | Yes |
| INSTRUCTION.medication_order | v3 | Drug | Yes | Yes |
| OBSERVATION.laboratory_test_result | v1 | Measurement | Yes | Yes |
| OBSERVATION.blood_pressure | v2 | Measurement | Yes | Yes |
| OBSERVATION.body_temperature | v2 | Measurement | Yes | Yes |
| OBSERVATION.body_weight | v2 | Measurement | Yes | Yes |
| OBSERVATION.height | v2 | Measurement | Yes | Yes |
| OBSERVATION.pulse | v1 | Measurement | Yes | Yes |
| OBSERVATION.pulse_oximetry | v1 | Measurement | Yes | Yes |
| ACTION.procedure | v1 | Procedure | Yes | Yes |
| EVALUATION.adverse_reaction_risk | v1 | Observation | Yes | Yes |

## FHIR Compatibility

| FHIR Version | Status | Profile Support |
|---|---|---|
| R4 (4.0.1) | Supported | US Core 3.1.1 |
| R4B (4.3.0) | Compatible (untested) | — |
| R5 (5.0.0) | Not supported | Planned |
| STU3 (3.0.2) | Not supported | Not planned |

### FHIR Resource Support

| Resource | Import | Export | Search | Profile |
|---|---|---|---|---|
| Patient | Yes | Yes | Yes | US Core |
| Condition | Yes | Yes | Yes | US Core |
| MedicationRequest | Yes | Yes | Yes | US Core |
| Observation (vitals) | Yes | Yes | Yes | US Core Vitals |
| Observation (labs) | Yes | Yes | Yes | US Core Labs |
| Procedure | Yes | Yes | Yes | US Core |
| AllergyIntolerance | Yes | Yes | Yes | US Core |
| DiagnosticReport | Yes | Yes | No | US Core |
| DocumentReference | Yes | Yes | No | US Core |

## Code System Support

| Code System | Version | Import | Export | Mapping |
|---|---|---|---|---|
| SNOMED CT | International + AU | Yes | Yes | OMOP |
| ICD-10-CM | 2025 | Yes | Yes | OMOP |
| ICD-10-AM | 12th Edition | Yes | Yes | OMOP (partial) |
| LOINC | 2.77 | Yes | Yes | OMOP |
| RxNorm | Current | Yes | Yes | OMOP |
| CPT | 2025 | Yes | Yes | OMOP |
| HCPCS | 2025 | Yes | Yes | OMOP |
| ATC | 2025 | Yes | No | Via RxNorm |

## Update Cadence

- **Quarterly**: Review matrix, update status of planned items
- **On integration**: Update when new connector or version validated
- **On standard update**: When FHIR/OpenEHR standards release new versions
