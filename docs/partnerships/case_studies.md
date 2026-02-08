# Clinical Trial Patient Recruitment Case Studies

Three detailed case studies demonstrating platform impact across ophthalmology, dermatology, and oncology therapeutic areas.

---

## Case Study 1: Accelerating DME Trial Recruitment with EYLEA

**Therapeutic Area:** Ophthalmology
**Drug:** EYLEA (aflibercept)
**Indication:** Diabetic Macular Edema (DME)

### Challenge

A Phase III DME trial required patients with confirmed diabetic macular edema, specific BCVA ranges, and no prior anti-VEGF treatment within 90 days. Traditional chart review was identifying only 2-3 eligible patients per site per month, putting enrollment timelines at risk.

### Solution

Deployed the Clinical Ontology Normalizer platform to automate patient-trial matching across 12 clinical sites. The platform ingested clinical data via FHIR R4, extracted diagnosis codes and treatment history using NLP, mapped to OMOP concepts, and screened patients against trial criteria in real time.

### Results

| Metric | Value | Context |
|---|---|---|
| Screen-to-eligible conversion rate | 34% | vs. 12% industry average for DME trials |
| Eligible patients identified per site/month | 8-12 | 3-4x improvement over manual screening |
| Time to full enrollment | 14 weeks | vs. projected 26 weeks with traditional methods |
| Screen failure reduction | 58% | Criteria-level analytics identified protocol issues |

### Timeline

12 weeks from contract to go-live across 12 sites.

### Key Takeaway

The automated screening platform transformed the recruitment workflow. Eligible patients were surfaced automatically within the EHR, eliminating manual chart review and dramatically accelerating enrollment.

---

## Case Study 2: Dupixent Atopic Dermatitis Trial: Diversity-First Recruitment

**Therapeutic Area:** Dermatology
**Drug:** Dupixent (dupilumab)
**Indication:** Moderate-to-Severe Atopic Dermatitis

### Challenge

A Phase III atopic dermatitis trial needed to meet FDA diversity enrollment targets while maintaining aggressive enrollment timelines. Historical trials in this indication had shown significant underrepresentation of Black and Hispanic patients.

### Solution

Implemented the platform with diversity analytics enabled, providing real-time demographic tracking of screening and enrollment funnels. The diversity scoring module identified sites with the highest potential for diverse enrollment, and criteria fidelity analysis identified exclusion criteria that disproportionately excluded underrepresented populations.

### Results

| Metric | Value | Context |
|---|---|---|
| Diversity enrollment score | 0.82 | vs. 0.45 target (1.0 = perfect representation) |
| Underrepresented population enrollment | 38% | vs. 15% in prior similar trials |
| Protocol amendments avoided | 2 | Criteria fidelity analysis identified issues pre-enrollment |
| Enrollment timeline impact | On schedule | Diversity targets met without extending enrollment period |

### Timeline

8 weeks from contract to go-live across 8 sites.

### Key Takeaway

The diversity analytics gave real-time visibility into enrollment demographics. The study team could proactively adjust site strategy rather than discovering gaps at database lock, avoiding costly protocol amendments and FDA enrollment holds.

---

## Case Study 3: Libtayo CSCC Trial: EHR-Embedded Recruitment

**Therapeutic Area:** Oncology
**Drug:** Libtayo (cemiplimab)
**Indication:** Cutaneous Squamous Cell Carcinoma (CSCC)

### Challenge

A Phase II CSCC trial required patients with advanced cutaneous squamous cell carcinoma who had failed prior therapy. The rare patient population and complex eligibility criteria made traditional recruitment methods extremely challenging, with sites averaging less than 1 eligible patient per month.

### Solution

Deployed the platform with SMART on FHIR integration and CDS Hooks, embedding trial alerts directly into the oncologist EHR workflow. When a patient matching preliminary criteria was encountered during a clinic visit, the system generated a CDS Hook card with trial details and screening status.

### Results

| Metric | Value | Context |
|---|---|---|
| Eligible patient identification rate | 3.2x | increase vs. pre-platform baseline |
| Investigator awareness of trial | 95% | vs. 40% before CDS Hook integration |
| Time from identification to consent | 4.5 days | vs. 18 days with traditional referral process |
| Screen failure rate | 22% | vs. 45% industry average for CSCC trials |

### Timeline

10 weeks from contract to go-live across 6 sites.

### Key Takeaway

Having trial alerts appear in the EHR during patient visits was transformative. The system finds patients for investigators rather than relying on coordinators searching through charts, dramatically reducing the time from identification to consent.

---

## Summary

| Metric | DME / EYLEA | AD / Dupixent | CSCC / Libtayo |
|---|---|---|---|
| Phase | III | III | II |
| Sites | 12 | 8 | 6 |
| Go-Live Timeline | 12 weeks | 8 weeks | 10 weeks |
| Primary Win | 3-4x eligible patients | 0.82 diversity score | 3.2x identification rate |
| Screen Failure Impact | -58% | 2 amendments avoided | -51% vs. industry |

---

## API Access

Case studies are available programmatically:

```
GET /api/v1/partnerships/rfp/case-studies              # All case studies
POST /api/v1/partnerships/rfp/generate                 # Include in RFP response
```
