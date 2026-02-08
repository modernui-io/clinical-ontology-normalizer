# Healthcare Data SaaS Organizational Structure Research

> Research on billion-dollar healthcare data SaaS companies: Commure, Palantir (Health/AIP), Veracyte, Flatiron Health, Tempus AI, Deep 6 AI, and comparable firms. Focus on leadership roles, organizational patterns, and what each role demands from a clinical data normalization + trial matching platform.

---

## Table of Contents

1. [Company Profiles](#company-profiles)
2. [C-Suite Leadership](#c-suite-leadership)
3. [VP / Director Level](#vp--director-level)
4. [Principal / Staff IC Level](#principal--staff-ic-level)
5. [IC Level Roles](#ic-level-roles)
6. [Role-by-Role Platform Concerns Matrix](#role-by-role-platform-concerns-matrix)

---

## Company Profiles

### Commure (Valuation: ~$6B)
- **What they do**: AI-native enterprise RCM & ambient platform for healthcare. Built from Athelas + Commure merger (Oct 2023). FDA-cleared remote patient monitoring, ambient scribing, EHR, AI agents for healthcare workflows.
- **Named to 2025 Fortune Future 50 List**
- **Key tech**: FHIR-based interoperability, ambient AI documentation, RCM automation
- **~26 executives**

### Tempus AI (NASDAQ: TEM)
- **What they do**: AI-enabled precision medicine. Genomic sequencing, clinical data structuring, real-world evidence, clinical trial matching. Acquired Deep 6 AI (March 2025) and Ambry Genetics ($600M, Feb 2025).
- **Revenue**: $693.4M (2024), growing rapidly
- **Key tech**: Multimodal data library (genomic + clinical + imaging), NLP on clinical notes, OMOP-based research datasets, ML-driven trial matching (via Deep 6 AI acquisition)

### Flatiron Health (Roche subsidiary, acquired for $1.9B)
- **What they do**: Oncology-focused real-world data and evidence platform. EHR (OncoEMR), clinical data abstraction, RWE analytics for biopharma.
- **Key tech**: Oncology EHR, clinical data abstraction pipelines, RWE datasets across US/UK/Germany/Japan
- **Certifications**: HITRUST CSF, SOC-2, HIPAA, GDPR, 21 CFR 11 alignment
- **Clinical research business acquired by Paradigm Health (2025/2026)**

### Palantir Technologies (Health Division)
- **What they do**: Foundry + AIP data integration and AI platform applied to healthcare. Partners with OneMedNet, TeleTracking, Cognizant/TriZetto.
- **Market cap**: $443B+ (early 2026)
- **Key tech**: Foundry (data integration/digital twin), AIP (AI/LLM orchestration), ontology-driven data modeling

### Veracyte (NASDAQ: VCYT)
- **What they do**: Genomic diagnostics company. AI-powered diagnostic tests for cancer and other diseases.
- **Key tech**: Bioinformatics pipelines, genomic data analysis, clinical decision support

### Deep 6 AI (now part of Tempus)
- **What they do**: AI-driven clinical trial recruitment. 750+ provider sites, 30M+ patients. NLP on structured and unstructured EHR data for trial matching.
- **Key tech**: NLP-based patient-protocol matching, HIPAA-compliant data processing, real-time screening

---

## C-Suite Leadership

### CEO / Founder

| Person | Company | Background |
|--------|---------|------------|
| **Tanay Tandon** | Commure (CEO) | Stanford CS, Google PM, co-founded Athelas (2015). Led merger with Commure creating $6B healthcare infrastructure company. Focus: scaling AI-native healthcare platform across thousands of US providers. |
| **Eric Lefkofsky** | Tempus AI (Founder/CEO) | Serial entrepreneur (Groupon co-founder). Founded Tempus to apply data science to precision medicine. Focus: building world's largest multimodal clinical data library. |
| **Nathan Hubbard** | Flatiron Health (CEO, appointed 2025) | 20+ years pharma/biopharma experience. Previously global head of healthcare ecosystems at Roche. Built Flatiron's international business. Focus: expanding RWE globally, deepening biopharma partnerships. |
| **Alex Karp** | Palantir (CEO) | PhD philosophy, co-founded Palantir. Focus: enterprise AI adoption, government + commercial data platforms. |
| **Marc Stapley** | Veracyte (CEO) | Appointed June 2021. Focus: global expansion of genomic diagnostics. |
| **Wout Brusselaers** | Deep 6 AI (Founder/CEO) | Founded Deep 6 AI for clinical trial recruitment. Company acquired by Tempus March 2025. |

**What a CEO demands from our platform:**
- Clear revenue narrative: How does clinical data normalization + trial matching generate or protect revenue?
- Defensible competitive moat: proprietary data assets, network effects, switching costs
- Regulatory story that doesn't slow GTM: compliance as enabler, not blocker
- Board-ready metrics: patient screening accuracy, time-to-match, data completeness rates
- Partnership readiness: can we integrate with Metriport, Epic, Cerner ecosystems?

### CTO / Chief Technology Officer

| Person | Company | Background |
|--------|---------|------------|
| **Dhruv Parthasarathy** | Commure (CTO) | MIT CS/AI (BS + MS). Previously Director of AI at Udacity. 8+ years applying ML to healthcare. Leads product, engineering, and design. Philosophy: Apple-level meticulousness applied to healthcare tech. |
| **Shane Colley** | Tempus AI (CTO) | Leads technology organization at Tempus. Background in large-scale data infrastructure and ML systems. |
| **Cat Miller** | Flatiron Health (CTO, current) | One of earliest Flatiron engineers, rose to CTO over 8 years. MIT CS/Math. Led 400-person team through $2B Roche acquisition. |
| **Gil Shklarski** | Flatiron Health (former CTO, 9 years) | PhD. Built Flatiron tech from inception to 350+ professionals across engineering, DevOps, IT, security, product design, data science. Previously Facebook, Microsoft, Israeli Ministry of Defense. Now at Operator Partners. |
| **Shyam Sankar** | Palantir (CTO/EVP) | 20+ years building data/AI platforms. Commissioned into Army Reserve. Focus: enterprise AI operating system, ontology-driven data integration. |

**What a CTO demands from our platform:**
- **Architecture scalability**: Can it handle 10x-100x data volume growth without re-architecture?
- **NLP pipeline reliability**: Ensemble ML + rules-based extraction must have measurable precision/recall with regression testing
- **OMOP mapping quality**: Concept coverage rates, unmapped mention rates, terminology version management
- **API contract stability**: Versioned APIs, backward compatibility guarantees, deprecation policies
- **Tech debt management**: Clear separation of production vs. pilot vs. scaffold maturity tiers
- **Observability**: Distributed tracing, NLP pipeline metrics, data quality dashboards
- **Build vs. buy decisions**: When to use existing FHIR servers vs. build custom, when to use commercial NLP vs. in-house

### Chief Medical Officer (CMO)

| Person | Company | Background |
|--------|---------|------------|
| **Michael Vasconcelles** | Flatiron Health (CMO) | Oncology background. Ensures clinical validity of RWD/RWE products. |

**What a CMO demands from our platform:**
- **Clinical accuracy**: NLP extraction must not miss clinically significant findings (false negatives are potentially dangerous)
- **Assertion/negation handling**: "Patient denies chest pain" vs "Patient reports chest pain" -- must be correctly distinguished
- **Temporal reasoning**: Disease progression timelines must be accurate for trial eligibility
- **Clinical validation methodology**: Annotated gold-standard datasets, clinician review workflows, inter-annotator agreement metrics
- **Terminology alignment**: Extracted concepts must map to clinically meaningful OMOP/SNOMED codes, not just syntactically close ones
- **Patient safety guardrails**: Trial matching must never recommend a contraindicated trial

### Chief Data Officer (CDO)

| Person | Company | Background |
|--------|---------|------------|
| **Melisa Tucker** | Tempus AI (CDO) | MBA Harvard, AB Chemistry Princeton. Previously VP PM & Operations at Flatiron Health (led RWE products), research products at Verily (Alphabet), CPO at Nym Health (AI medical coding). McKinsey alum. |

**What a CDO demands from our platform:**
- **Data provenance and lineage**: Every clinical fact must trace back to source document, extraction method, and mapping confidence
- **Data quality metrics**: Completeness, consistency, accuracy, timeliness dashboards
- **De-identification rigor**: Expert determination method or safe harbor compliance before any data sharing
- **Multimodal data integration**: Clinical notes + lab results + imaging + genomics must coalesce into unified patient representation
- **OMOP CDM compliance**: Must pass OHDSI data quality checks (Achilles, DQD)
- **Competitive data moat**: How do we build proprietary data assets that competitors can't replicate?

### Chief Scientific Officer (CSO)

| Person | Company | Background |
|--------|---------|------------|
| **Kate Sasser, PhD** | Tempus AI (CSO) | PhD integrated biomedical sciences (Ohio State), 20+ years translational research. Previously Genmab (antibody therapeutics), J&J/Janssen (oncology translational research). Focus: multimodal data for personalized medicine. |
| **Giulia Kennedy, PhD** | Veracyte (CSO) | Since 2008. Focus: genomic diagnostic test development. |

**What a CSO demands from our platform:**
- **Research-grade data quality**: Data must be usable for peer-reviewed publications and regulatory submissions
- **Reproducibility**: Same input document must produce identical extraction + mapping results across versions
- **Cohort identification accuracy**: Patient knowledge graphs must enable precise phenotyping for research cohorts
- **Trial eligibility criteria fidelity**: Structured criteria must faithfully represent protocol inclusion/exclusion
- **Longitudinal patient tracking**: Disease trajectory must be reconstructable from knowledge graph

### COO / Chief Operating Officer

| Person | Company | Background |
|--------|---------|------------|
| **Sanjeev Gumber** | Commure (COO) | Operations leadership for healthcare platform scaling. |
| **Deepika Bodapati** | Commure/Athelas (COO) | Co-founded Athelas with Tandon. Stanford. Focus: operational scaling. |
| **Bruce Gottlieb** | Flatiron Health (COO) | Operational leadership for oncology data platform. |
| **Christopher M. Hall** | Veracyte (President/COO) | Focus: global operations and commercial expansion. |

**What a COO demands from our platform:**
- **Operational reliability**: SLAs for webhook ingestion, NLP processing, trial matching response times
- **Cost efficiency**: Infrastructure cost per patient processed, per document ingested
- **Scale planning**: Capacity modeling for 10K, 100K, 1M patients
- **Incident response**: Runbooks for data pipeline failures, NLP degradation, FHIR webhook outages

### Chief Legal Officer / Chief Compliance Officer

| Person | Company | Background |
|--------|---------|------------|
| **Daniel Brian** | Commure/Athelas (CLO) | Oversees regulatory affairs, compliance, legal strategy. Instrumental in HIPAA-compliant software deployments. |

**What a CLO/CCO demands from our platform:**
- **HIPAA compliance**: BAA framework, PHI handling audit trail, minimum necessary access controls
- **Data use agreements**: Template frameworks for sharing de-identified data with pharma partners
- **Consent management**: Patient consent tracking for data use in trial matching
- **Audit trails**: Immutable logs of every data access, transformation, and export
- **Regulatory readiness**: 21 CFR Part 11 alignment for any data submitted to FDA

---

## VP / Director Level

### VP of Information Security / CISO

| Person | Company | Background |
|--------|---------|------------|
| **Justin Berman** | Flatiron Health (VP Information Security) | Led Flatiron to HITRUST CSF certification (March 2024). Focus: ensuring patient data security ahead of regulatory mandates. |

**What a VP InfoSec / CISO demands from our platform:**
- **HITRUST CSF or SOC 2 Type II certification path**: Must be achievable within 12-18 months
- **Encryption**: At-rest (AES-256) and in-transit (TLS 1.3) for all PHI
- **Access controls**: RBAC with principle of least privilege, MFA everywhere
- **Vulnerability management**: Regular penetration testing, dependency scanning, SAST/DAST in CI/CD
- **Incident response plan**: Documented, tested, with <72hr breach notification capability
- **PHI data flow mapping**: Know exactly where PHI lives, moves, and who can access it
- **Webhook security**: HMAC signature verification on all Metriport webhooks, IP allowlisting
- **Database security**: Encrypted connections, parameterized queries (no SQL injection), audit logging on PHI tables
- **Container security**: Image scanning, no root processes, network policies in k8s
- **Secret management**: No hardcoded credentials, vault-based secret rotation

### VP of Engineering

| Person | Company | Background |
|--------|---------|------------|
| **Allison Candido** | Flatiron Health (VP Software Engineering) | Leads engineering team focused on OncoEMR and Flatiron Assist products. Focus: reimagining technology for clinical users. |

**What a VP Engineering demands from our platform:**
- **Engineering excellence**: Code review standards, test coverage thresholds, CI/CD maturity
- **Team scalability**: Can 5 engineers maintain this? 20? Architecture must support parallel workstreams
- **Technical debt tracking**: Quantified debt with paydown plans, not aspirational cleanup
- **On-call sustainability**: Incident rates, MTTR, alert fatigue metrics
- **Developer experience**: Local dev environment parity with prod, fast feedback loops
- **Service reliability**: 99.9%+ uptime for critical paths (webhook ingestion, trial matching API)
- **Database migration safety**: Zero-downtime migrations, rollback plans

### VP of Data Science

| Person | Company | Background |
|--------|---------|------------|
| **Will Shapiro** | Flatiron Health (VP Data Science) | Previously Spotify (personalized recommendation engines using AI/ML). Leads data science and insights engineering team. |

**What a VP Data Science demands from our platform:**
- **Model evaluation framework**: Standardized precision/recall/F1 measurement for NLP extraction
- **A/B testing infrastructure**: Ability to compare NLP model versions on same input data
- **Feature stores**: Structured access to patient features for ML model training
- **Gold standard datasets**: Clinician-annotated corpora for NLP validation
- **Drift detection**: Monitoring for NLP model performance degradation over time
- **Explainability**: Why did the NLP extract this mention? Why did trial matching recommend this trial?

### VP of Product

**What a VP Product demands from our platform:**
- **User-centric design**: Clinical coordinators and research nurses are primary users -- not engineers
- **Workflow integration**: Must fit into existing EHR workflows, not require new tabs/windows
- **Trial matching UX**: One-click screening, clear eligibility/ineligibility explanations, override capabilities
- **Knowledge graph visualization**: Clinicians need intuitive patient timeline views, not raw graph data
- **Feedback loops**: Clinicians can correct NLP errors, and corrections feed back into model improvement
- **Competitive differentiation**: Feature parity with Deep 6 AI, then differentiation through KG-powered insights

### VP of Quality / Regulatory

**What a VP Quality/Regulatory demands from our platform:**
- **Software validation**: IQ/OQ/PQ documentation for clinical-grade software
- **Change control**: Every code change affecting clinical output must have documented review and approval
- **CAPA process**: Corrective and preventive action workflow for NLP errors with clinical impact
- **FDA readiness**: If trial matching is considered SaMD (Software as Medical Device), 21 CFR 820 QMS
- **Traceability matrix**: Requirements -> design -> implementation -> test for all clinical features
- **Risk management**: ISO 14971 risk assessment for patient-facing features

### Director of Clinical Informatics

**What a Director of Clinical Informatics demands from our platform:**
- **Terminology governance**: Who approves new OMOP concept mappings? What's the review workflow?
- **Clinical data model fidelity**: FHIR R4 resources must preserve clinical semantics through normalization
- **Value set management**: Curated, versioned value sets for conditions, medications, procedures
- **Interoperability testing**: Regular testing against Metriport FHIR bundles, HL7 FHIR Connectathon participation
- **Clinical documentation improvement**: NLP must handle abbreviations, misspellings, non-standard terminology
- **OMOP ETL validation**: Systematic comparison of source FHIR data vs. OMOP CDM output

### Director of Data Engineering

**What a Director of Data Engineering demands from our platform:**
- **Pipeline reliability**: Exactly-once processing guarantees for FHIR webhook ingestion
- **Data freshness**: SLAs from document ingestion to knowledge graph availability
- **Schema evolution**: Forward-compatible schema changes without breaking downstream consumers
- **Backfill capabilities**: Ability to re-process historical data through updated NLP pipelines
- **Monitoring**: Pipeline lag, throughput, error rate dashboards with alerting
- **Cost optimization**: Efficient use of compute for NLP processing (batch vs. streaming tradeoffs)

---

## Principal / Staff IC Level

### Principal Engineer

**Typical background**: 10-15+ years, deep domain expertise, system design authority.

**What they demand from our platform:**
- **Clean architecture boundaries**: Clear separation between ingestion, NLP, mapping, KG, and API layers
- **Idempotent operations**: Re-processing a FHIR bundle must not create duplicate clinical facts
- **Failure isolation**: NLP pipeline failure must not block FHIR ingestion or API serving
- **Performance budgets**: Max latency for each pipeline stage, documented and enforced
- **API design quality**: Consistent naming, proper HTTP semantics, HATEOAS where appropriate
- **Database design**: Proper indexing strategy, query performance SLAs, connection pool management
- **Event-driven architecture**: Webhook ingestion -> message queue -> NLP processing -> fact building should be decoupled

### Security Architect

**Typical background**: 8-12+ years, CISSP/CISM certified, healthcare security experience.

**Job requirements (from industry postings):**
- Expertise in HIPAA, HITRUST, SOC 2 compliance frameworks
- AWS/Azure security best practices (IAM, VPC, KMS encryption)
- Threat modeling for healthcare data pipelines
- Penetration testing coordination, vulnerability management

**What they demand from our platform:**
- **Threat model**: Documented attack surface for each component (webhooks, NLP, API, database, KG)
- **Zero-trust networking**: Service-to-service authentication, no implicit trust
- **PHI boundary enforcement**: Clear architectural boundary around PHI, with data flow controls
- **Secrets management**: Vault-based, with rotation policies and audit trails
- **Dependency security**: SBOM generation, CVE monitoring, automated dependency updates
- **Secure SDLC**: Security review gates in PR process, automated SAST/DAST

### Data Architect / Clinical Data Architect

**Typical job requirements:**
- 8+ years in healthcare data architecture
- Deep OMOP CDM expertise, FHIR R4, HL7v2
- Experience with SNOMED CT, LOINC, RxNorm, ICD-10
- ETL pipeline design at scale
- HIPAA-compliant architecture on cloud platforms

**What they demand from our platform:**
- **OMOP CDM adherence**: Strict conformance to OMOP CDM v5.4, not a custom variant
- **Vocabulary management**: Athena vocabulary updates on defined cadence, with regression testing
- **Concept mapping quality**: Multi-candidate ranking with confidence scores, human review workflow for ambiguous mappings
- **Clinical data lineage**: Full provenance from source FHIR resource -> extracted mention -> OMOP concept -> clinical fact -> KG node
- **CDM validation**: Automated Achilles and DataQualityDashboard runs on OMOP output

---

## IC Level Roles

### Software Engineer (Backend)

**Typical requirements**: Python/Java/Go, REST APIs, PostgreSQL, Redis, message queues, Docker/K8s.

**What they flag as risks in our platform:**
- API endpoint explosion (726 endpoints is a lot -- discoverability and consistency concerns)
- Service file count (187 service files) -- how do you find the right service for a task?
- Multiple NLP pipeline variants that may diverge in behavior
- WebSocket reliability for real-time trial matching updates
- Database connection management under load

### Software Engineer (Frontend)

**Typical requirements**: TypeScript, React/Next.js, Tailwind, accessible design, real-time data visualization.

**What they flag as risks:**
- Knowledge graph visualization performance with large patient graphs
- Real-time WebSocket state management complexity
- Accessible design for clinical users (WCAG compliance)
- Consistent error handling for API failures in the UI

### Data Scientist / ML Engineer

**Typical requirements**: Python, NLP (transformers, spaCy, John Snow Labs), clinical data, OMOP, statistics.

**What they demand from our platform:**
- **Experiment tracking**: MLflow or equivalent for NLP model versioning
- **Evaluation datasets**: Gold-standard annotated clinical notes for each extraction type
- **Feature engineering**: Access to structured patient features from the knowledge graph
- **Model serving infrastructure**: Low-latency inference for real-time NLP extraction
- **Feedback incorporation**: Clinician corrections must flow back to model retraining pipeline
- **Clinical NLP benchmarks**: Performance against established benchmarks (i2b2, n2c2, OHNLP)

### NLP Engineer

**Typical requirements**: 3+ years ML/NLP, clinical text experience, transformer models, rule-based systems, UMLS/SNOMED expertise.

**What they demand from our platform:**
- **Hybrid pipeline support**: Rule-based + ML ensemble must be configurable per extraction type
- **Assertion detection**: Negation, hypothetical, family history, conditional must be handled
- **Section detection**: Chief complaint vs. assessment vs. plan affect mention interpretation
- **Pre-processing robustness**: Handle OCR artifacts, abbreviations, misspellings, non-standard formatting
- **Custom model deployment**: Easy path from trained model to production serving
- **Annotation tooling**: Integrated annotation UI for creating training data

### FHIR Integration Specialist

**Typical requirements**: HL7 FHIR R4, HL7v2, healthcare interoperability, integration engines (Mirth, InterSystems), Epic/Cerner experience.

**Salary range**: $129K-$200K (2025 market data)

**What they demand from our platform:**
- **FHIR R4 conformance**: Strict resource validation on Metriport webhooks
- **Resource mapping completeness**: Handle Patient, Condition, Observation, MedicationRequest, DiagnosticReport, DocumentReference, Encounter, Procedure, AllergyIntolerance at minimum
- **Bundle processing**: Proper handling of Transaction vs. Batch bundles, reference resolution
- **Error handling**: Graceful degradation when receiving malformed or partial FHIR resources
- **Terminology translation**: ICD-10 -> SNOMED -> OMOP concept mapping must handle all common terminologies
- **Provenance tracking**: Every data element traces back to specific FHIR resource + element path

### QA Engineer

**Typical requirements**: Healthcare domain, regulatory testing, automated testing, HIPAA compliance testing.

**What they demand from our platform:**
- **Test coverage for clinical paths**: NLP extraction, OMOP mapping, trial matching must have >90% test coverage
- **Regression testing**: Automated regression suite that runs on every PR for NLP pipeline changes
- **Golden dataset testing**: Fixed input documents with expected outputs, validated by clinicians
- **Load testing**: Performance under realistic concurrent user loads
- **Security testing**: Regular OWASP Top 10 testing, PHI access audit verification
- **Compliance testing**: HIPAA technical safeguard verification (access controls, audit logs, encryption)

### Clinical Data Analyst

**Typical requirements**: Healthcare data (EHR, claims), SQL, OMOP CDM, clinical terminologies, basic statistics.

**What they demand from our platform:**
- **Query-friendly data model**: Easy to write SQL against OMOP CDM for cohort identification
- **Data dictionaries**: Clear documentation of every table, column, and concept domain
- **Data quality reports**: Automated reports on missing data, outliers, inconsistencies
- **Patient timeline views**: Chronological view of all clinical events for a patient
- **Export capabilities**: Bulk export in OMOP CDM format for research partners

### DevOps / SRE Engineer

**Typical requirements**: Kubernetes, Terraform, AWS/GCP, CI/CD, monitoring (Prometheus, Grafana, Datadog), HIPAA-compliant infrastructure.

**What they demand from our platform:**
- **Infrastructure as code**: All infrastructure defined in Terraform/Pulumi, no manual configuration
- **Observability stack**: Metrics, logs, traces for every service (especially NLP pipeline and webhook processing)
- **Auto-scaling**: NLP processing must scale with document ingestion volume
- **Disaster recovery**: RPO/RTO defined and tested, multi-region capable
- **Secret rotation**: Automated rotation for database credentials, API keys, webhook secrets
- **Cost monitoring**: Per-service cost attribution, alerting on spend anomalies

---

## Role-by-Role Platform Concerns Matrix

This matrix maps each role to their PRIMARY concerns when evaluating our specific platform (FHIR ingestion -> NLP -> OMOP mapping -> KG -> trial matching).

| Role | Top 3 Concerns | Risk They Flag | What They Push For |
|------|----------------|----------------|-------------------|
| **CEO** | Revenue model, competitive moat, regulatory story | "We'll get outpaced by Tempus/Deep 6 AI" | Clear differentiation, partnership readiness, compliance-as-feature |
| **CTO** | Architecture scalability, NLP reliability, tech debt | "187 service files and 726 endpoints is unsustainable" | Service consolidation, maturity labeling, observability |
| **CMO** | Clinical accuracy, patient safety, validation methodology | "NLP might miss a cancer diagnosis or mis-match a trial" | Gold-standard validation, clinician-in-the-loop, safety guardrails |
| **CDO** | Data quality, provenance, competitive data assets | "We can't prove our data is better than competitors'" | Data quality dashboards, lineage tracking, OHDSI compliance |
| **CSO** | Research-grade quality, reproducibility, cohort precision | "This data won't pass peer review scrutiny" | Reproducible pipelines, versioned outputs, publication-ready exports |
| **CLO/CCO** | HIPAA compliance, consent management, audit trails | "A data breach would be existential" | PHI flow mapping, BAA framework, immutable audit logs |
| **VP InfoSec** | Encryption, access controls, vulnerability management | "Webhook endpoints are attack surface" | HITRUST path, zero-trust, penetration testing, SBOM |
| **VP Engineering** | Code quality, developer productivity, reliability | "Can we hire and onboard engineers quickly?" | Test coverage, CI/CD maturity, documentation, modular architecture |
| **VP Data Science** | Model evaluation, drift detection, explainability | "We can't tell if NLP performance is degrading" | MLOps infrastructure, gold-standard datasets, A/B testing |
| **VP Product** | User workflows, clinical coordinator UX, differentiation | "Clinicians won't adopt complex tools" | One-click screening, EHR integration, intuitive KG visualization |
| **VP Quality/Regulatory** | Software validation, change control, SaMD classification | "FDA could classify this as a medical device" | IQ/OQ/PQ, traceability matrix, ISO 14971 risk assessment |
| **Dir. Clinical Informatics** | Terminology governance, FHIR fidelity, value sets | "OMOP mappings are drifting from clinical meaning" | Terminology review workflows, value set curation, FHIR validation |
| **Dir. Data Engineering** | Pipeline reliability, data freshness, backfill capability | "A stuck webhook could delay trial matching by hours" | Exactly-once processing, monitoring, schema evolution strategy |
| **Principal Engineer** | Architecture boundaries, idempotency, failure isolation | "NLP failure cascades to the entire platform" | Event-driven decoupling, performance budgets, clean interfaces |
| **Security Architect** | Threat model, PHI boundaries, secure SDLC | "No documented threat model for the webhook pipeline" | Threat modeling, security gates in CI, dependency scanning |
| **NLP Engineer** | Hybrid pipeline quality, assertion detection, annotation | "Rule-based and ML pipelines may contradict each other" | Ensemble conflict resolution, annotation tooling, clinical NLP benchmarks |
| **FHIR Specialist** | R4 conformance, resource mapping, error handling | "Metriport sends non-conformant bundles sometimes" | Strict FHIR validation, graceful degradation, resource coverage testing |
| **QA Engineer** | Test coverage, regression testing, compliance testing | "No regression suite for NLP changes" | Golden datasets, automated regression, OWASP testing |
| **Data Scientist** | Experiment tracking, evaluation datasets, feedback loops | "We can't reproduce last month's model results" | MLOps, gold-standard corpora, clinician feedback integration |
| **DevOps/SRE** | Observability, auto-scaling, disaster recovery | "No defined RPO/RTO for the database" | IaC, monitoring stack, auto-scaling, DR testing |
| **Clinical Data Analyst** | Query access, data documentation, export capabilities | "I can't find where lab results are stored in OMOP" | Data dictionaries, quality reports, OMOP CDM export |

---

## Key Organizational Patterns Observed

### 1. Engineering Organization Size at Scale
- Flatiron Health: 350-400 engineers at peak (under Gil Shklarski / Cat Miller)
- Tempus AI: Estimated 500+ technical staff (post-acquisitions)
- Commure: Engineering + product + design under single CTO (Dhruv Parthasarathy)
- Pattern: Healthcare data companies typically run 40-60% of headcount in engineering/data

### 2. Clinical + Technical Dual Leadership
- Every company has both a CTO AND a CMO/CSO
- Clinical leadership has veto power on anything patient-facing
- Pattern: Clinical validation is a first-class engineering concern, not an afterthought

### 3. Security as Organizational Priority
- Flatiron: Dedicated VP of Information Security (Justin Berman), HITRUST certified
- Pattern: CISO/VP InfoSec is a top-10 hire, not a "we'll get to it" role
- Healthcare breach cost: $11.3M average in 2025 (highest of any industry)

### 4. Data Leadership as Distinct Function
- Tempus: Dedicated CDO (Melisa Tucker) separate from CTO
- Pattern: Data quality, governance, and strategy is a C-level function, not buried under engineering

### 5. Forward-Deployed Engineering Model
- Commure and Palantir both use forward-deployed engineers who work directly with healthcare customers
- Pattern: Healthcare platform companies need engineers who understand clinical workflows

### 6. Regulatory/Quality as Early Investment
- Flatiron: SOC 2 + HITRUST + HIPAA + GDPR + 21 CFR 11
- Pattern: Billion-dollar healthcare companies invest in compliance infrastructure early, not retroactively

---

## Implications for Our Platform

Based on this research, the organizational roles at companies like these would evaluate our platform with these top priorities:

### Must-Have (Table Stakes)
1. HIPAA compliance with documented PHI data flows and audit trails
2. HITRUST or SOC 2 Type II certification path
3. Clinical validation methodology for NLP extraction accuracy
4. OMOP CDM conformance with standard vocabulary management
5. FHIR R4 conformance testing for Metriport webhook ingestion
6. Encryption at rest and in transit for all PHI

### Should-Have (Competitive Requirement)
1. MLOps infrastructure for NLP model versioning and evaluation
2. Clinician-in-the-loop validation and feedback workflows
3. Data quality dashboards with OHDSI-standard metrics
4. Full data provenance/lineage from source document to clinical fact
5. Threat model and security architecture documentation
6. IQ/OQ/PQ software validation documentation

### Nice-to-Have (Differentiation)
1. Real-time trial matching with sub-second response times
2. Knowledge graph-powered patient insights beyond simple matching
3. Multi-site federated data analysis without PHI sharing
4. Publication-ready data exports for research partners
5. EHR-embedded workflow integration (SMART on FHIR apps)

---

*Research compiled February 2026. Sources include company websites, SEC filings, press releases, job postings, and industry publications.*
