# Regeneron Clinical Trial Patient Recruitment Demo
## Video Script (5-7 minutes)

### Target Audience
Regeneron leadership / clinical ops team evaluating platform capabilities for trial recruitment acceleration.

### Key Message
"We can ingest patient data from any HIE via Metriport, standardize it to OMOP, build a patient knowledge graph, and automatically screen patients against your trial eligibility criteria — in real time."

---

## SCENE 1: Introduction (30 seconds)

**Show**: Landing page / dashboard

**Script**:
> "This is our Clinical Ontology Normalizer platform. Today I'll show you how it can accelerate patient recruitment for Regeneron clinical trials by automatically screening patients from health information exchanges against your trial eligibility criteria."

---

## SCENE 2: Trial Portfolio Overview (45 seconds)

**Show**: `/trials` page

**Script**:
> "Here we have three active Regeneron trials loaded into the system:
> - **EYLEA HD** — Phase III for Diabetic Macular Edema, targeting 900 patients across 300 sites
> - **LIBTAYO** — Phase II for advanced Cutaneous Squamous Cell Carcinoma, 200-patient target
> - **LIBERTY ADCHRONOS** — Phase III for Atopic Dermatitis with Dupilumab, 600 patients
>
> The dashboard shows real-time enrollment progress and aggregate statistics."

**Action**: Point out stats cards (3 trials, 3 recruiting, total enrolled, avg enrollment).

---

## SCENE 3: Trial Detail — EYLEA HD Deep Dive (60 seconds)

**Show**: Click into EYLEA HD trial

**Script**:
> "Let's look at the EYLEA HD trial in detail. You can see the enrollment pipeline — candidates flowing through screening, eligibility, enrollment, and active participation. The protocol ID, NCT number, therapeutic area, and indication codes are all captured."

**Action**: Show the Overview tab with enrollment pipeline breakdown.

> "Click the Eligibility Criteria tab."

> "The eligibility criteria are modeled as structured data — not free text. Inclusion requires adult patients with Diabetic Macular Edema and Type 2 Diabetes. The exclusion criterion filters out patients with uncontrolled diabetes — HbA1c above 12%. These criteria are mapped to standard codes: ICD-10-CM for conditions, LOINC for measurements."

**Action**: Show green inclusion cards and red exclusion card.

---

## SCENE 4: Patient Screening (60 seconds)

**Show**: Candidates tab → Click "Screen Patients"

**Script**:
> "Now the powerful part. When I click 'Screen Patients', the system evaluates every patient in our database against these criteria. It checks conditions, medications, lab values — all standardized to OMOP concepts."

**Action**: Click "Screen Patients" button, wait for results.

> "In seconds, the system screened [X] patients. We can see the exclusion breakdown — how many patients were filtered out by each criterion. For a real deployment, eligible candidates would be ranked by match score and flagged for site coordinators."

**Action**: Point out Total Screened, Eligible, Ineligible counts and Exclusion Breakdown.

---

## SCENE 5: Enrollment Tracking (30 seconds)

**Show**: Enrollment tab

**Script**:
> "The Enrollment tab tracks every patient through the recruitment funnel — from candidate to screened to eligible to enrolled. Each enrollment record includes the match score, criteria met and failed, and screening date. This gives site coordinators full visibility into the pipeline."

**Action**: Scroll through enrollment table showing status badges and match scores.

---

## SCENE 6: Data Ingestion — FHIR Bundle Import (60 seconds)

**Show**: Terminal / API call (or Swagger UI)

**Script**:
> "Where does this patient data come from? We support direct FHIR R4 Bundle import. A single API call can ingest a complete patient record — conditions, medications, lab results, procedures — and the system automatically normalizes everything to OMOP concepts and builds the knowledge graph."

**Action**: Show the curl command or Swagger UI for `POST /api/v1/fhir/bundle` with a sample Bundle. Show the response with resource counts and KG node/edge counts.

> "In this example, we imported a patient with Type 2 Diabetes, Hypertension, Metformin, and an HbA1c lab result. The system created 5 knowledge graph nodes and 4 edges — instantly queryable for trial matching."

---

## SCENE 7: HIE Integration — Metriport Webhook (45 seconds)

**Show**: Architecture diagram or terminal

**Script**:
> "For production scale, we integrate with Metriport's Medical API to pull patient records from Health Information Exchanges — Carequality, CommonWell, and eHealth Exchange. When Metriport delivers a consolidated patient record, our webhook receiver automatically queues it for FHIR import in the background."

**Action**: Show the webhook endpoint and ping test, or show the architecture flow:
`HIE → Metriport → Webhook → FHIR Import → OMOP → Knowledge Graph → Trial Matching`

> "This means every time a new patient record becomes available through the HIE network, it's automatically processed and available for trial screening — no manual intervention required."

---

## SCENE 8: Platform Capabilities (30 seconds)

**Show**: Sidebar navigation

**Script**:
> "Beyond trial recruitment, the platform provides a full clinical data infrastructure:
> - **NLP extraction** from clinical notes
> - **OMOP standardization** across vocabularies
> - **Knowledge graph** for clinical reasoning
> - **Drug safety** monitoring
> - **Clinical calculators** and **quality measures**
> - **CDS Hooks** for EHR integration
>
> The trial recruitment module leverages all of these capabilities."

---

## SCENE 9: Closing (30 seconds)

**Script**:
> "To summarize: we can ingest patient data from HIEs via Metriport, standardize it to OMOP, and automatically screen patients against Regeneron trial criteria — all in real time. This accelerates recruitment, reduces manual chart review, and ensures no eligible patient is missed.
>
> We're ready to connect to Metriport's sandbox to demonstrate live HIE data flow. Thank you."

---

## Technical Setup Checklist

Before recording:

- [ ] Backend running on port 8000 (`uvicorn`)
- [ ] Frontend running on port 3001 (`npm run dev`)
- [ ] PostgreSQL, Redis, Neo4j all healthy (`/api/v1/health`)
- [ ] 3 Regeneron trials loaded and visible
- [ ] Demo patient data seeded
- [ ] Browser zoomed to ~90% for readability
- [ ] Dark mode OFF (light theme for video clarity)
- [ ] Close unnecessary browser tabs
- [ ] Terminal ready for FHIR Bundle curl command
- [ ] Screen recording tool ready (OBS / QuickTime / Loom)

## Pre-recorded curl commands

### FHIR Bundle Import
```bash
curl -s -X POST "http://localhost:8000/api/v1/fhir/bundle" \
  -H "Content-Type: application/json" \
  -d '{
    "bundle": {
      "resourceType": "Bundle",
      "type": "searchset",
      "entry": [
        {
          "resource": {
            "resourceType": "Patient",
            "id": "demo-patient",
            "name": [{"family": "Johnson", "given": ["Sarah"]}],
            "gender": "female",
            "birthDate": "1958-09-12"
          }
        },
        {
          "resource": {
            "resourceType": "Condition",
            "id": "cond-1",
            "subject": {"reference": "Patient/demo-patient"},
            "code": {
              "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9", "display": "Type 2 diabetes mellitus"}]
            },
            "clinicalStatus": {"coding": [{"code": "active"}]}
          }
        },
        {
          "resource": {
            "resourceType": "Condition",
            "id": "cond-2",
            "subject": {"reference": "Patient/demo-patient"},
            "code": {
              "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "H35.81", "display": "Retinal edema"}]
            },
            "clinicalStatus": {"coding": [{"code": "active"}]}
          }
        },
        {
          "resource": {
            "resourceType": "MedicationRequest",
            "id": "med-1",
            "subject": {"reference": "Patient/demo-patient"},
            "medicationCodeableConcept": {
              "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975", "display": "Metformin 500 MG"}]
            },
            "status": "active",
            "authoredOn": "2024-03-15"
          }
        },
        {
          "resource": {
            "resourceType": "Observation",
            "id": "obs-1",
            "subject": {"reference": "Patient/demo-patient"},
            "code": {
              "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}]
            },
            "valueQuantity": {"value": 7.8, "unit": "%"},
            "effectiveDateTime": "2026-01-15",
            "status": "final"
          }
        }
      ]
    },
    "internal_patient_id": "regeneron-demo-patient-1"
  }' | python3 -m json.tool
```

### Metriport Webhook Ping
```bash
curl -s -X POST "http://localhost:8000/api/v1/metriport/webhook" \
  -H "Content-Type: application/json" \
  -d '{"meta": {"messageId": "demo-ping", "type": "ping"}, "ping": "12345"}' \
  | python3 -m json.tool
```

## Timing Guide

| Scene | Duration | Cumulative |
|-------|----------|------------|
| 1. Introduction | 0:30 | 0:30 |
| 2. Trial Portfolio | 0:45 | 1:15 |
| 3. EYLEA HD Detail | 1:00 | 2:15 |
| 4. Patient Screening | 1:00 | 3:15 |
| 5. Enrollment Tracking | 0:30 | 3:45 |
| 6. FHIR Bundle Import | 1:00 | 4:45 |
| 7. Metriport Webhook | 0:45 | 5:30 |
| 8. Platform Capabilities | 0:30 | 6:00 |
| 9. Closing | 0:30 | 6:30 |

**Total: ~6:30** (within 5-7 minute target)
