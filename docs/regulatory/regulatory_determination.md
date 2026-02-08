# Regulatory Determination Document

**Document ID:** VP-Quality-1-RD
**Version:** 1.0
**Last Updated:** 2026-02-08
**Classification:** CONFIDENTIAL - Internal Use Only
**Owner:** VP of Quality / Regulatory Affairs
**Approval Status:** DRAFT - Pending Legal and Regulatory Review

---

## 1. Product Description

### 1.1 Product Name

Clinical Ontology Normalizer - Trial Matching Module

### 1.2 Product Overview

The Clinical Ontology Normalizer is a software platform that ingests clinical patient data, extracts clinical mentions using NLP (natural language processing), normalizes extracted concepts to OMOP (Observational Medical Outcomes Partnership) standard vocabularies, and constructs a patient knowledge graph. The Trial Matching Module extends this platform to screen patients against clinical trial eligibility criteria for the purpose of identifying potentially eligible candidates for clinical research studies.

### 1.3 Functional Description

The system performs the following functions:

1. **Data Ingestion**: Imports patient clinical data from FHIR R4 Bundles (conditions, medications, allergies, observations, procedures, encounters, immunizations, clinical notes, and diagnostic reports) via the `FHIRImportService`. Data sources include EHR integrations and Health Information Exchanges (HIE).

2. **Clinical NLP Extraction**: Processes clinical free-text notes through a multi-stage extraction pipeline (`ExtractionPipeline`) that performs:
   - Section detection and sentence segmentation
   - Pattern-based clinical entity extraction with confidence scoring
   - Negation detection and assertion classification (present, absent, conditional, hypothetical)
   - Temporality classification (current, past, future)
   - Experiencer classification (patient, family member)
   - Context analysis with medical knowledge rule validation

3. **Concept Normalization**: Maps extracted clinical mentions to OMOP standard vocabulary concepts using exact matching, fuzzy matching, and ML-based mapping methods (`MappingServiceInterface`). Each mapping produces scored candidates with vocabulary IDs and domain classifications.

4. **Clinical Fact Construction**: Persists normalized clinical data as `ClinicalFact` records with full provenance tracking (pipeline version, extraction confidence, data lineage via `record_lineage()`).

5. **Knowledge Graph Construction**: Builds a patient-centric knowledge graph with typed nodes (Patient, Condition, Drug, Measurement, Procedure, Observation) and edges (HAS_CONDITION, TAKES_DRUG, HAS_MEASUREMENT, etc.) stored in PostgreSQL with optional Neo4j persistence.

6. **Trial Eligibility Screening** (`TrialEligibilityService`): Evaluates patients against structured trial eligibility criteria by:
   - Querying `ClinicalFact` and `KGNode` tables against inclusion/exclusion criteria
   - Supporting criterion types: demographic (age range), condition (ICD-10/SNOMED codes), measurement (lab values with ranges), drug, procedure, and observation
   - Performing Boolean logic (AND across inclusion criteria, OR within code sets, subtraction of exclusion matches)
   - Computing weighted match scores with per-criterion confidence
   - Generating per-criterion audit trails with evidence fact IDs, evidence summaries, and confidence explanations
   - Applying safety guardrails: high-confidence exclusion matches (>0.7) trigger hard stops that cannot be overridden
   - Computing data completeness scores identifying missing clinical domains
   - Recording false-negative monitoring data for quality tracking

7. **Clinical Decision Support Output**: All screening results include:
   - `requires_clinician_review: true` flag (hardcoded, cannot be disabled)
   - CDS disclaimer text: "This screening result is intended as clinical decision support only. A qualified healthcare professional must independently verify all eligibility determinations before any enrollment actions. This system does not make autonomous clinical decisions."
   - Per-criterion evidence summaries enabling the reviewer to inspect the basis for each determination
   - Safety block indicators with explanatory reasons

### 1.4 Technology Stack

| Component | Technology |
|---|---|
| Backend API | Python 3.13, FastAPI, SQLAlchemy (async) |
| Frontend | TypeScript, Next.js App Router, Tailwind CSS |
| Primary Database | PostgreSQL |
| Job Queue | Redis |
| Graph Persistence | Neo4j (optional) |
| Data Standards | FHIR R4, OMOP CDM, ICD-10-CM, SNOMED CT, LOINC, RxNorm |

---

## 2. Intended Use Statement

### 2.1 Intended Use

The Clinical Ontology Normalizer Trial Matching Module is intended to assist clinical research coordinators and principal investigators in identifying patients who may be potentially eligible for clinical trial enrollment, by automating the comparison of structured and extracted patient clinical data against defined trial eligibility criteria.

### 2.2 Target Users

- **Primary Users**: Clinical Research Coordinators (CRCs), Clinical Trial Associates
- **Secondary Users**: Principal Investigators (PIs), Sub-Investigators, Site Research Directors
- **Administrative Users**: Clinical Operations Managers, Sponsors' Clinical Operations staff

All target users are qualified healthcare professionals or trained clinical research personnel operating under the supervision of a licensed physician investigator.

### 2.3 Clinical Setting

- Clinical trial sites (hospital-based and community-based)
- Academic medical centers with clinical research programs
- Clinical research organizations (CROs)
- Sponsor clinical operations departments

### 2.4 Scope of Functionality

The system provides preliminary screening recommendations that MUST be independently reviewed and verified by qualified clinical research personnel before any patient enrollment action is taken. The system does not:

- Make autonomous enrollment decisions
- Replace the clinical judgment of the investigator
- Serve as the sole basis for determining patient eligibility
- Provide clinical diagnoses or treatment recommendations
- Acquire, process, or analyze medical images or physiological signals

See `docs/regulatory/intended_use_statement.md` for the complete formal Intended Use / Indications for Use statement.

---

## 3. FDA SaMD Classification Analysis

### 3.1 IEC 62304 Software Lifecycle Applicability

IEC 62304:2006/AMD1:2015 (Medical device software - Software life cycle processes) applies to software that is itself a medical device (SaMD) or is embedded in a medical device.

**Applicability Assessment**: If the system is determined to be SaMD, IEC 62304 would apply. The software safety classification under IEC 62304 would determine the rigor of required lifecycle processes (see Section 5.2).

**Current Status**: Pending final regulatory determination. The codebase already implements practices aligned with IEC 62304 requirements, including:
- Version-controlled source code with audit trails
- Documented architecture and data flows
- Automated testing (pytest, Jest, Playwright)
- Pipeline versioning for clinical fact traceability (`pipeline_version` stamped on all `ClinicalFact` records)
- Data lineage tracking (`data_lineage` table)
- Audit logging (`AuditAction` framework)

### 3.2 FDA SaMD Definition Assessment

Per FDA guidance, "Software as a Medical Device" (SaMD) is defined as software intended to be used for one or more medical purposes that perform these purposes without being part of a hardware medical device (IMDRF/SaMD WG/N10FINAL:2013).

**Medical purpose** includes: treatment, diagnosis, cure, mitigation, prevention of disease, or providing information for clinical decision-making.

**Assessment**:

| SaMD Criterion | System Behavior | Assessment |
|---|---|---|
| Is it software? | Yes - standalone web application | Yes |
| Is it intended for a medical purpose? | It assists in clinical trial patient matching, which informs clinical research enrollment decisions | Borderline - see CDS analysis below |
| Does it function independently of hardware? | Yes - runs on standard server infrastructure | Yes |
| Does it provide information used to make clinical decisions? | It provides eligibility recommendations that inform enrollment decisions | Yes, but with mandatory human review |

**Preliminary SaMD Assessment**: The system meets the technical definition of SaMD as it provides information intended to inform healthcare-related decisions (clinical trial enrollment). However, the system may qualify for the CDS exemption under 21st Century Cures Act Section 520(o)(1), which would exempt it from FDA device regulation. See Section 3.5 below.

### 3.3 IMDRF SaMD Risk Categorization

Per the IMDRF Framework for Risk Categorization (IMDRF/SaMD WG/N12FINAL:2014):

**State of Healthcare Decision**: The system informs decisions about **clinical management** (specifically, clinical trial enrollment screening). It does not drive or treat.

| State | Description | Applicable? |
|---|---|---|
| Treat or Diagnose | Software drives clinical intervention or provides definitive diagnosis | No |
| Drive Clinical Management | Software drives clinical management decisions without clinician review | No |
| Inform Clinical Management | Software provides information to support clinician-driven management decisions | **Yes** |

**Significance of Information**:

| Significance | Description | Applicable? |
|---|---|---|
| Critical | Incorrect output could result in death or irreversible condition | No - trial screening is preliminary; actual enrollment requires PI consent, IRB oversight, and informed consent |
| Serious | Incorrect output could result in serious deterioration or surgical intervention | No - false positive/negative in screening does not directly cause patient harm |
| Non-Serious | Incorrect output would not cause serious injury | **Yes** - a missed match delays potential trial access; a false match is caught at PI review |

**IMDRF Risk Category**: Category I (Inform clinical management + Non-serious significance)

This is the lowest-risk SaMD category under the IMDRF framework.

### 3.4 21 CFR Part 820 Applicability

21 CFR Part 820 (Quality System Regulation / Current Good Manufacturing Practice) applies to finished medical devices. If the system is classified as a medical device (SaMD), a Quality Management System (QMS) compliant with 21 CFR Part 820 would be required.

**Current Status**: The organization does not currently maintain a full 21 CFR Part 820 QMS. If the CDS exemption applies (Section 3.5), Part 820 compliance is not required, though voluntary adoption of QMS practices is recommended.

### 3.5 Clinical Decision Support (CDS) Exemption Analysis

The 21st Century Cures Act, Section 3060 (codified at 21 USC 360j(o)), exempts certain clinical decision support software from regulation as a medical device, provided it meets ALL FOUR criteria:

#### Criterion 1: Not intended to acquire, process, or analyze a medical image or a signal from an in vitro diagnostic device or a pattern or signal from a signal acquisition system

**Analysis**: The system does NOT acquire, process, or analyze:
- Medical images (X-ray, MRI, CT, ultrasound, pathology slides)
- Signals from in vitro diagnostic devices
- Physiological signals (ECG, EEG, pulse oximetry)

The system processes structured clinical data (FHIR resources containing coded diagnoses, lab results, medications) and unstructured clinical text notes (via NLP extraction). It does not interface with imaging or signal acquisition systems.

**Criterion 1 Assessment: MET**

#### Criterion 2: Intended for the purpose of displaying, analyzing, or printing medical information about a patient or other medical information

**Analysis**: The system:
- Analyzes patient clinical data (conditions, labs, medications, demographics) against structured trial eligibility criteria
- Displays per-criterion evaluation results with evidence summaries
- Presents match scores, data completeness assessments, and safety block indicators
- Provides audit trails with evidence fact IDs traceable to source clinical data

All of these functions constitute displaying and analyzing medical information.

**Criterion 2 Assessment: MET**

#### Criterion 3: Intended for the purpose of supporting or providing recommendations to a healthcare professional about prevention, diagnosis, or treatment of a disease or condition

**Analysis**: The system provides recommendations to clinical research professionals (who are healthcare professionals or operate under their supervision) regarding which patients may be eligible for clinical trial enrollment. While clinical trial matching is not treatment per se, FDA guidance has interpreted "treatment" broadly to include clinical management decisions, and trial enrollment is a form of clinical management.

The system explicitly frames its output as "clinical decision support" and recommendations, not autonomous decisions.

**Criterion 3 Assessment: MET**

#### Criterion 4: Intended for the purpose of enabling such healthcare professional to independently review the basis for such recommendations that such software presents so that it is not the intent that such healthcare professional rely primarily on any of such recommendations to make a clinical decision regarding an individual patient without independently reviewing the basis for such recommendations

**Analysis**: This is the critical criterion. The system has been specifically designed to satisfy this requirement:

1. **Mandatory Clinician Review Flag**: Every `PatientEligibility` and `ScreeningResponse` object carries `requires_clinician_review: true` (hardcoded at the schema level in `backend/app/schemas/trial.py`, line 269-272). This flag cannot be disabled.

2. **CDS Disclaimer**: Every result includes the disclaimer: "This screening result is intended as clinical decision support only. A qualified healthcare professional must independently verify all eligibility determinations before any enrollment actions. This system does not make autonomous clinical decisions."

3. **Per-Criterion Evidence Transparency**: Each criterion evaluation (`CriterionResult`) exposes:
   - `evidence_fact_ids`: Direct references to the source clinical facts used
   - `evidence_summary`: Human-readable summary of the evidence (e.g., "Patient has Atopic dermatitis, unspecified (OMOP:12345), recorded 2025-03-15")
   - `confidence_explanation`: Why the system is confident or uncertain (e.g., "High confidence (92%): diagnosis code match on Atopic dermatitis (OMOP:12345)")
   - `status`: PASS / FAIL / NOT_MET / UNKNOWN / POSSIBLE_MATCH with clear definitions
   - `missing_domain`: Identifies which data categories are absent, enabling the reviewer to understand data gaps

4. **Data Completeness Scoring** (`DataCompletenessScore`): Provides:
   - `overall_completeness`: Percentage of evaluable criteria
   - `missing_domains`: List of clinical data categories that are absent
   - `recommendation`: Actionable guidance (e.g., "Obtain laboratory results and medication records to complete eligibility evaluation")

5. **Safety Block Transparency**: When a patient is safety-blocked due to a contraindication, the system provides:
   - `safety_blocked: true` flag
   - `safety_blocked_reasons`: Detailed explanations with evidence fact counts and confidence levels
   - Full audit trail logged to `patient_safety` logger and audit system

6. **Frontend Transparency**: The `MatchExplanation` component (`frontend/src/components/trials/MatchExplanation.tsx`) renders per-criterion evidence with expandable details, color-coded status indicators, confidence badges, and source document links.

7. **No Autonomous Enrollment**: The system creates CANDIDATE enrollment records only; progression from CANDIDATE to ENROLLED requires explicit human action through the enrollment management workflow.

**Criterion 4 Assessment: MET - The system provides comprehensive transparency into the basis for its recommendations, and its design intent is that healthcare professionals independently review this basis before acting.**

### 3.6 CDS Exemption Determination

**DETERMINATION: The system qualifies for the CDS exemption under 21st Century Cures Act Section 520(o)(1).**

All four criteria are satisfied:
1. The system does not acquire, process, or analyze medical images or signals.
2. The system displays and analyzes medical information.
3. The system provides recommendations to healthcare professionals.
4. The system enables independent review of the basis for its recommendations.

**Therefore, the system is NOT a medical device under FDA jurisdiction, provided the intended use remains within the scope described in this document.**

**Critical Caveat**: This exemption is maintained ONLY if:
- The system continues to require mandatory clinician review (Criterion 4 controls remain in place)
- The system does not begin acquiring/processing medical images or signals
- The intended use does not expand to autonomous clinical decision-making
- The CDS disclaimer and `requires_clinician_review` flag remain hardcoded and non-removable
- The system does not market itself as replacing physician judgment

---

## 4. Regulatory Pathway Analysis

### 4.1 Primary Determination: CDS Exempt

Based on the analysis in Section 3, the system qualifies for the CDS exemption. No FDA premarket submission (510(k), De Novo, or PMA) is required.

### 4.2 Documentation Requirements for Maintaining CDS Exemption

Although no FDA submission is required, the organization MUST maintain the following documentation to support the exemption claim if challenged:

| Document | Purpose | Status |
|---|---|---|
| Regulatory Determination (this document) | Demonstrates CDS exemption analysis | Complete |
| Intended Use Statement | Formal scope definition | Complete |
| Software Risk Assessment (FMEA) | Identifies and mitigates failure modes | Complete |
| Change Control Process | Ensures changes do not alter regulatory classification | Complete |
| CDS Criterion 4 Design Documentation | Evidence that independent review is enabled | Covered by this document + code inspection |
| PHI Data Flow Mapping | HIPAA compliance documentation | Complete (CISO-7) |
| User Training Materials | Demonstrates intended use communication | Pending |
| Post-Market Surveillance Plan | Monitors for misuse or unintended clinical reliance | Recommended |

### 4.3 If CDS Exemption Were Lost

If future changes to the system or regulatory guidance cause the CDS exemption to no longer apply, the following pathway analysis would apply:

**IMDRF Category I SaMD** (Inform clinical management, Non-serious significance):

- **FDA Risk Class**: Class I or Class II
- **Likely Pathway**: 510(k) with predicate device, or De Novo if no suitable predicate exists
- **EU MDR Classification**: Class IIa under Rule 11 (software intended to provide information used to take decisions for diagnostic or therapeutic purposes)
- **IEC 62304 Safety Class**: Class A (no contribution to hazardous situation) or Class B (non-serious injury)

**Predicate Device Candidates** (if 510(k)):

| Device | 510(k) Number | Description |
|---|---|---|
| TrialScope (IBM Watson Health) | K192854 | Clinical trial matching using NLP and structured data |
| Tempus Next | K201473 | Genomic and clinical data analysis for trial matching |
| Deep 6 AI | K211256 | EHR-based clinical trial matching |
| Criteria (Medidata) | K193847 | Electronic eligibility screening for clinical trials |

*Note: Predicate numbers are illustrative. Actual predicate analysis would require updated FDA 510(k) database search at time of submission.*

### 4.4 EU MDR Implications

If the system is marketed in the European Union:

- **Classification**: Class IIa under MDR Annex VIII, Rule 11 (software intended to provide information which is used to take decisions with diagnosis or therapeutic purposes is classified as Class IIa)
- **Required**: CE marking, EU Authorized Representative, Technical Documentation per Annex II/III, GSPR compliance, UDI-DI assignment
- **Notified Body**: Required for Class IIa and above
- **Post-Market Surveillance**: Required per Article 83
- **MDCG Guidance**: MDCG 2019-11 (Guidance on Qualification and Classification of Software in Regulation (EU) 2017/745) applies

**Recommendation**: The CDS exemption is a US-specific regulatory concept. EU MDR does not have an equivalent exemption for CDS software. If EU market entry is planned, a full MDR conformity assessment would be required regardless of the US CDS exemption status.

---

## 5. Risk Classification

### 5.1 IMDRF Risk Categorization Matrix

| | **State of Healthcare Decision** | |
|---|---|---|
| **Significance of Information** | Treat or Diagnose | Drive Clinical Management | Inform Clinical Management |
| Critical | IV | III | II |
| Serious | III | II | I |
| Non-Serious | II | I | **I (THIS SYSTEM)** |

**This system: Category I** - Informs clinical management decisions (trial screening) with non-serious significance (a screening error does not directly cause patient harm; it either delays trial access or is caught by mandatory PI review).

### 5.2 IEC 62304 Software Safety Classification

| Class | Definition | Applicability |
|---|---|---|
| **Class A** | No contribution to a hazardous situation | **Most likely classification** - The software provides recommendations that require independent clinician verification; a software failure does not directly create a hazardous situation because the clinician review serves as a safety barrier |
| Class B | Non-serious injury possible | Possible if safety guardrails (exclusion hard stops) are considered part of the safety chain |
| Class C | Death or serious injury possible | Not applicable - trial screening does not directly cause serious injury |

**Recommended Classification: Class A**, with the rationale that mandatory clinician review (Criterion 4 controls) serves as an effective safety barrier between the software output and any patient-affecting action.

**Note on Safety Guardrails**: The system implements patient safety guardrails (CMO-5) where high-confidence exclusion criterion matches trigger hard stops (`safety_blocked: true`) that force the match score to zero and prevent auto-enrollment. These guardrails provide an additional defense layer but are not the primary safety barrier (the primary barrier is clinician review).

---

## 6. Predicate Device Analysis

*This section is provided for completeness in the event that the CDS exemption is lost and a 510(k) pathway is pursued.*

### 6.1 Predicate Identification

A suitable predicate device would need to demonstrate substantial equivalence in:
- **Intended Use**: Clinical trial patient screening/matching
- **Technology**: Software-based analysis of EHR/clinical data against eligibility criteria
- **Performance**: Comparable sensitivity/specificity for eligibility determination

### 6.2 Potential Predicate Devices

| Device | Manufacturer | Function | Key Similarities |
|---|---|---|---|
| TrialScope | IBM Watson Health | NLP-based clinical trial matching from EHR data | NLP extraction, structured criteria matching, CDS output |
| Deep 6 AI | Deep 6 AI | AI-powered clinical trial patient matching | EHR data ingestion, eligibility screening, CDS paradigm |
| Criteria (Medidata) | Medidata Solutions | Electronic eligibility verification | Structured criteria evaluation, site-level screening |
| Tempus Next | Tempus | Clinical and genomic data analysis for trial matching | Multi-modal data integration, trial matching |

### 6.3 Substantial Equivalence Argument (Preliminary)

The system would be considered substantially equivalent to predicate trial matching devices because:
1. Same intended use (clinical trial patient-eligibility screening)
2. Same user population (clinical research coordinators, investigators)
3. Same technology (software analysis of EHR data against structured criteria)
4. Same output (ranked candidate lists requiring clinician review)
5. No new safety or effectiveness questions raised

---

## 7. Recommendations and Action Items

### 7.1 Immediate Actions (Required)

| # | Action | Owner | Priority | Status |
|---|---|---|---|---|
| 1 | Review and approve this regulatory determination with legal counsel | VP Quality + Legal | Critical | Pending |
| 2 | Ensure CDS Criterion 4 controls cannot be disabled via configuration or code change | Engineering Lead | Critical | Implemented (`requires_clinician_review` is hardcoded; CDS_DISCLAIMER is a constant) |
| 3 | Document CDS exemption claim in user-facing terms of use and licensing agreements | Legal | High | Pending |
| 4 | Create user training materials emphasizing that system output requires clinician verification | Clinical Operations | High | Pending |
| 5 | Implement change control process for regulatory-impacting changes | VP Quality | High | Complete (this document set) |

### 7.2 Ongoing Requirements

| # | Requirement | Frequency | Owner |
|---|---|---|---|
| 1 | Review regulatory determination for continued accuracy | Annual or upon significant system change | VP Quality |
| 2 | Monitor FDA guidance updates on CDS exemption scope | Quarterly | Regulatory Affairs |
| 3 | Audit CDS Criterion 4 controls in code | Per release | Engineering Lead |
| 4 | Review false-negative monitoring data for safety signal detection | Monthly | Clinical Operations |
| 5 | Maintain intended use documentation current with product changes | Per release | Product Management |

### 7.3 Risk Mitigation Recommendations

| # | Recommendation | Rationale |
|---|---|---|
| 1 | Do NOT market the system as "AI-powered diagnosis" or "automated enrollment" | Such claims could shift the intended use outside CDS exemption scope |
| 2 | Do NOT remove or make configurable the `requires_clinician_review` flag or CDS disclaimer | Removing these controls would undermine Criterion 4 compliance |
| 3 | Do NOT add medical image analysis or signal processing capabilities without re-evaluating Criterion 1 | Image/signal processing would disqualify the CDS exemption |
| 4 | Maintain the safety hard-stop mechanism for exclusion criteria | Demonstrates responsible safety design even under CDS exemption |
| 5 | Consider voluntary adoption of IEC 62304 Class A lifecycle practices | Strengthens quality posture and provides a foundation if CDS exemption is ever lost |
| 6 | Implement a formal post-market surveillance process | Monitors for unintended clinical reliance on system output |
| 7 | Conduct annual user surveys to verify that clinicians are independently reviewing results | Empirical evidence that Criterion 4 intent is being realized in practice |

### 7.4 EU Market Entry Considerations

If EU market entry is planned:
1. Engage an EU Authorized Representative
2. Engage a Notified Body for Class IIa conformity assessment
3. Prepare Technical Documentation per MDR Annex II
4. Implement a Quality Management System per ISO 13485
5. Conduct a clinical evaluation per MDR Article 61
6. Prepare a Post-Market Surveillance plan per MDR Article 83
7. Register the device in EUDAMED

---

## Appendix A: Regulatory References

| Reference | Description |
|---|---|
| 21st Century Cures Act, Section 3060 | CDS software exemption from device regulation |
| 21 USC 360j(o) | Statutory text of CDS exemption |
| FDA Guidance: CDS Software (Sept 2022) | FDA interpretation of CDS exemption criteria |
| IMDRF/SaMD WG/N10FINAL:2013 | SaMD definition |
| IMDRF/SaMD WG/N12FINAL:2014 | SaMD risk categorization framework |
| IEC 62304:2006/AMD1:2015 | Medical device software lifecycle standard |
| 21 CFR Part 820 | Quality System Regulation |
| EU MDR 2017/745 | European Medical Device Regulation |
| MDCG 2019-11 | EU guidance on software classification |
| ISO 13485:2016 | Medical device QMS standard |
| ISO 14971:2019 | Medical device risk management |

## Appendix B: System Evidence References

| Evidence | Location in Codebase |
|---|---|
| CDS Disclaimer constant | `backend/app/schemas/trial.py` lines 17-22 |
| `requires_clinician_review` field | `backend/app/schemas/trial.py` lines 269-272, 340-343 |
| Safety block hard-stop logic | `backend/app/services/trial_eligibility_service.py` lines 1260-1323 |
| Per-criterion evidence audit trail | `backend/app/services/trial_eligibility_service.py` lines 834-1146 |
| Data completeness scoring | `backend/app/services/trial_eligibility_service.py` lines 1148-1198 |
| Safety block logging | `backend/app/services/trial_eligibility_service.py` lines 1364-1428 |
| False-negative monitoring | `backend/app/services/fn_monitoring_service.py` |
| Pipeline version stamping | `backend/app/core/pipeline_version.py` |
| Data lineage tracking | `backend/app/services/lineage_service.py` |
| Audit logging framework | `backend/app/core/audit.py` |
| Frontend evidence display | `frontend/src/components/trials/MatchExplanation.tsx` |
