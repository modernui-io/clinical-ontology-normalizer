# Intended Use / Indications for Use Statement

**Document ID:** VP-Quality-1-IUS
**Version:** 1.0
**Last Updated:** 2026-02-08
**Classification:** CONFIDENTIAL - Internal Use Only
**Owner:** VP of Quality / Regulatory Affairs
**Approval Status:** DRAFT - Pending Legal and Regulatory Review

---

## 1. Intended Use

The Clinical Ontology Normalizer Trial Matching Module is a software-based clinical decision support (CDS) tool intended to assist qualified clinical research personnel in identifying patients who may be potentially eligible for clinical trial enrollment.

The system ingests patient clinical data from electronic health records (EHRs) and health information exchanges (HIEs) via FHIR R4 interfaces, extracts and normalizes clinical concepts using natural language processing (NLP) and standard medical vocabularies (OMOP, ICD-10-CM, SNOMED CT, LOINC, RxNorm), and screens patients against structured clinical trial eligibility criteria to produce ranked candidate lists with per-criterion evidence summaries.

The system is intended to support, not replace, the clinical judgment of qualified healthcare professionals. All eligibility determinations produced by the system are preliminary recommendations that require independent verification by a qualified clinical research professional before any patient enrollment action is taken.

---

## 2. Indications for Use

### 2.1 Clinical Application

The system is indicated for use as a clinical decision support tool in the following specific applications:

1. **Pre-screening Identification**: Identifying patients within a healthcare system's EHR population who may potentially meet inclusion criteria and not trigger exclusion criteria for specific clinical trials based on their documented clinical data.

2. **Eligibility Evidence Assembly**: Aggregating and presenting the clinical evidence (diagnoses, lab results, medications, procedures, demographics) relevant to each eligibility criterion for a specific patient-trial pair, enabling research coordinators to review evidence in a structured format.

3. **Data Completeness Assessment**: Identifying gaps in available patient clinical data that prevent complete eligibility evaluation, enabling targeted chart review or data acquisition efforts.

4. **Enrollment Pipeline Management**: Tracking patients through the clinical trial enrollment workflow stages (candidate, screened, eligible, enrolled, active, completed, withdrawn, screen-failed).

### 2.2 Target Population

The system screens patients against clinical trial eligibility criteria. It is applicable to:

- Adult and pediatric patient populations as defined by individual trial protocols
- Patients with structured clinical data available in FHIR-compatible EHR systems
- Patients whose clinical data includes coded diagnoses, laboratory results, medication records, procedure records, and/or clinical narrative notes

### 2.3 Trial Types

The system supports screening for:

- Phase I, II, III, and IV clinical trials
- Interventional and observational studies
- All therapeutic areas (including but not limited to oncology, dermatology, ophthalmology, cardiology, endocrinology, neurology)

### 2.4 Eligibility Criteria Types Supported

| Criterion Type | Description | Data Sources |
|---|---|---|
| Demographic | Age range, sex | Patient node properties (birth date, gender) |
| Condition | Diagnosed conditions (ICD-10-CM, SNOMED CT codes) | ClinicalFact records in Condition domain |
| Measurement | Laboratory values with numeric ranges (LOINC codes) | ClinicalFact records in Measurement domain |
| Drug | Current/past medications (RxNorm codes) | ClinicalFact records in Drug domain |
| Procedure | Past procedures (CPT, SNOMED CT codes) | ClinicalFact records in Procedure domain |
| Observation | Clinical observations and allergy data | ClinicalFact records in Observation domain |

---

## 3. Contraindications

The system has no patient-facing contraindications (it does not interact with patients directly). The following are contraindications for system USE:

1. **The system MUST NOT be used as the sole basis for determining patient eligibility for clinical trial enrollment.** A qualified healthcare professional must independently verify all eligibility determinations.

2. **The system MUST NOT be used to make autonomous enrollment decisions.** The system produces recommendations, not binding determinations.

3. **The system MUST NOT be used when clinician review of output is not feasible.** If the intended clinical research workflow does not include a step for independent clinician review of system recommendations, the system should not be deployed.

4. **The system MUST NOT be used for clinical diagnosis, treatment selection, or therapeutic decision-making.** The system is intended exclusively for clinical trial eligibility screening.

5. **The system MUST NOT be used for emergency or time-critical clinical decisions.** The system is designed for non-urgent clinical research screening workflows with adequate time for human review.

---

## 4. Warnings and Precautions

### 4.1 Warnings

1. **False Negatives**: The system may fail to identify eligible patients (false negatives) due to:
   - Incomplete clinical data in the source EHR
   - NLP extraction errors in clinical narrative notes
   - Temporal data gaps (patient's condition changed after most recent documented encounter)
   - Coding discrepancies between the trial criteria vocabulary and the patient's clinical data
   - Missing data domains (e.g., lab results not imported)

   Organizations should monitor false-negative rates using the built-in false-negative monitoring service and conduct periodic manual chart review audits to validate system sensitivity.

2. **False Positives**: The system may incorrectly identify ineligible patients as potentially eligible (false positives) due to:
   - NLP confidence scores above threshold for incorrect extractions
   - Broad text matching on condition/medication names (the system uses `ILIKE` pattern matching which may match related but clinically distinct concepts)
   - Temporal context limitations (a resolved condition may be incorrectly treated as current)
   - Insufficient granularity in eligibility criteria coding

   The mandatory clinician review step (CDS Criterion 4) is the primary mitigation for false positives. Clinical research personnel must verify each candidate against the complete trial protocol.

3. **Data Currency**: Clinical data reflects the patient's documented state at the time of data import. Patient clinical status may have changed since the most recent documented encounter. Clinical research personnel should verify current patient status through direct clinical assessment per the trial protocol.

4. **Safety Blocks**: When the system identifies a high-confidence exclusion criterion match (confidence > 0.7), it triggers a safety block that forces the match score to zero and prevents auto-enrollment. Safety blocks MUST NOT be overridden through the system. If a safety block is believed to be erroneous, the clinical data and criterion coding should be reviewed and corrected, and the patient should be re-screened.

5. **NLP Extraction Limitations**: The NLP extraction pipeline uses a combination of pattern-based and rule-based methods. It is not infallible. Extraction accuracy depends on the quality, completeness, and format of the source clinical text. Unusual abbreviations, misspellings, non-standard formatting, or domain-specific jargon may reduce extraction accuracy.

### 4.2 Precautions

1. **Data Quality Dependency**: System accuracy is directly dependent on the quality, completeness, and timeliness of the input clinical data. Organizations should establish data quality monitoring processes for FHIR import pipelines.

2. **Criterion Coding Accuracy**: Eligibility criteria must be accurately coded in the system's structured format. Errors in criterion coding (wrong ICD-10 codes, incorrect value ranges, missing criteria) will propagate to all screening results for the affected trial.

3. **User Training**: All users must receive training on:
   - The system's intended use and limitations
   - How to interpret match scores, confidence levels, and evidence summaries
   - The requirement for independent clinical verification
   - How to recognize and respond to safety block indicators
   - How to interpret data completeness scores and act on data gap recommendations

4. **Regulatory Compliance**: Use of the system does not satisfy or replace any regulatory requirements for clinical trial eligibility determination, including but not limited to: IRB-approved protocol compliance, informed consent, sponsor-required source document verification, or 21 CFR Part 11 requirements for electronic records.

5. **Audit Trail Preservation**: System audit logs, screening results, and evidence records should be retained per organizational record retention policies and applicable regulatory requirements (e.g., 21 CFR Part 11, ICH E6(R2) GCP).

---

## 5. Target User Profile

### 5.1 Primary Users

| Role | Qualifications | System Use |
|---|---|---|
| Clinical Research Coordinator (CRC) | Bachelor's degree in health sciences or related field; ACRP or SOCRA certification preferred; training in GCP and trial protocols | Reviews screening results, verifies eligibility against protocol, coordinates enrollment workflow |
| Clinical Trial Associate | Clinical research training; familiarity with trial protocols and eligibility criteria | Configures trial eligibility criteria, reviews candidate lists, manages enrollment pipeline |

### 5.2 Secondary Users

| Role | Qualifications | System Use |
|---|---|---|
| Principal Investigator (PI) | Licensed physician (MD/DO); board-certified in relevant specialty | Makes final eligibility determination, approves enrollment decisions |
| Sub-Investigator | Licensed healthcare professional (MD, NP, PA); GCP-trained | Assists PI in eligibility review and verification |
| Clinical Operations Manager | Clinical operations experience; clinical trial management expertise | Monitors enrollment metrics, reviews dashboard analytics, oversees screening operations |

### 5.3 Required Training

All users must complete the following before system use:

1. System-specific training on features, workflow, and limitations
2. Good Clinical Practice (GCP) training (ICH E6(R2))
3. HIPAA Privacy and Security training
4. Trial-specific protocol training (per-trial)

---

## 6. Use Environment

### 6.1 Physical Environment

- Clinical research offices and coordinators' workstations
- Hospital or medical center clinical research departments
- CRO offices
- Sponsor clinical operations departments
- Remote work environments (via VPN/secure access)

### 6.2 Technical Environment

| Requirement | Specification |
|---|---|
| Client Device | Standard workstation, laptop, or tablet with modern web browser |
| Browser | Chrome 90+, Firefox 88+, Safari 14+, Edge 90+ |
| Network | Secure network connection (HTTPS/TLS 1.2+) |
| Authentication | Role-based access control with user authentication |
| EHR Integration | FHIR R4-compatible EHR system for data import |

### 6.3 Workflow Context

The system is intended for use within the following workflow:

1. Patient clinical data is imported into the system via FHIR interface
2. Clinical trial eligibility criteria are configured in the system
3. The system screens patients against criteria and produces candidate lists
4. **Clinical Research Coordinator reviews each candidate** against the trial protocol, verifying the system's evidence summaries against source clinical records
5. **Principal Investigator makes the final eligibility determination** based on the CRC's verification and independent clinical assessment
6. Patient is approached for informed consent per IRB-approved procedures
7. Patient is formally enrolled per protocol requirements

Steps 4 and 5 are mandatory human review steps that cannot be bypassed.

---

## 7. Not Intended For (Negative Scope)

The system is explicitly NOT intended for:

1. **Clinical Diagnosis**: The system does not diagnose diseases or medical conditions. It analyzes pre-existing clinical data that has already been documented by healthcare providers.

2. **Treatment Decisions**: The system does not recommend, suggest, or influence treatment selections, medication prescriptions, or therapeutic interventions.

3. **Replacing Physician Judgment**: The system does not replace the independent clinical judgment of the principal investigator or any healthcare professional involved in the trial enrollment process.

4. **Autonomous Decision-Making**: The system does not make autonomous enrollment, exclusion, or any other clinical decisions. All outputs are recommendations requiring human review and verification.

5. **Patient-Facing Use**: The system is not intended for use by patients or their caregivers. It is a professional tool for trained clinical research personnel.

6. **Medical Image Analysis**: The system does not acquire, process, analyze, or display medical images (radiographs, MRI, CT, ultrasound, pathology images, or any other medical imaging modality).

7. **Physiological Signal Processing**: The system does not acquire, process, or analyze physiological signals (ECG, EEG, EMG, pulse oximetry, blood pressure waveforms, or any other bioelectric or biophysical signals).

8. **In Vitro Diagnostic Analysis**: The system does not interface with or analyze signals from in vitro diagnostic (IVD) devices.

9. **Emergency Medicine**: The system is not intended for use in emergency, acute care, or time-critical clinical decision-making scenarios.

10. **Genetic/Genomic Analysis**: The system does not perform genetic or genomic data analysis for trial matching (although genomic criteria could be added in the future, which would require regulatory re-assessment).

11. **Drug Safety Assessment for Patient Care**: While the platform includes a drug safety module, the trial matching module does not use drug safety data for patient care decisions. Drug safety data is used solely within the context of trial eligibility screening (e.g., checking for contraindicated medications).

12. **Regulatory Submission**: System output does not constitute regulatory-quality documentation. Formal eligibility case report forms (CRFs) must be completed per sponsor and regulatory requirements independently of system output.

---

## Document Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| VP of Quality | | | |
| Chief Medical Officer | | | |
| VP of Engineering | | | |
| Legal Counsel | | | |
| Regulatory Affairs | | | |
