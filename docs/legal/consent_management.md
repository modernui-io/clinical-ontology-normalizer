# Consent Management

## Purpose

This document defines the consent management framework for the Clinical
Ontology Normalizer platform. As a HIPAA-covered clinical trial recruitment
system, the platform must obtain, track, verify, and enforce patient consent
before accessing, using, or disclosing Protected Health Information (PHI).

Consent management is not a single checkbox -- it involves multiple consent
types, each with distinct legal bases, scopes, and revocation procedures.

---

## 1. Types of Consent Required

### 1.1 HIPAA Authorization

**Legal basis**: 45 CFR 164.508

A valid HIPAA authorization is required before using or disclosing PHI for
purposes beyond Treatment, Payment, and Health Care Operations (TPO).

Required elements of a valid HIPAA authorization:

1. Description of PHI to be used or disclosed
2. Name of person(s) authorized to make the disclosure
3. Name of person(s) to whom disclosure is made
4. Purpose of the use or disclosure
5. Expiration date or event
6. Signature and date
7. Right to revoke (and how to do so)
8. Statement that information may be re-disclosed
9. Statement that treatment/payment cannot be conditioned on
   authorization (unless for research)

**Consent type in system**: `HIPAA_AUTHORIZATION`

### 1.2 Research Participation Consent

**Legal basis**: 45 CFR 46 (Common Rule), 21 CFR 50 (FDA)

Required before enrolling a patient in a clinical trial. This is the
informed consent document approved by the trial's IRB.

Key requirements:

- Written in understandable language
- Describes the research purpose, procedures, risks, and benefits
- States participation is voluntary
- Describes confidentiality protections
- Provides contact information for questions
- Must be IRB-approved

**Consent type in system**: `RESEARCH_PARTICIPATION`

### 1.3 Data Sharing Consent

**Legal basis**: HIPAA, state privacy laws, organizational policy

Consent for sharing PHI between entities (e.g., between a healthcare
provider and the clinical trial platform, or between the platform and a
trial sponsor).

Scope must specify:

- Which data elements may be shared
- With whom (specific entities)
- For what purpose
- Duration of sharing authorization

**Consent type in system**: `DATA_SHARING`

### 1.4 Screening Consent

**Legal basis**: Organizational policy, IRB protocol

Consent to screen a patient's medical records against clinical trial
eligibility criteria. This is a narrower consent than research
participation -- it authorizes the platform to evaluate patient data
against trial criteria, but does not enroll the patient.

**Consent type in system**: `SCREENING_CONSENT`

---

## 2. Consent Workflow

### 2.1 Capture

```
Patient/Provider -> Consent Form -> Platform API -> Consent Record
```

1. **Initiation**: Provider or research coordinator presents consent
   form to patient (paper or electronic)
2. **Signature**: Patient signs consent (wet signature, e-signature,
   or verbal with witness per state law)
3. **Recording**: Authorized user records consent in the platform via
   `POST /api/v1/consent` with:
   - Patient ID
   - Consent type
   - Scope (what PHI, for what purpose)
   - Granted by (who captured the consent)
   - Expiration date (if applicable)
4. **Confirmation**: System returns a ConsentRecord with unique ID
   and timestamp

### 2.2 Storage

- Consent records stored with full audit trail
- Each record is immutable -- updates create new records
- Original consent documents (scanned forms, e-signatures) stored in
  secure document management system
- Consent metadata indexed for fast lookup during access checks

### 2.3 Verification

Every access to patient PHI must verify consent:

```
API Request -> Consent Check -> [Authorized] -> Process Request
                             -> [Not Authorized] -> 403 Forbidden
```

1. **On every PHI access**: Call `check_consent(patient_id, consent_type)`
2. **Check result**: `active`, `expired`, `revoked`, or `not_found`
3. **Enforce**: Only proceed if consent is `active`
4. **Purpose check**: For specific data uses, call
   `check_data_use_authorization(patient_id, purpose)` to verify the
   consent covers the requested purpose

### 2.4 Revocation

Patients have the right to revoke consent at any time:

1. **Request**: Patient or authorized representative requests revocation
2. **Recording**: Authorized user calls `POST /api/v1/consent/revoke`
   with patient ID, consent type, revoked by, and reason
3. **Effective date**: Revocation is effective immediately upon recording
4. **Prospective only**: Revocation applies prospectively -- it does not
   undo prior uses made in reliance on the authorization
5. **Notification**: System notifies relevant downstream systems/users
   of the revocation
6. **Audit**: Revocation recorded in consent audit trail

---

## 3. Right to Deletion (HIPAA Right of Access)

### 3.1 Individual Right of Access (45 CFR 164.524)

Patients have the right to:

- Access their PHI maintained by the platform
- Request copies in electronic format
- Direct copies to a third party

**Platform response timeline**: Within **15 business days** (one 15-day
extension permitted with written notice).

### 3.2 Right to Request Amendment (45 CFR 164.526)

Patients may request amendments to their PHI. The platform must:

- Accept or deny amendment requests within **60 days**
- If denied, provide written denial with basis and inform patient of
  right to file a statement of disagreement
- If accepted, make amendment and notify relevant parties

### 3.3 Right to Restriction (45 CFR 164.522)

Patients may request restrictions on uses/disclosures of their PHI.
The platform:

- Is not required to agree to a restriction (except for self-pay
  patients requesting restriction from health plan disclosure)
- If agreed, must honor the restriction
- Must document all agreed-upon restrictions

### 3.4 Right to Deletion Under State Laws

Some state laws (e.g., California CCPA/CPRA) provide broader deletion
rights. The platform must:

- Accept deletion requests from California residents under CCPA
- Verify identity of requestor
- Delete or de-identify PHI within **45 days** (one 45-day extension)
- Notify service providers/contractors to delete
- Confirm deletion to the consumer
- Document exceptions (legal holds, ongoing treatment, etc.)

### 3.5 Deletion Procedure

1. **Receive request**: Via API, email, or written request
2. **Verify identity**: Confirm requestor identity and authorization
3. **Scope determination**: Identify all PHI held for the patient
4. **Legal hold check**: Verify no litigation hold or regulatory
   retention requirement applies
5. **Execute deletion**: Remove PHI from all systems (database, backups,
   caches, knowledge graph, search indices)
6. **Downstream notification**: Notify subcontractors/vendors to delete
   per BAA obligations
7. **Confirmation**: Provide written confirmation of deletion
8. **Audit record**: Maintain record of the deletion request and
   execution (metadata only, no PHI)

---

## 4. Consent Audit Trail Requirements

### 4.1 What Must Be Logged

Every consent-related event must be logged with:

| Field | Description |
|---|---|
| event_id | Unique event identifier |
| timestamp | ISO 8601 timestamp with timezone |
| patient_id | Patient whose consent is affected |
| consent_type | Type of consent (HIPAA_AUTHORIZATION, etc.) |
| action | GRANTED, REVOKED, CHECKED, EXPIRED |
| actor | User or system that performed the action |
| scope | What PHI/purposes the consent covers |
| result | For checks: AUTHORIZED or DENIED |
| ip_address | Source IP of the request |
| reason | For revocations: reason for revocation |

### 4.2 Retention

- Consent audit records must be retained for **6 years** from the date
  of creation or the date the consent was last in effect, whichever is
  later (per HIPAA 45 CFR 164.530(j)).
- Audit records must not be modified or deleted.
- Audit records must be available for inspection by the HHS Secretary.

### 4.3 Access to Audit Trail

- Patients may request an accounting of disclosures (see section 3.1)
- Compliance officers can query the audit trail via
  `GET /api/v1/consent/audit/{patient_id}`
- Audit data must be exportable for regulatory review

---

## 5. State-Specific Requirements

### 5.1 California (CCPA/CPRA)

| Requirement | Implementation |
|---|---|
| Right to know what PI is collected | Support via patient data access API |
| Right to delete PI | Deletion procedure (section 3.5) |
| Right to opt-out of sale | Platform does NOT sell PHI (documented) |
| Right to non-discrimination | No service degradation for exercising rights |
| Notice at collection | Provided at data ingestion point |
| Verification of identity | Required before honoring access/deletion requests |

### 5.2 New York

- Genetic information has additional protections under NY Civil Rights
  Law Article 79-l
- HIV/AIDS data requires specific written consent per NY Public Health
  Law Article 27-F
- Mental health records have restrictions under NY Mental Hygiene Law

### 5.3 Texas

- Texas Medical Records Privacy Act (TMRPA) provides broader
  protections than HIPAA for certain categories
- Requires consent for electronic disclosure of PHI
- 15-day response timeline for access requests

### 5.4 Washington

- Washington My Health My Data Act (MHMDA) applies to non-HIPAA
  health data
- Requires affirmative consent before collecting health data
- Provides geofencing protections

### 5.5 Multi-State Compliance Strategy

The platform applies the **most restrictive standard** across all
applicable jurisdictions:

1. Identify patient's state of residence
2. Apply HIPAA as the baseline
3. Layer state-specific requirements on top
4. When requirements conflict, apply the more protective standard
5. Document which standards apply to each patient interaction

---

## 6. Minimum Necessary Standard Application

### 6.1 Principle

The HIPAA Minimum Necessary standard (45 CFR 164.502(b)) requires that
the platform limit PHI access, use, and disclosure to the minimum
amount necessary to accomplish the intended purpose.

### 6.2 Implementation

#### Role-Based Access

| Role | PHI Access Level |
|---|---|
| Site Coordinator | Full PHI for assigned patients at assigned sites |
| Trial Manager | De-identified screening results; full PHI only for enrolled patients |
| Sponsor Analyst | De-identified aggregate data only |
| System Admin | Access to audit logs, no direct PHI access |
| Clinician Reviewer | Full PHI for patients under review |
| Data Entry | Limited to data being entered |

#### Purpose-Based Filtering

| Purpose | Permitted PHI Elements |
|---|---|
| SCREENING | Demographics, diagnoses, labs, medications (as defined by trial criteria) |
| TREATMENT | Full clinical record |
| PAYMENT | Claims data, procedure codes, billing demographics |
| OPERATIONS | De-identified quality metrics |
| RESEARCH | As specified in HIPAA authorization or IRB waiver |
| MARKETING | Prohibited without specific authorization |

#### Technical Controls

1. **API-level filtering**: Each endpoint returns only PHI elements
   authorized for the requesting role and purpose
2. **Query restriction**: Database queries filter by authorized
   patient set
3. **Response redaction**: Sensitive fields (SSN, genetic data)
   redacted unless specifically authorized
4. **Logging**: All PHI access logged with purpose code for audit

### 6.3 Exceptions to Minimum Necessary

The minimum necessary standard does NOT apply to:

- Disclosures to the individual (patient access requests)
- Disclosures pursuant to a valid HIPAA authorization
- Disclosures required by law
- Disclosures to HHS for compliance investigations
- Uses for treatment purposes

---

## 7. Consent Service API Reference

### 7.1 Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/consent` | Record a new consent |
| GET | `/api/v1/consent/patients/{patient_id}` | Get all consents for a patient |
| GET | `/api/v1/consent/check/{patient_id}/{consent_type}` | Check consent status |
| POST | `/api/v1/consent/revoke` | Revoke a consent |
| GET | `/api/v1/consent/audit/{patient_id}` | Get consent audit trail |

### 7.2 Consent Types

- `HIPAA_AUTHORIZATION` -- HIPAA authorization for use/disclosure
- `RESEARCH_PARTICIPATION` -- Informed consent for trial participation
- `SCREENING_CONSENT` -- Consent to screen against trial criteria
- `DATA_SHARING` -- Consent to share PHI between entities

### 7.3 Purposes

- `TREATMENT` -- Direct patient care
- `PAYMENT` -- Billing and claims
- `OPERATIONS` -- Healthcare operations
- `RESEARCH` -- Clinical research/trials
- `SCREENING` -- Trial eligibility screening
- `MARKETING` -- Marketing communications (requires specific authorization)

---

## 8. Implementation Checklist

- [ ] Consent service deployed and operational
- [ ] All API endpoints require consent verification for PHI access
- [ ] Consent capture workflow integrated into patient onboarding
- [ ] Consent revocation triggers downstream PHI access removal
- [ ] Audit trail captures all consent events
- [ ] 6-year retention policy configured for consent records
- [ ] State-specific consent requirements documented and implemented
- [ ] Minimum necessary controls implemented per role and purpose
- [ ] Patient access request workflow operational
- [ ] Deletion request workflow operational
- [ ] Staff trained on consent procedures
- [ ] BAA terms align with consent management procedures
