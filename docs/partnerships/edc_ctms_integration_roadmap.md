# EDC/CTMS Integration Roadmap (Partnership-2)

## Overview

This document defines the integration roadmap for connecting the Clinical Ontology Normalizer platform with six target clinical trial systems. The roadmap is organized into four phases, prioritized by technical readiness, strategic value, and implementation effort.

## Target Systems

### EDC Systems (Electronic Data Capture)

| System | Vendor | API Type | Data Formats | Auth | Phase |
|--------|--------|----------|--------------|------|-------|
| **REDCap** | Vanderbilt University | REST | JSON, CSV | API Key | Phase 1 |
| **Medidata Rave** | Dassault Systemes | REST | CDISC ODM, JSON | OAuth2, API Key | Phase 2 |

### CTMS Systems (Clinical Trial Management)

| System | Vendor | API Type | Data Formats | Auth | Phase |
|--------|--------|----------|--------------|------|-------|
| **Veeva Vault CTMS** | Veeva Systems | REST | JSON, CSV | OAuth2 | Phase 3 |
| **Oracle Siebel CTMS** | Oracle | SOAP/REST | XML, JSON | Basic/Cert | Phase 4 |

### EHR/EMR Systems

| System | Vendor | API Type | Data Formats | Auth | Phase |
|--------|--------|----------|--------------|------|-------|
| **Epic** | Epic Systems | SMART on FHIR | FHIR R4, HL7v2 | OAuth2 | Phase 1 |
| **Flatiron OncoEMR** | Flatiron Health (Roche) | REST (FHIR R4) | FHIR R4 | OAuth2 | Phase 3 |

---

## System-by-System Integration Analysis

### REDCap

**Category:** EDC | **Priority:** Phase 1 (Lowest Effort)

REDCap is widely used in academic research and investigator-initiated trials. Its simple REST API with token-based authentication makes it the easiest integration target.

**Technical Architecture:**
- API: REST with token-based auth
- Data Exchange: JSON records, CSV export, data dictionary API
- Sync: On-demand API calls and batch export
- Key Data: Data dictionary, subject records, events/arms, reports

**Platform Readiness:** HIGH
- ETL pipeline: IMPLEMENTED (85%)
- Data mapping engine: PARTIAL (60%) -- needs REDCap-specific mappers
- Batch import/export: IMPLEMENTED (85%)
- Audit trail: IMPLEMENTED (95%)

**Effort:** 6 calendar weeks, 2 engineers, 10 engineer-weeks

---

### Epic

**Category:** EHR | **Priority:** Phase 1 (FHIR-Native)

Epic is the market-leading EHR deployed in major health systems. The platform's existing SMART on FHIR and CDS Hooks capabilities provide a strong foundation.

**Technical Architecture:**
- API: SMART on FHIR (R4)
- Data Exchange: FHIR R4 resources, HL7v2 messages
- Sync: Real-time (SMART launch), on-demand (API queries)
- Key Data: Patient demographics, clinical data (problems, meds, allergies, vitals), orders, encounters

**Platform Readiness:** HIGH
- FHIR R4 compliance: IMPLEMENTED (95%)
- SMART on FHIR: IMPLEMENTED (92%)
- OAuth2 client: IMPLEMENTED (90%)
- Patient matching: IMPLEMENTED (88%)
- CDS Hooks: IMPLEMENTED (88%)
- HL7v2 support: PARTIAL (40%) -- needs ORU/ORM messages

**Effort:** 8 calendar weeks, 3 engineers, 18 engineer-weeks

**Key Risk:** Epic app review process can take 4-8 weeks.

---

### Medidata Rave

**Category:** EDC | **Priority:** Phase 2 (CDISC Adapter)

Medidata Rave is the dominant EDC in top-20 pharma. Integration requires building a CDISC ODM adapter, which is strategic capability reusable across many EDC systems.

**Technical Architecture:**
- API: REST with OAuth2
- Data Exchange: CDISC ODM-XML for study events, JSON for operational data
- Sync: Real-time webhooks and batch export
- Key Data: Study events, subject data, clinical data (labs, vitals, AEs), study design

**Platform Readiness:** MODERATE
- CDISC ODM support: NEEDS_DEVELOPMENT (10%) -- major gap
- OAuth2 client: IMPLEMENTED (90%)
- ETL pipeline: IMPLEMENTED (85%)
- Data mapping engine: PARTIAL (60%)
- Webhook infrastructure: IMPLEMENTED (90%)

**Effort:** 10 calendar weeks, 3 engineers, 24 engineer-weeks

**Key Risk:** CDISC ODM complexity requires careful implementation; study-specific ODM configurations vary significantly.

---

### Veeva Vault CTMS

**Category:** CTMS | **Priority:** Phase 3

Veeva Vault CTMS manages clinical trial operations for top pharma companies. REST API with comprehensive object model for study/site/subject management.

**Technical Architecture:**
- API: REST with OAuth2
- Data Exchange: JSON objects, CSV bulk export
- Sync: Real-time and batch
- Key Data: Study management, site management, subject enrollment, monitoring

**Platform Readiness:** MODERATE-HIGH
- OAuth2 client: IMPLEMENTED (90%)
- ETL pipeline: IMPLEMENTED (85%)
- Data mapping engine: PARTIAL (60%)
- Webhook infrastructure: IMPLEMENTED (90%)
- Batch import/export: IMPLEMENTED (85%)

**Effort:** 8 calendar weeks, 2 engineers, 14 engineer-weeks

**Key Risk:** Veeva object model is complex and heavily customized per client.

---

### Flatiron OncoEMR

**Category:** EMR (Oncology) | **Priority:** Phase 3

Flatiron OncoEMR provides structured oncology data via FHIR R4 with oncology-specific extensions (mCODE profiles).

**Technical Architecture:**
- API: REST (FHIR R4) with OAuth2
- Data Exchange: FHIR R4 with mCODE extensions
- Sync: Real-time and batch
- Key Data: Oncology demographics, tumor data (staging, biomarkers), treatment regimens, lab results

**Platform Readiness:** HIGH
- FHIR R4 compliance: IMPLEMENTED (95%)
- OAuth2 client: IMPLEMENTED (90%)
- ETL pipeline: IMPLEMENTED (85%)
- Patient matching: IMPLEMENTED (88%)
- Data mapping engine: PARTIAL (60%)

**Effort:** 8 calendar weeks, 2 engineers, 14 engineer-weeks

**Key Risk:** Oncology-specific FHIR profiles (mCODE) require domain expertise.

---

### Oracle Siebel CTMS

**Category:** CTMS (Legacy) | **Priority:** Phase 4

Oracle Siebel CTMS is a legacy platform still widely deployed in large pharma. Integration is the most complex due to SOAP APIs and certificate-based authentication.

**Technical Architecture:**
- API: SOAP/REST with basic auth and mTLS certificates
- Data Exchange: Custom XML, JSON
- Sync: Batch and on-demand
- Key Data: Enrollment tracking, site management, study configuration

**Platform Readiness:** LOW
- SOAP client: NEEDS_DEVELOPMENT (0%) -- no infrastructure
- Certificate auth: NEEDS_DEVELOPMENT (5%) -- mTLS not built
- ETL pipeline: IMPLEMENTED (85%)
- Data mapping engine: PARTIAL (60%)
- Batch import/export: IMPLEMENTED (85%)

**Effort:** 12 calendar weeks, 3 engineers, 28 engineer-weeks

**Key Risks:**
- Legacy SOAP APIs can be brittle and poorly documented
- Certificate management adds operational complexity
- Siebel customizations vary wildly between deployments
- May require on-premise connectivity (VPN/dedicated link)

---

## Phased Delivery Roadmap

### Phase 1: FHIR-Native Integrations (Weeks 1-8)

**Systems:** REDCap, Epic

**Rationale:** Both systems support FHIR R4 natively. The platform already has FHIR compliance (95%) and SMART on FHIR (92%), requiring minimal new development. This phase hardens FHIR infrastructure for later phases.

**Milestones:**
1. **Week 4:** REDCap API integration (client, data dictionary, records)
2. **Week 6:** Epic SMART on FHIR launch (app registration, patient matching, clinical data sync)
3. **Week 8:** Phase 1 validation (integration tests, performance benchmarks, documentation)

**Total Effort:** 8 calendar weeks, 28 engineer-weeks

---

### Phase 2: CDISC EDC Integration (Weeks 9-18)

**Systems:** Medidata Rave

**Rationale:** Medidata Rave is the dominant EDC in pharma; CDISC ODM support is a strategic capability. Phase 1 hardens FHIR infrastructure reused here.

**Milestones:**
1. **Week 4:** CDISC ODM engine (parser, generator, domain mapping)
2. **Week 7:** Medidata API integration (client, study events, enrollment sync)
3. **Week 10:** Phase 2 validation (ODM round-trip, clinical data exchange)

**Total Effort:** 10 calendar weeks, 24 engineer-weeks

---

### Phase 3: CTMS + Oncology EMR (Weeks 19-26)

**Systems:** Veeva Vault CTMS, Flatiron OncoEMR

**Rationale:** High-value targets for pharma partnerships. REST API and FHIR R4 patterns are already proven from earlier phases. These can run in parallel.

**Milestones:**
1. **Week 6:** Veeva Vault integration (API client, enrollment management)
2. **Week 6:** Flatiron OncoEMR integration (FHIR client, mCODE support)
3. **Week 8:** Phase 3 validation (cross-system testing, performance)

**Total Effort:** 8 calendar weeks, 28 engineer-weeks

---

### Phase 4: Legacy CTMS Adapter (Weeks 27-38)

**Systems:** Oracle Siebel CTMS

**Rationale:** Most complex integration deferred to final phase. Requires new SOAP infrastructure and certificate management. Earlier phases provide reusable data mapping patterns.

**Milestones:**
1. **Week 4:** SOAP infrastructure (client library, certificate auth, mTLS)
2. **Week 9:** Siebel integration (object mapper, enrollment tracking, site management)
3. **Week 12:** Phase 4 validation (legacy system testing, deployment plan)

**Total Effort:** 12 calendar weeks, 28 engineer-weeks

---

## Resource and Budget Requirements

### Engineering Resources

| Phase | Calendar Weeks | Engineers | Engineer-Weeks |
|-------|---------------|-----------|----------------|
| Phase 1 | 8 | 3 | 28 |
| Phase 2 | 10 | 3 | 24 |
| Phase 3 | 8 | 2 | 28 |
| Phase 4 | 12 | 3 | 28 |
| **Total** | **38** | **3 (peak)** | **108** |

### Capability Development Requirements

| Capability | Status | Gap | Effort |
|-----------|--------|-----|--------|
| FHIR R4 Compliance | Implemented (95%) | Minor specialty profiles | 1 week |
| SMART on FHIR | Implemented (92%) | Vendor-specific contexts | 0.5 weeks |
| OAuth2 Client | Implemented (90%) | Vendor token refresh | 0.5 weeks |
| CDS Hooks | Implemented (88%) | - | 0.5 weeks |
| Patient Matching | Implemented (88%) | - | 1 week |
| ETL Pipeline | Implemented (85%) | Custom connectors | 2 weeks |
| Batch Import/Export | Implemented (85%) | CSV/ODM handlers | 2 weeks |
| Audit Trail | Implemented (95%) | - | 0 weeks |
| Data Mapping Engine | Partial (60%) | CDISC/vendor mappers | 4 weeks |
| HL7v2 Support | Partial (40%) | ORU/ORM messages | 4 weeks |
| CDISC ODM Support | Needs Dev (10%) | Full implementation | 8 weeks |
| Certificate Auth | Needs Dev (5%) | mTLS infrastructure | 3 weeks |
| SOAP Client | Needs Dev (0%) | Full implementation | 4 weeks |

### Key Dependencies

- Phase 2 depends on Phase 1 completion (FHIR infrastructure hardening)
- Phase 3 depends on Phase 1 completion
- Phase 4 depends on Phase 2 completion (CDISC adapter reusable) and certificate auth infrastructure
- Vendor partnership agreements required for Medidata, Flatiron, and Veeva sandbox access
- Epic app review process (4-8 weeks) should start during Phase 1 development

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/partnerships/integrations` | GET | List all target integrations |
| `/partnerships/integrations/{system}` | GET | Integration detail for a system |
| `/partnerships/integrations/{system}/readiness` | GET | Readiness assessment |
| `/partnerships/integrations/roadmap` | GET | Phased integration roadmap |
| `/partnerships/integrations/{system}/data-mapping` | GET | Data mapping templates |
| `/partnerships/integrations/summary` | GET | Overall integration status |

Valid system identifiers: `redcap`, `epic`, `medidata_rave`, `veeva_vault_ctms`, `flatiron_oncoemr`, `oracle_siebel_ctms`
