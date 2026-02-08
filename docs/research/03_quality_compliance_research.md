# Quality Engineering, Regulatory Compliance, and Clinical Validation for Clinical Trial Matching Software

**Research Date:** February 2026
**Scope:** Regulatory classification, clinical validation, QA testing strategies, privacy/compliance requirements, and industry benchmarks for software that matches patients to clinical trials.

---

## Table of Contents

1. [VP Quality/Regulatory Perspective](#1-vp-qualityregulatory-perspective)
2. [Clinical Informaticist/CMO Perspective](#2-clinical-informaticistcmo-perspective)
3. [QA Engineering Perspective](#3-qa-engineering-perspective)
4. [Compliance Officer Perspective](#4-compliance-officer-perspective)
5. [Industry Benchmarks: What Leaders Do](#5-industry-benchmarks-what-leaders-do)
6. [Recommendations for Our Platform](#6-recommendations-for-our-platform)

---

## 1. VP Quality/Regulatory Perspective

### 1.1 Is Clinical Trial Matching Software a Medical Device?

The regulatory classification of clinical trial matching software depends on its intended use, the nature of its outputs, and how much clinical autonomy it exercises. The answer is nuanced and jurisdiction-dependent.

#### FDA / United States

**21st Century Cures Act CDS Exemption (Section 3060(a))**

The Cures Act amended the FD&C Act to exempt certain Clinical Decision Support (CDS) software from device regulation if it meets ALL four criteria:

1. **Criterion 1:** Does not acquire, process, or analyze medical images, signals from an IVD, or patterns from a signal acquisition system
2. **Criterion 2:** Displays, analyzes, or prints medical information about a patient or other medical information
3. **Criterion 3:** Is intended for supporting or providing recommendations to a healthcare professional (HCP)
4. **Criterion 4:** Provides sufficient information about the basis for recommendations so the HCP does not rely primarily on the software's recommendations

**Analysis for Trial Matching Software:**

A clinical trial matching system that presents candidate trials to a clinician with transparent reasoning (showing which criteria matched and which didn't) likely qualifies for the CDS exemption under Cures Act Section 520(o) -- IF:
- The clinician retains full autonomy to accept or reject matches
- The system shows its reasoning (which eligibility criteria matched, data sources used)
- It does not make time-critical decisions
- It is intended for HCP use, not direct patient use

**Key risk:** If the software autonomously enrolls patients, screens without clinician review, or is marketed directly to patients for self-screening, it likely falls under SaMD regulation.

**Important limitation (2026 FDA update):** In January 2026, the FDA broadened interpretations of exempt CDS, but simultaneously confirmed that time-critical CDS does NOT qualify for exemption because clinicians may not have adequate time to independently evaluate the reasoning. Trial matching is generally not time-critical, which favors exemption.

**SaMD Classification (If Regulated)**

If the software IS classified as SaMD, the FDA uses the IMDRF framework to determine risk class based on:
- **Significance of information:** Does it treat/diagnose, drive clinical management, or merely inform?
- **Healthcare situation:** Critical, serious, or non-serious condition?

Trial matching software that informs clinical management for serious conditions (e.g., oncology) would likely be **Class II** (moderate risk), requiring a 510(k) or De Novo pathway.

#### EU MDR (Medical Device Regulation 2017/745)

The EU takes a more stringent approach than the FDA:

**MDR Rule 11** governs standalone software classification. Key provisions:
- Software intended to provide information used to make decisions with diagnosis or therapeutic purposes is classified as **Class IIa minimum**
- If decisions could cause death or irreversible deterioration, classification rises to **Class III**
- The EU does NOT have a broad CDS exemption equivalent to the Cures Act

**Practical impact:** Most clinical decision support software, including trial matching, is classified as **at least Class IIa** under EU MDR, requiring Notified Body involvement. This is significantly more burdensome than the US pathway.

**MDCG 2019-11 Guidance** provides the classification decision tree based on:
1. Significance of information to the healthcare situation
2. State of the patient condition (critical vs. serious vs. non-serious)

A trial matching system for oncology patients under EU MDR would likely be **Class IIa or IIb**, depending on whether incorrect matching could directly impact treatment decisions.

### 1.2 Applicable Standards and Frameworks

#### IEC 62304: Medical Device Software Lifecycle

If regulated as SaMD, IEC 62304 compliance is required. The standard defines three software safety classes:
- **Class A:** No injury or damage possible
- **Class B:** Non-serious injury possible
- **Class C:** Death or serious injury possible

Trial matching software would likely be **Class B** (incorrect matching could lead to inappropriate trial enrollment, but the clinical team provides a safety layer before actual enrollment).

Key IEC 62304 requirements:
- Software development planning
- Software requirements analysis
- Software architectural design
- Detailed design and unit implementation
- Software integration and integration testing
- Software system testing
- Software release
- Software maintenance
- Software configuration management
- Software problem resolution

#### ISO 13485: Quality Management System

As of February 2, 2026, the FDA's updated QMSR requirements align with ISO 13485, making compliance a legal requirement for regulated medical device software in the US. Key requirements:
- Documented QMS procedures
- Design and development controls
- Risk management integration
- Traceability (requirements to design to verification to validation)
- Document control and records management
- CAPA (Corrective and Preventive Action) system
- Management review
- Supplier and purchasing controls

#### ISO 14971: Risk Management

The foundational risk management standard for medical devices. Requires:
- Systematic hazard identification
- Risk estimation and evaluation
- Risk control measures
- Evaluation of residual risk
- Production and post-production monitoring

Common risk analysis tools applicable to trial matching:
- **FMEA (Failure Mode and Effects Analysis):** For systematic analysis of NLP extraction failures, mapping errors, eligibility logic bugs
- **FTA (Fault Tree Analysis):** For top-down analysis of critical failure scenarios (e.g., "wrong patient enrolled in trial")
- **HAZOP (Hazard and Operability Study):** For analyzing deviations in data flow

Note: FMEA alone does NOT satisfy ISO 14971 requirements -- it must be part of a broader risk management process.

#### GAMP 5 (2nd Edition) / FDA Computer Software Assurance

GAMP 5 2nd Edition (July 2022) provides a risk-based framework for software validation:
- Emphasizes critical thinking over checkbox documentation
- Supports agile/iterative development methods
- Categories software by configurability and risk
- Aligns with FDA's CSA (Computer Software Assurance) draft guidance

The FDA's CSA guidance (2022) shifts from traditional CSV (Computer System Validation) to a more risk-proportionate approach, prioritizing testing over documentation for lower-risk components.

### 1.3 Recommended Regulatory Strategy

**Phase 1 (Current):** Position as CDS-exempt under Cures Act
- Ensure all four CDS criteria are met in product design
- Document intended use carefully: "clinical decision support for healthcare professionals"
- Maintain transparency of matching logic (Criterion 4 compliance)
- Keep clinician in the loop for all matching decisions
- Prepare a regulatory determination file documenting exemption rationale

**Phase 2 (If Market Demands):** Prepare for SaMD classification
- Implement IEC 62304 Class B software lifecycle
- Build ISO 13485-compliant QMS
- Conduct ISO 14971 risk management
- Prepare technical documentation for 510(k) or De Novo

**Phase 3 (EU Expansion):** MDR Class IIa/IIb pathway
- Engage Notified Body early
- Full technical documentation per MDR Annex II/III
- Clinical evaluation per MEDDEV 2.7/1 Rev. 4
- Post-market surveillance plan

---

## 2. Clinical Informaticist/CMO Perspective

### 2.1 Clinical Validation of NLP Extraction for Trial Matching

#### Key Accuracy Metrics

Clinical NLP validation for trial matching requires measuring:

| Metric | Definition | Target | Why It Matters |
|--------|-----------|--------|---------------|
| **Sensitivity/Recall** | % of truly eligible patients identified | >90% | Missing eligible patients (false negatives) |
| **Specificity** | % of truly ineligible patients correctly excluded | >85% | Wasting clinician time on false positives |
| **Positive Predictive Value (PPV)** | % of flagged patients who are truly eligible | >50% | Screening efficiency |
| **Negative Predictive Value (NPV)** | % of excluded patients who are truly ineligible | >95% | Patient safety and missed opportunities |
| **F1 Score** | Harmonic mean of precision and recall | >0.80 | Overall balance |
| **Inter-annotator Agreement** | Cohen's kappa for human reviewers | >0.75 | Reliability of gold standard |

#### Published Benchmarks from the Literature

**LLM-Based Systems:**
- GPT-4 on n2c2 2018 dataset: accuracy 0.87, sensitivity 0.85, specificity 0.89, micro-F1 0.86
- TrialGPT (NIH/NLM): 87.3% accuracy on 1,015 patient-criterion pairs; >90% recall using <6% of initial trial collection
- TrialGPT reduces screening time by 42.6%

**Hybrid NLP/Rules-Based Systems:**
- Colorectal cancer CTPM tool: 94% retrospective accuracy, 88% prospective accuracy, 100% sensitivity
- 10x reduction in chart review workload, 41% reduction in screening time

**Traditional NLP Systems:**
- IBM Watson for Oncology trial matching: PPV up to 76.5%
- Historical range across studies: PPV 13%-63% (highly variable)

**OMOP Concept Mapping:**
- Best models: 96.5% accuracy for common drugs, 83.0% for random drugs
- LLM-based query generation: hallucination rates of 21%-50% require careful validation

#### Risk Analysis: False Positives vs. False Negatives

**False Positives (Flagging ineligible patients as eligible):**
- **Patient safety risk:** LOW-MODERATE. Clinical team reviews before enrollment, providing a safety net
- **Operational cost:** HIGH. Wastes clinician screening time, reduces trust in the system
- **Consequence:** Increased screening burden, potential for "alert fatigue" if too frequent
- **Acceptable rate:** Industry standard allows PPV as low as 50% (i.e., half of flagged patients may not be eligible after full review)

**False Negatives (Missing eligible patients):**
- **Patient safety risk:** MODERATE-HIGH. Patients miss potentially beneficial trial opportunities
- **Ethical concern:** Equity implications if certain populations are systematically missed
- **Business impact:** Reduced enrollment rates, slower trial completion
- **Acceptable rate:** Should be <10% (sensitivity >90%), especially for rare diseases or last-line therapies

**Asymmetry insight:** In trial matching, false negatives are generally MORE harmful than false positives because:
1. Missed eligible patients cannot be recovered (the opportunity is lost)
2. False positives are caught by downstream clinical review
3. For serious/life-threatening conditions, missing a trial option is a meaningful harm

### 2.2 Clinical Validation Study Design

#### Recommended Validation Studies

**Study 1: Retrospective Chart Review Validation**
- **Design:** Compare system matches against manual chart review by clinical experts on a retrospective cohort
- **Population:** 500-1,000 patients with known trial eligibility status
- **Gold standard:** Board-certified oncologist manual review
- **Metrics:** Sensitivity, specificity, PPV, NPV, F1, AUC-ROC
- **Subgroup analysis:** By cancer type, stage, biomarker status, demographics

**Study 2: Prospective Concordance Study**
- **Design:** Run system in parallel with standard-of-care screening for 6-12 months
- **Measure:** Concordance between system recommendations and clinician decisions
- **Track:** Cases where system identified eligible patients missed by standard workflow
- **Outcome:** Time-to-identification, enrollment conversion rate

**Study 3: Safety Outcome Monitoring**
- **Design:** Track outcomes of patients enrolled through system-assisted matching
- **Metrics:** Screen failure rate, protocol deviation rate, adverse event rate vs. standard screening cohort
- **Duration:** 12-24 months post-implementation
- **Primary concern:** Screen failure rate should not increase vs. baseline

**Study 4: Bias and Equity Audit**
- **Design:** Stratified analysis of system performance across demographic groups
- **Variables:** Age, sex, race/ethnicity, language, insurance status, rural vs. urban
- **Goal:** Ensure no systematic bias in trial identification
- **Regulatory requirement:** FDA and EU MDR both increasingly require algorithmic fairness assessment

#### Gold Standard Corpus Development

Building a validated gold standard corpus for NLP evaluation requires:
1. **Annotation guidelines:** Detailed, domain-specific annotation schema developed with clinical SMEs
2. **Multiple annotators:** Minimum 2 independent annotators per document, ideally 3
3. **Inter-annotator agreement:** Measure Cohen's kappa; target >0.75 for substantial agreement
4. **Adjudication process:** Expert review of disagreements to produce final gold labels
5. **Corpus size:** Minimum 200-500 annotated documents for initial validation; 1,000+ for production benchmarks
6. **Regular refresh:** Gold standard must be updated as clinical terminology and trial criteria evolve

### 2.3 Ongoing Clinical Monitoring

**Performance dashboards should track:**
- Match accuracy by trial type and therapeutic area
- Screen failure rate trends
- Time from patient identification to enrollment
- Clinician override rates (system recommended, clinician rejected)
- Patient diversity metrics for matched cohorts
- NLP extraction confidence scores and distribution over time

---

## 3. QA Engineering Perspective

### 3.1 Testing Strategy for Healthcare NLP Pipelines

#### Testing Pyramid for Clinical NLP

```
                    /\
                   /  \  End-to-End Clinical Validation
                  /    \  (prospective studies, chart review)
                 /------\
                /        \  Integration Tests
               /          \  (pipeline-level, FHIR/OMOP round-trip)
              /------------\
             /              \  Component Tests
            /                \  (NER, assertion, mapping, eligibility logic)
           /------------------\
          /                    \  Unit Tests
         /                      \  (individual functions, edge cases)
        /--------------------------\
```

#### Unit Testing Layer

**NLP Component Tests:**
- Tokenizer: boundary cases, abbreviations, medical shorthand
- NER (Named Entity Recognition): entity boundary detection, nested entities
- Assertion detection: negation ("no evidence of"), hypothetical ("if patient develops"), family history
- Temporal extraction: relative dates, date ranges, ongoing vs. resolved
- Section detection: clinical notes section boundaries (HPI, Assessment, Plan)

**OMOP Mapping Tests:**
- Exact match verification against known concept-term pairs
- Synonym resolution (e.g., "heart attack" -> SNOMED 22298006 "Myocardial infarction")
- Ambiguity handling (e.g., "cold" -> condition vs. temperature)
- Deprecated concept detection and migration
- Vocabulary version compatibility

**Eligibility Logic Tests:**
- Boolean logic evaluation for inclusion/exclusion criteria
- Numeric range comparisons (lab values, age)
- Temporal constraint evaluation (e.g., "within 6 months of diagnosis")
- Compound criteria (AND/OR/NOT combinations)
- Edge cases: missing data, ambiguous values, conflicting information

#### Integration Testing Layer

**Pipeline Integration Tests:**
- Document ingestion through NLP extraction through OMOP mapping through fact building through eligibility evaluation
- FHIR resource import/export round-trip validation
- Data transformation fidelity at each pipeline stage
- Error propagation: verify that upstream errors are handled gracefully downstream

**OMOP Mapping Regression Tests:**
- Maintain a curated regression test suite of 500+ known term-to-concept mappings
- Run on every vocabulary update (SNOMED, RxNorm, LOINC releases)
- Track mapping stability: what percentage of existing mappings changed?
- Flag new unmapped terms for review

#### Golden Dataset Testing

**Structure of golden test datasets:**

```
golden_dataset/
  annotations/
    clinical_notes/     # 200+ annotated clinical notes
    lab_reports/        # 100+ annotated lab reports
    pathology/          # 100+ annotated pathology reports
  eligibility/
    trial_criteria/     # 50+ trial criteria with expected parse trees
    patient_profiles/   # 200+ patient profiles with known eligibility
    edge_cases/         # 100+ edge cases (ambiguous, missing data)
  omop_mapping/
    known_mappings/     # 500+ curated term-to-concept mappings
    regression_set/     # Version-tracked regression corpus
```

**Refresh cadence:** Quarterly review and expansion of golden datasets.

### 3.2 Regression Testing OMOP Mappings

OMOP vocabulary updates (SNOMED CT, RxNorm, LOINC, ICD-10) occur regularly and can break existing mappings.

**Regression testing strategy:**
1. **Snapshot baseline:** Capture all active mappings before vocabulary update
2. **Apply update:** Load new vocabulary version
3. **Diff analysis:** Compare new mappings against baseline
4. **Categorize changes:**
   - New concepts added (low risk)
   - Concepts deprecated/retired (HIGH risk -- existing data may reference them)
   - Concept relationships changed (MEDIUM risk)
   - Concept descriptions changed (LOW risk)
5. **Impact assessment:** For each deprecated concept, trace all ClinicalFacts and eligibility rules that reference it
6. **Migration plan:** Map deprecated concepts to successors
7. **Verification:** Re-run golden dataset tests after migration

**Automated checks:**
- No orphaned concept references in ClinicalFacts
- All eligibility criteria resolve to valid OMOP concepts
- Mapping coverage: % of extracted terms successfully mapped (target >95%)
- Mapping confidence score distribution (flag downward trends)

### 3.3 Data Drift Detection

Data drift monitoring is critical for maintaining clinical NLP accuracy over time.

**Types of drift to monitor:**

| Drift Type | Description | Detection Method |
|-----------|-------------|-----------------|
| **Input distribution drift** | Changes in patient population, note types, clinical vocabulary | Statistical tests on feature distributions (KS test, PSI) |
| **Concept drift** | Changes in the relationship between inputs and correct outputs | Performance monitoring against periodic gold standard reviews |
| **Upstream data drift** | Changes in EHR systems, data formats, coding practices | Schema validation, format checks, source profiling |
| **Vocabulary drift** | New medical terms, drug names, biomarkers | Unmapped term rate monitoring, new term extraction |
| **Temporal drift** | Seasonal patterns, pandemic effects, guideline changes | Time-series analysis of key metrics |

**Monitoring implementation:**
- Track NLP confidence score distributions over time (weekly aggregates)
- Monitor unmapped term rates (should remain <5%)
- Compare extraction entity type distributions month-over-month
- Alert on >2 standard deviation shifts in any monitored metric
- Quarterly re-evaluation against updated gold standard subset

**Real-world example:** ML models trained on pre-COVID-19 data showed substantial performance degradation during the pandemic due to shifts in patient populations and clinical patterns. Healthcare NLP systems must be designed for continuous monitoring.

### 3.4 Testing Trial Eligibility Logic

**Eligibility criteria are complex boolean expressions. Testing strategy:**

**Formal verification approaches:**
- Model eligibility criteria as first-order predicate logic
- Use property-based testing (hypothesis-style) to generate patient profiles
- Verify logical consistency: no criteria set should be simultaneously satisfiable and unsatisfiable
- Test boundary conditions for all numeric criteria

**Test categories:**
1. **Clearly eligible patients:** All inclusion criteria met, no exclusion criteria triggered
2. **Clearly ineligible patients:** Key inclusion criteria unmet
3. **Boundary cases:** Values at exact cutoff points (e.g., age = 18 exactly)
4. **Missing data cases:** What happens when a required data point is absent?
5. **Conflicting data cases:** Multiple sources provide different values
6. **Temporal edge cases:** Criteria with time-dependent conditions
7. **Complex boolean cases:** Deeply nested AND/OR/NOT structures

**Automated test generation:**
- Parse trial criteria into structured logic trees
- Generate test patient profiles that exercise each branch
- Ensure 100% branch coverage for eligibility logic
- Track criteria parsing accuracy: target >89% boolean logic accuracy at criterion level (per published benchmarks)

### 3.5 FDA Software Testing Guidance Alignment

Key testing requirements from FDA guidance:
- **Verification:** Confirm software meets specified requirements (unit tests, integration tests)
- **Validation:** Confirm software meets user needs and intended uses (clinical validation studies)
- **Traceability matrix:** Link requirements to design to tests to results
- **Test documentation:** Test plans, test cases, test results, defect reports
- **Risk-based test coverage:** Higher coverage for higher-risk components

---

## 4. Compliance Officer Perspective

### 4.1 HIPAA Compliance for Trial Matching

#### Legal Basis for Using Patient Data

Patient EHR data can be used for trial matching screening under several HIPAA provisions:

**Preparatory to Research (45 CFR 164.512(i)(1)(ii)):**
- Permits use of PHI to identify potentially eligible patients
- **Critical limitation:** PHI may NOT leave the covered entity's premises under this provision
- Researcher must be an employee or workforce member of the covered entity
- Data cannot be disclosed to external parties (e.g., sponsors)

**IRB/Privacy Board Waiver of Authorization:**
- Required if PHI will be disclosed outside the covered entity
- Must demonstrate that research cannot practicably be conducted without the waiver
- Must establish that the PHI requested is the minimum necessary
- IRB must document approval per 45 CFR 164.512(i)

**Patient Authorization (45 CFR 164.508):**
- Most protective pathway: patient directly authorizes use of their data
- Required if data leaves the covered entity for external matching
- Must specify the purpose, types of PHI, and recipients

**Minimum Necessary Standard:**
- Applies to all research uses and disclosures
- Only the minimum PHI needed for screening should be accessed
- Technical controls should enforce data minimization
- Role-based access controls aligned with screening workflow

#### De-identification Approaches

**Safe Harbor Method (18 identifiers removed):**
- Remove all 18 specified identifiers
- Suitable for aggregate analytics and reporting
- May limit utility for individual patient matching

**Expert Determination Method:**
- Qualified statistical expert certifies very low re-identification risk
- More flexible than Safe Harbor
- Must be documented and periodically reviewed
- Methods must be generally accepted and reproducible

**Limited Data Set with Data Use Agreement:**
- Removes direct identifiers but retains dates and zip codes
- Requires formal Data Use Agreement
- Suitable for multi-site screening with appropriate controls

### 4.2 IRB Considerations

**When IRB Review is Required:**
- Any clinical trial recruitment activity that goes beyond basic directory listings
- Use of patient data for eligibility screening (even if preparatory)
- Electronic outreach to potentially eligible patients
- Any materials displayed to patients about trial opportunities

**Key IRB Compliance Requirements:**
- Informed consent documents must be at 8th-grade reading level or lower
- Website recruitment materials require IRB approval
- Electronic consent (eConsent) platforms must meet 21 CFR Part 11 requirements
- Patient-facing screening questionnaires need IRB review
- Compensation/incentive language requires review

**Common IRB Concerns with Automated Matching:**
- Patient autonomy: is the system creating undue pressure to enroll?
- Privacy: are patients being contacted based on sensitive diagnoses without explicit consent?
- Equity: is the system introducing bias in who gets identified?
- Transparency: do patients understand how they were identified?

### 4.3 Audit Trail Requirements

#### 21 CFR Part 11 Compliance

The October 2024 finalized FDA guidance on electronic records requires:

**Technical Requirements:**
- Secure, computer-generated, time-stamped audit trails
- Record date/time of all create, modify, and delete operations
- Previously recorded information must NOT be obscured by changes
- Audit trail must be independent of system operators
- No user (including administrators) should modify audit trails
- Retention period must equal or exceed the underlying record retention

**Operational Requirements:**
- Written policies and procedures for system use
- Authority checks and access controls
- Training records for all system users
- System validation documentation
- Backup and recovery procedures

**For Trial Matching Systems, audit trails must capture:**
- Every patient screening event (who was screened, when, against which trial)
- Every eligibility determination (result, reasoning, confidence scores)
- Every clinician review action (approved, rejected, modified)
- Every data access event (who accessed which patient data, when)
- All system configuration changes (eligibility criteria updates, NLP model changes)
- All data imports and exports

### 4.4 Privacy Laws Beyond HIPAA

#### GDPR (EU/EEA)

If processing data of EU residents:
- **Lawful basis:** Likely requires explicit consent or legitimate interest assessment
- **Data Protection Impact Assessment (DPIA):** Required for large-scale health data processing
- **Data minimization:** Only process data necessary for trial matching
- **Right to erasure:** Must support patient data deletion requests
- **Cross-border transfer:** Requires adequacy decisions or Standard Contractual Clauses
- **Data Protection Officer:** Required for organizations processing health data at scale

#### Washington My Health My Data Act (MHMDA)

Effective March 31, 2024:
- Requires **opt-in consent** (GDPR-level) for collection, use, and disclosure of consumer health data
- **Separate consent** required for sharing health data with third parties
- Applies to ANY entity collecting health data of Washington consumers -- no revenue or volume thresholds
- **Private right of action** -- individuals can sue directly
- **Clinical trial carve-out:** Data collected under the Common Rule (45 CFR 46) may be exempt
- Per-se violation of Washington CPA

#### Connecticut Data Privacy Act (Health Data Amendments)

- Governs "consumer health data" with specific consent requirements
- Geofencing restrictions around healthcare facilities
- Right to delete covered health information

#### Nevada SB 370

Effective March 31, 2024:
- Broad restrictions on collection, use, and sale of consumer health data
- Requires opt-in consent
- Privacy policy requirements
- No private right of action (AG enforcement only)

#### CCPA/CPRA (California)

- Classifies health data as "sensitive personal information"
- Requires opt-in consent for secondary use
- Right to delete, right to know, right to correct
- Private right of action for data breaches

#### Practical Compliance Strategy

Given the patchwork of state laws:
1. **Default to highest standard:** Design for GDPR/MHMDA-level consent (opt-in for all health data processing)
2. **Maintain consent records:** Track what each patient consented to, when, and through what mechanism
3. **Implement data minimization:** Only access and retain the minimum PHI needed for screening
4. **Support deletion rights:** Build "right to be forgotten" capabilities from the start
5. **Geographic awareness:** Track patient location to apply appropriate state law requirements
6. **Regular legal review:** Privacy law is evolving rapidly; quarterly compliance reviews recommended

### 4.5 Security Certifications

**Recommended certification roadmap:**

| Certification | Purpose | Priority | Cost Range | Timeline |
|--------------|---------|----------|------------|----------|
| **SOC 2 Type II** | Baseline security attestation | HIGH (Year 1) | $20K-$100K | 6-12 months |
| **HITRUST r2** | Healthcare gold standard | MEDIUM (Year 2) | $60K-$200K | 12-18 months |
| **ISO 27001** | International security standard | MEDIUM (Year 2-3) | $30K-$80K | 9-15 months |
| **FedRAMP** | US government contracts | LOW (Year 3+) | $250K-$1M+ | 12-24 months |

**Industry perspective:** HIPAA is the legal floor, SOC 2 is the baseline expectation, and HITRUST is the gold standard for healthcare SaaS. Enterprise health systems increasingly require HITRUST r2 certification for vendor selection.

---

## 5. Industry Benchmarks: What Leaders Do

### 5.1 Flatiron Health

**Approach to trial matching quality:**
- Structured + unstructured data processing via ML pipelines
- 24-hour data recency for patient matching
- Multi-year FDA collaboration (since 2016) on real-world data quality
- Fit-for-purpose assessments including quantitative feasibility outputs
- Access to 2.2M+ active patient records across 280+ medical practices
- Regulatory strategy: Positioned as real-world evidence platform supporting FDA regulatory submissions, not as SaMD
- Key differentiator: Deep FDA partnership validates data quality approaches

**Quality practices:**
- Abstraction and curation infrastructure for EHR data
- Human-in-the-loop validation for all clinical data extraction
- Periodic data quality audits
- Published validation studies in peer-reviewed journals

### 5.2 Tempus AI (including Deep 6 AI)

**Approach to trial matching quality:**
- TIME Trial Program: screens >1 million patients daily via EMR integrations
- Acquired Deep 6 AI (March 2025) adding 30M+ patients across 750+ provider sites
- Patient Query tool: generative AI reads unstructured clinical data and assigns relevance scores
- Published accuracy: 94.39% overall accuracy across 196 reviewed queries (range: 84.62%-100%)
- Nurses review AI-identified matches before sharing with TIME network sites

**Quality practices:**
- Human-in-the-loop: Nurse review layer between AI screening and site notification
- Automated pre-screening with measured efficiency: screens out ~72% of ineligible patients
- Operational metrics tracked: evaluated 9,875 patients across 8 trials in published study
- Combined genomic + clinical data matching (NGS testing integration)

### 5.3 Deep 6 AI (now Tempus)

**Pre-acquisition approach:**
- NLP + ML analysis of structured (ICD-10, demographics) and unstructured (physician notes, pathology reports, lab results) EHR data
- Integrated with 750+ provider site locations
- Used Spark NLP (John Snow Labs) for clinical NLP processing
- Focus on de-risking clinical trials through accurate matching

### 5.4 Medidata (Dassault Systemes)

**Approach:**
- Positions AI as built on "regulatory-grade data"
- Emphasizes transparency, security, and ethical rigor in model development
- Integrated CTMS/EDC platform with trial matching capabilities
- Leverages large historical trial dataset for matching intelligence

### 5.5 Common Patterns Across Industry Leaders

| Practice | Flatiron | Tempus | Deep 6 | Medidata |
|----------|----------|--------|--------|----------|
| Human-in-the-loop review | Yes | Yes (nurses) | Yes | Yes |
| Published validation metrics | Yes | Yes | Yes | Limited |
| Structured + unstructured data | Yes | Yes | Yes | Yes |
| FDA engagement/collaboration | Deep partnership | Regulatory-grade claims | Via Tempus | Regulatory-grade claims |
| Continuous monitoring | Yes | Yes | Yes | Yes |
| Multi-source data fusion | EHR + genomic | EHR + genomic + NGS | EHR | Trial + EHR |

**Universal finding:** Every major player maintains a human-in-the-loop validation layer. No company relies solely on automated matching for patient enrollment decisions.

---

## 6. Recommendations for Our Platform

### 6.1 Immediate Priorities (0-6 months)

#### Regulatory Positioning
- [ ] Draft a regulatory determination document establishing CDS exemption rationale
- [ ] Ensure all user-facing outputs include transparent reasoning (Criterion 4)
- [ ] Add prominent "clinician review required" labeling to all match outputs
- [ ] Document intended use statement: "clinical decision support for healthcare professionals"

#### Clinical Validation Foundation
- [ ] Build initial golden dataset: 200+ annotated clinical notes, 50+ trial criteria, 200+ patient profiles with known eligibility
- [ ] Establish inter-annotator agreement protocol (minimum 2 annotators per document, target kappa >0.75)
- [ ] Implement retrospective validation study design for first therapeutic area (oncology recommended)
- [ ] Define and instrument key performance metrics: sensitivity, specificity, PPV, NPV, F1

#### QA Infrastructure
- [ ] Implement OMOP mapping regression test suite (500+ curated mappings)
- [ ] Build eligibility logic test framework with property-based test generation
- [ ] Establish golden dataset CI/CD integration (tests run on every PR)
- [ ] Implement NLP confidence score monitoring and alerting

#### Compliance Foundations
- [ ] Implement comprehensive audit trails meeting 21 CFR Part 11 requirements
- [ ] Build consent management system supporting opt-in at GDPR/MHMDA level
- [ ] Implement role-based access controls aligned with HIPAA minimum necessary
- [ ] Establish data retention and deletion policies

### 6.2 Medium-Term Priorities (6-18 months)

#### Validation Studies
- [ ] Complete retrospective chart review validation (n=500+)
- [ ] Launch prospective concordance study at pilot site(s)
- [ ] Conduct algorithmic fairness/bias audit across demographics
- [ ] Publish validation results in peer-reviewed venue

#### Quality System
- [ ] Implement risk management framework per ISO 14971 methodology
- [ ] Build FMEA for critical failure modes in the screening pipeline
- [ ] Establish CAPA (Corrective and Preventive Action) system
- [ ] Begin SOC 2 Type II audit preparation

#### Monitoring
- [ ] Deploy data drift detection for NLP inputs and outputs
- [ ] Implement vocabulary drift monitoring (unmapped term rate tracking)
- [ ] Build clinician override tracking dashboard
- [ ] Establish quarterly gold standard refresh cadence

### 6.3 Long-Term Priorities (18-36 months)

#### Certifications
- [ ] Achieve SOC 2 Type II attestation
- [ ] Begin HITRUST r2 assessment
- [ ] If EU market entry planned, engage Notified Body for MDR Class IIa pathway

#### Advanced Validation
- [ ] Safety outcome monitoring study (12-24 months post-implementation)
- [ ] Multi-site validation across diverse healthcare systems
- [ ] Therapeutic area expansion with per-area validation studies
- [ ] Continuous learning pipeline with prospective performance monitoring

#### Regulatory Maturity
- [ ] IEC 62304 Class B software lifecycle (if SaMD pathway pursued)
- [ ] ISO 13485 QMS implementation (if SaMD pathway pursued)
- [ ] FDA pre-submission meeting (if 510(k)/De Novo pathway pursued)

### 6.4 Risk Register (Top Clinical Risks)

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| False negative: eligible patient missed for life-threatening condition | HIGH | MEDIUM | Sensitivity >90%, human fallback screening, continuous monitoring |
| False positive: ineligible patient enrolled, experiences adverse event | HIGH | LOW | Clinician review gate, multi-step enrollment workflow |
| NLP extraction error: wrong lab value extracted, incorrect eligibility | HIGH | MEDIUM | Confidence thresholds, human verification for borderline cases |
| OMOP mapping drift: vocabulary update breaks existing mappings | MEDIUM | HIGH | Regression test suite, automated migration, pre-deployment testing |
| Data drift: model performance degrades silently | MEDIUM | HIGH | Drift monitoring, quarterly gold standard re-evaluation |
| Bias: systematic under-identification of minority populations | HIGH | MEDIUM | Fairness audit, stratified performance metrics, diverse training data |
| Privacy breach: PHI exposed through matching pipeline | HIGH | LOW | Encryption, access controls, audit trails, SOC 2/HITRUST |
| Regulatory reclassification: FDA determines SaMD status | MEDIUM | LOW | Proactive CDS exemption documentation, IEC 62304 readiness plan |

---

## Appendix A: Key Regulatory References

- FDA SaMD Clinical Evaluation Guidance (2017): https://www.fda.gov/regulatory-information/search-fda-guidance-documents/software-medical-device-samd-clinical-evaluation
- FDA CDS Final Guidance (2022): https://www.federalregister.gov/documents/2022/09/28/2022-20993/clinical-decision-support-software-guidance
- 21st Century Cures Act Section 3060(a): Section 520(o) of the FD&C Act
- IEC 62304:2006/A1:2015: Medical device software lifecycle processes
- ISO 13485:2016: Medical devices QMS requirements
- ISO 14971:2019: Risk management for medical devices
- 21 CFR Part 11: Electronic records and signatures
- HIPAA Privacy Rule: 45 CFR Parts 160 and 164
- EU MDR 2017/745: Medical Device Regulation
- MDCG 2019-11: Guidance on qualification and classification of software
- GAMP 5 2nd Edition (2022): ISPE guide for GxP computerized systems
- FDA CSA Draft Guidance (2022): Computer Software Assurance

## Appendix B: Key Research References

- TrialGPT (NIH/NLM): Matching patients to clinical trials with LLMs (Nature Communications, 2024)
- n2c2 2018 Challenge: Clinical trial eligibility NLP benchmarks
- CTPM Tool Validation: 94% retrospective accuracy for colorectal cancer trial matching (JCO Clinical Cancer Informatics, 2025)
- Data Drift in Medical ML: Implications and remedies (PMC, 2023)
- OMOP NLP Mapping: Sentence transformer approaches for EHR schema mapping (PMC, 2025)
- Systematic Literature Review on Clinical Trial Eligibility Matching (arXiv, 2025)

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **SaMD** | Software as a Medical Device -- software intended to be used for medical purposes without being part of a hardware medical device |
| **CDS** | Clinical Decision Support -- software that provides clinicians with knowledge and patient-specific information to enhance health care |
| **OMOP CDM** | Observational Medical Outcomes Partnership Common Data Model -- standardized data model for observational health data |
| **NER** | Named Entity Recognition -- NLP task of identifying and classifying named entities in text |
| **PPV** | Positive Predictive Value -- probability that a positive test result is truly positive |
| **NPV** | Negative Predictive Value -- probability that a negative test result is truly negative |
| **FMEA** | Failure Mode and Effects Analysis -- systematic technique for failure analysis |
| **CAPA** | Corrective and Preventive Action -- systematic approach to investigating and correcting nonconformities |
| **PHI** | Protected Health Information -- individually identifiable health information under HIPAA |
| **MHMDA** | My Health My Data Act -- Washington state consumer health data privacy law |
| **HITRUST** | Health Information Trust Alliance -- healthcare-specific security certification framework |
| **QMS** | Quality Management System -- formalized system documenting processes, procedures, and responsibilities |
