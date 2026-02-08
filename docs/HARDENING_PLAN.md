# Platform Hardening Plan — By Role

> Every role at a billion-dollar clinical data SaaS would walk through the door with different priorities.
> This plan is organized by WHO would demand each item, not just by security tier.
> Synthesized from research on Commure ($6B), Tempus ($TEM), Flatiron ($1.9B), Palantir, Deep 6 AI, TriNetX, Medidata ($5.8B), Veeva, Komodo Health ($3.3B).

---

## CEO / Founder

*Reference: Tanay Tandon (Commure), Eric Lefkofsky (Tempus), Nathan Hubbard (Flatiron)*

The CEO cares about revenue narrative, competitive moat, and regulatory story that doesn't slow GTM.

- [ ] **Define revenue model** — Choose pricing structure: SaaS subscription ($50-500K/yr) + per-enrolled-patient fees ($2,000-$15,000) + data licensing. Tempus does $81M/quarter in data licensing alone. *(Business critical)*
- [ ] **Build competitive moat documentation** — What's our proprietary data asset? TriNetX has 150M EHRs federated. Tempus has multimodal genomic+clinical. Komodo has 330M patients. What's ours? *(Strategy)*
- [ ] **Create board-ready metrics dashboard** — Patient screening accuracy, time-to-match, data completeness rates, screen-to-enroll ratio, pipeline throughput. *(Investor readiness)*
- [ ] **Partnership readiness assessment** — Can we integrate with Metriport, Epic, Cerner? Do we have BAA templates ready? Can we respond to a pharma RFP? *(BD readiness)*
- [ ] **Position compliance as sales enabler** — SOC 2 Type II is table stakes for enterprise pharma. 80%+ of hospitals require HITRUST from vendors. Frame compliance work as revenue unlocking, not cost. *(GTM strategy)*

---

## CTO

*Reference: Dhruv Parthasarathy (Commure), Cat Miller (Flatiron), Shane Colley (Tempus), Gil Shklarski (Flatiron, former)*

The CTO cares about architecture scalability, NLP reliability, tech debt, and whether this can be maintained by a real team.

- [ ] **Architecture scalability audit** — Can this handle 10x-100x data volume? What breaks first? Document capacity limits for webhook ingestion, NLP processing, graph queries. *(Architecture)*
- [ ] **Consolidate service variants** — 187 service files and 726 endpoints is a lot. Map which are Production vs Pilot vs Scaffold. Block Scaffold endpoints in production. *(Tech debt)*
- [ ] **NLP pipeline regression testing** — Ensemble ML + rules-based extraction must have measurable precision/recall. Every PR that touches NLP must run regression suite. *(Reliability)*
- [ ] **OMOP mapping quality dashboard** — Concept coverage rates, unmapped mention rates, terminology version tracking. Alert when vocabulary updates break existing mappings. *(Data quality)*
- [ ] **API contract stability** — Versioned APIs, backward compatibility guarantees, deprecation policies. 726 endpoints need consistent naming and proper HTTP semantics. *(API maturity)*
- [ ] **Observability stack** — Distributed tracing across webhook ingestion → NLP → OMOP mapping → KG build → trial match. Pipeline lag, throughput, error rate dashboards with alerting. *(Operations)*
- [ ] **Developer experience** — Local dev environment parity with prod. Fast feedback loops. Can a new engineer onboard and ship in week 1? *(Team scalability)*
- [ ] **Build vs buy decisions** — Document rationale for in-house NLP vs commercial (John Snow Labs, AWS Comprehend Medical). In-house FHIR server vs HAPI FHIR. In-house KG vs commercial graph. *(Strategy)*

---

## CMO / Chief Medical Officer

*Reference: Michael Vasconcelles (Flatiron)*

The CMO cares about clinical accuracy, patient safety, and whether this could hurt someone.

- [ ] **Add "clinician review required" labeling** — All match outputs must prominently state this. Required for CDS exemption under Cures Act Criterion 4. No autonomous enrollment. *(Patient safety, regulatory)*
- [ ] **Assertion/negation validation** — "Patient denies chest pain" vs "Patient reports chest pain" must be correctly distinguished. Build test suite for assertion detection. *(Clinical accuracy)*
- [ ] **Temporal reasoning validation** — Disease progression timelines must be accurate for trial eligibility. "Diagnosed 6 months ago" vs "diagnosed 6 years ago" changes everything. *(Clinical accuracy)*
- [ ] **Clinical validation study design** — Plan retrospective chart review (n=500+), prospective concordance study (6-12 months), safety outcome monitoring. Published benchmarks: TrialGPT 87.3%, hybrid systems up to 94%. *(Validation)*
- [ ] **Patient safety guardrails** — Trial matching must never recommend a contraindicated trial. Build exclusion criteria enforcement with hard stops, not just warnings. *(Patient safety)*
- [ ] **False negative monitoring** — False negatives (missing eligible patients) are MORE harmful than false positives. Target sensitivity >90%. Track and report miss rates. *(Clinical quality)*
- [ ] **Clinician feedback loop** — When a clinician overrides a match (approves or rejects), capture that as training signal. Track override rates as a system quality metric. *(Continuous improvement)*

---

## CDO / Chief Data Officer

*Reference: Melisa Tucker (Tempus, ex-Flatiron, ex-Verily)*

The CDO cares about data provenance, data quality, and building a defensible data asset.

- [ ] **Data lineage tracking** — Every clinical fact must trace back to: source FHIR resource → extraction method → mention with offsets → mapping confidence → selected OMOP concept. *(Provenance)*
- [ ] **Data quality dashboard** — Completeness, consistency, accuracy, timeliness metrics. How many patients have full demographic data? How many have lab results? How many conditions are mapped to OMOP? *(Quality)*
- [ ] **OHDSI data quality checks** — Run Achilles and DataQualityDashboard on OMOP output. These are the standard tools the research community uses. *(Standards compliance)*
- [ ] **De-identification pipeline** — Expert determination method or Safe Harbor compliance before any data sharing with pharma. This unlocks the data licensing revenue stream. *(Revenue enablement)*
- [ ] **Multimodal data integration plan** — Clinical notes + lab results + imaging + genomics must coalesce into unified patient representation in the knowledge graph. *(Data architecture)*
- [ ] **Data completeness scoring per patient** — For trial matching, know whether you have enough data to make a confident determination. Flag "UNKNOWN" vs "NOT MET" when data is missing. *(Matching quality)*
- [ ] **Competitive data moat strategy** — How do we build proprietary data assets that competitors can't replicate? TriNetX built a federated network. Tempus built multimodal. What's ours? *(Strategy)*

---

## VP Product

*Reference: Flatiron, Deep 6 AI product patterns*

The VP Product cares about user workflows, clinical coordinator UX, and differentiation.

- [ ] **Clinical coordinator UX audit** — Primary users are research nurses and clinical coordinators, not engineers. One-click screening, clear eligibility explanations, override capabilities. *(Usability)*
- [ ] **Per-match explainability engine** — For each patient-trial pair, show which criteria matched/failed with links to source evidence (specific note, lab result, medication). Pharma RFP Tier 2 requirement. *(Differentiation)*
- [ ] **Screen failure analytics** — Track screen-to-enroll ratios. This is the #1 ROI metric for pharma sponsors. A platform that reduces screen failures by 30-50% saves $1.2M per study. *(Revenue justification)*
- [ ] **Knowledge graph visualization** — Clinicians need intuitive patient timeline views, not raw graph data. Chronological view of all clinical events for a patient. *(Usability)*
- [ ] **Patient-facing screener** — Landing pages, chat interfaces, self-service eligibility checks. Drives direct-to-patient recruitment channel. *(Feature — table stakes)*
- [ ] **Site referral orchestration** — Route matched patients to appropriate trial sites. Operationalizes the match into actual enrollment. *(Feature — table stakes)*
- [ ] **Funnel analytics dashboard** — Screen-fail reasons, conversion rates, time-to-enroll by trial, by site, by therapeutic area. Sponsors won't pay without measurable ROI. *(Revenue critical)*
- [ ] **FDORA diversity enrollment tools** — Tracking, reporting, and active enrollment goal monitoring for DAP compliance. Effective Dec 2025. Both compliance obligation and sales differentiator. *(Regulatory + revenue)*
- [ ] **Protocol optimization feedback** — Use matching data to recommend I/E criteria changes that reduce screen failures. $1.2M savings per study when screen failure rate drops below 40%. *(Differentiation)*

---

## VP Engineering

*Reference: Allison Candido (Flatiron)*

The VP Eng cares about code quality, team scalability, and whether this is maintainable.

- [ ] **Test coverage for clinical paths** — NLP extraction, OMOP mapping, trial matching must have >90% test coverage. Currently unknown. *(Quality)*
- [ ] **CI/CD maturity** — Add SAST (Bandit), dependency scanning (pip-audit, npm audit), container scanning (Trivy) to pipeline. Currently none of these exist. *(Engineering excellence)*
- [ ] **On-call sustainability** — Define incident rates, MTTR targets, alert fatigue metrics. Build runbooks for data pipeline failures, NLP degradation, webhook outages. *(Operations)*
- [ ] **Database migration safety** — Zero-downtime migration strategy. Rollback plans. The `deleted_at` column issue we just hit is an example of schema drift. *(Reliability)*
- [ ] **Service reliability SLAs** — 99.9%+ uptime for critical paths (webhook ingestion, trial matching API). Define and measure. *(Operations)*
- [ ] **Technical debt quantification** — Inventory the Production/Pilot/Scaffold tiers. Quantify debt with paydown plans, not aspirational cleanup. *(Planning)*
- [ ] **Create docker-compose.prod.yml** — Separate production compose with all hardening applied, no dev defaults, no volume mounts, no exposed DB ports. *(DevOps)*

---

## VP Data Science

*Reference: Will Shapiro (Flatiron, ex-Spotify)*

The VP Data Science cares about model evaluation, drift detection, and explainability.

- [ ] **Model evaluation framework** — Standardized precision/recall/F1 measurement for NLP extraction. Per-entity-type metrics (conditions, medications, lab values, procedures). *(ML ops)*
- [ ] **Gold standard datasets** — Clinician-annotated corpora for NLP validation. Minimum 200 annotated documents. Two annotators per document, target Cohen's kappa >0.75. *(Validation)*
- [ ] **A/B testing infrastructure** — Compare NLP model versions on same input data. Must maintain audit trail of which algorithm version produced each match. *(Experimentation)*
- [ ] **Drift detection** — Monitor NLP performance degradation over time. Input distribution drift, concept drift, vocabulary drift. Pre-COVID models degraded substantially. *(Monitoring)*
- [ ] **Explainability for all stakeholders** — Clinicians need criteria-level pass/fail. Sponsors need aggregate match quality. Patients need plain-language explanations. Regulators need full audit trail. *(Trust)*
- [ ] **Fairness audit framework** — Match rates by race, ethnicity, sex, age, geography. FDA January 2025 draft guidance explicitly addresses bias. FDORA DAP requires demographic enrollment goals. *(Compliance + ethics)*
- [ ] **Model governance framework** — Model registry, validation protocol, bias audit schedule (quarterly), drift monitoring (weekly), incident response, retraining schedule, model cards. *(ML ops maturity)*
- [ ] **Experiment tracking** — MLflow or equivalent for NLP model versioning. Reproducible results. "Same input document must produce identical extraction results across versions." *(Reproducibility)*

---

## CSO / Chief Scientific Officer

*Reference: Kate Sasser (Tempus), Giulia Kennedy (Veracyte)*

The CSO cares about research-grade quality and whether this data can survive peer review.

- [ ] **Reproducibility** — Same input document must produce identical extraction + mapping results across pipeline versions. Version-pin all models, vocabularies, and mapping tables. *(Research quality)*
- [ ] **Publication-ready data exports** — OMOP CDM format, FHIR bulk export, cohort definition export. Research partners need standard formats. *(Partnerships)*
- [ ] **Cohort identification accuracy** — Patient knowledge graphs must enable precise phenotyping for research cohorts. Validate against manual chart review. *(Research utility)*
- [ ] **Trial eligibility criteria fidelity** — Structured criteria must faithfully represent protocol inclusion/exclusion. Measure criteria parsing accuracy (target >89% per published benchmarks). *(Data quality)*
- [ ] **Longitudinal patient tracking** — Disease trajectory must be reconstructable from knowledge graph. Temporal ordering of events, treatment sequences, outcome tracking. *(Research utility)*
- [ ] **Publish validation results** — Peer-reviewed venue. Every major competitor (Flatiron, Tempus, Deep 6) has published. Required for credibility. *(Market credibility)*

---

## CISO / VP Information Security

*Reference: Justin Berman (Flatiron, led HITRUST cert)*

The CISO cares about everything that could cause a breach. Healthcare breach cost: $11.3M average.

- [ ] **Remove hardcoded credentials** — PostgreSQL, Neo4j, API keys all in docker-compose plaintext. Move to `.env` (git-ignored). *(Critical — 2h)*
- [ ] **Enable TLS everywhere** — nginx TLS currently commented out. Internal services on plaintext. Enable TLS 1.2+ external, mTLS internal. *(Critical — 4h)*
- [ ] **Fix auth defaults** — `AUTH_BYPASS_DEV=true` and `AUTH_ENABLED=false` as defaults is a production incident waiting to happen. *(Critical — 1h)*
- [ ] **Wildcard CORS** — `Access-Control-Allow-Origin: *` in nginx. Replace with explicit allowlist. *(Critical — 1h)*
- [ ] **Network segmentation** — Database ports exposed to host. Frontend can reach databases. Implement Docker network isolation. *(High — 4h)*
- [ ] **Webhook HMAC verification** — Metriport webhooks must be verified with constant-time HMAC comparison. *(High — 4h)*
- [ ] **PHI data flow mapping** — Document exactly where PHI lives, moves, and who can access it across all services. *(Compliance — 1 week)*
- [ ] **Comprehensive audit logging** — All PHI access: who, what, when, from where. Immutable, tamper-evident, 6-year retention. *(HIPAA — 2-3 days)*
- [ ] **RBAC with least privilege** — Fine-grained permissions on all 726 endpoints. *(High — 2-3 weeks)*
- [ ] **Vulnerability management program** — Regular pen testing, dependency scanning, SAST/DAST in CI/CD. *(Ongoing)*
- [ ] **Incident response plan** — Documented, tested, <24h breach notification (HIPAA 2025 NPRM requirement). *(Compliance)*
- [ ] **SOC 2 Type II path** — Gap analysis, then 6-12 month certification process. Budget: $20K-$100K. *(Enterprise sales enabler)*
- [ ] **HITRUST CSF r2 path** — Required by 80%+ of hospitals. Budget: $60K-$200K, 12-18 months. *(Market access)*

---

## VP Quality / Regulatory

*Reference: Flatiron (SOC 2 + HITRUST + HIPAA + GDPR + 21 CFR 11)*

The VP Quality cares about whether the FDA will classify this as a medical device and whether you can prove the software works.

- [ ] **Regulatory determination document** — Establish CDS exemption rationale under Cures Act Section 520(o). All 4 criteria must be documented. *(Regulatory — 1 week)*
- [ ] **Intended use statement** — "Clinical decision support for healthcare professionals" must be prominent in product and documentation. *(Regulatory — 1h)*
- [ ] **IQ/OQ/PQ documentation** — Installation, Operational, and Performance Qualification for clinical-grade software. GAMP 5 2nd Edition framework. *(Quality — 2-4 weeks)*
- [ ] **Change control process** — Every code change affecting clinical output must have documented review and approval. Not just PR review — formal change control. *(Quality)*
- [ ] **CAPA system** — Corrective and Preventive Action workflow for NLP errors with clinical impact. When a false negative is discovered, what's the formal response? *(Quality)*
- [ ] **Traceability matrix** — Requirements → design → implementation → test for all clinical features. Required for IEC 62304 if SaMD classification pursued. *(Regulatory)*
- [ ] **ISO 14971 risk assessment** — FMEA for NLP extraction, mapping, eligibility logic failures. FTA for "wrong patient enrolled in trial." *(Patient safety)*
- [ ] **SaMD contingency plan** — IEC 62304 Class B lifecycle + ISO 13485 QMS readiness, in case FDA reclassifies. EU MDR requires Class IIa minimum with Notified Body. *(Regulatory)*

---

## Director of Clinical Informatics

The Dir of Clinical Informatics cares about terminology, FHIR fidelity, and whether the mappings make clinical sense.

- [ ] **Terminology governance workflow** — Who approves new OMOP concept mappings? What's the review process? Establish a terminology committee or at minimum a review queue. *(Governance)*
- [ ] **FHIR R4 conformance testing** — Validate against US Core profiles. Handle Patient, Condition, Observation, MedicationRequest, DiagnosticReport, DocumentReference, Encounter, Procedure, AllergyIntolerance at minimum. *(Interoperability)*
- [ ] **Value set management** — Curated, versioned value sets for conditions, medications, procedures. Track which SNOMED/ICD-10/LOINC/RxNorm versions are in use. *(Terminology)*
- [ ] **OMOP ETL validation** — Systematic comparison of source FHIR data vs OMOP CDM output. Are we losing clinical semantics in translation? *(Data quality)*
- [ ] **Vocabulary update regression testing** — SNOMED CT, RxNorm, LOINC release quarterly+. Each update can break existing mappings. Snapshot baseline, apply update, diff analysis, impact assessment. *(Stability)*
- [ ] **Clinical abbreviation handling** — NLP must handle abbreviations, misspellings, non-standard terminology. "HTN" = hypertension. "SOB" = shortness of breath. "CA" = cancer or calcium? *(NLP quality)*

---

## Director of Data Engineering

The Dir of Data Engineering cares about pipeline reliability, data freshness, and not getting paged at 3am.

- [ ] **Exactly-once processing guarantees** — FHIR webhook ingestion must be idempotent. Re-processing a bundle must not create duplicate clinical facts. *(Reliability)*
- [ ] **Data freshness SLAs** — Define: how long from document ingestion to knowledge graph availability to trial match? Pharma expects <24-48 hours. *(SLA)*
- [ ] **Schema evolution strategy** — Forward-compatible schema changes without breaking downstream consumers. The `deleted_at` column issue we hit is a symptom of this gap. *(Architecture)*
- [ ] **Backfill capability** — When NLP models improve, can we re-process all historical data through the updated pipeline? Without duplicates? *(Operations)*
- [ ] **Pipeline monitoring dashboard** — Ingestion rate, NLP throughput, mapping success rate, graph build time, error rates. Alert on stalls. *(Observability)*
- [ ] **Event-driven decoupling** — Webhook ingestion → message queue → NLP processing → fact building should be decoupled. NLP failure must not block ingestion or API serving. *(Architecture)*
- [ ] **Cost optimization** — Efficient compute for NLP processing. Batch vs streaming tradeoffs. What's the cost per patient processed, per document ingested? *(Economics)*

---

## NLP Engineer

The NLP Engineer cares about hybrid pipeline quality, assertion detection, and whether the extraction actually works on real clinical text.

- [ ] **Hybrid pipeline conflict resolution** — When rule-based and ML pipelines disagree on an extraction, what wins? Define ensemble resolution strategy. *(Architecture)*
- [ ] **Assertion detection test suite** — Negation ("no evidence of"), hypothetical ("if patient develops"), family history ("mother had"), conditional ("consider if"). Each must be tested. *(NLP quality)*
- [ ] **Section detection** — Chief complaint vs Assessment vs Plan affect mention interpretation. "Diabetes" in family history is different from "Diabetes" in active problems. *(NLP quality)*
- [ ] **Pre-processing robustness** — Handle OCR artifacts, abbreviations, misspellings, non-standard formatting, mixed encodings. *(NLP robustness)*
- [ ] **Annotation tooling** — Integrated annotation UI for creating training data. Clinician corrections should feed back into model improvement pipeline. *(ML ops)*
- [ ] **Clinical NLP benchmarks** — Measure performance against established benchmarks (i2b2, n2c2, OHNLP). Published: GPT-4 at 87% on n2c2 2018. *(Validation)*
- [ ] **Custom model deployment path** — Easy path from trained model to production serving. Model versioning, canary deployment, rollback capability. *(ML ops)*

---

## FHIR Integration Specialist

The FHIR Specialist cares about conformance, resource coverage, and graceful failure.

- [ ] **FHIR R4 resource validation** — Strict validation on Metriport webhook payloads. Reject malformed resources with detailed error logging (but never log PHI in errors). *(Data quality)*
- [ ] **Resource mapping completeness** — Verify handling of: Patient, Condition, Observation, MedicationRequest, DiagnosticReport, DocumentReference, Encounter, Procedure, AllergyIntolerance, Immunization. *(Coverage)*
- [ ] **Bundle processing** — Proper handling of Transaction vs Batch bundles. Reference resolution within bundles. *(Conformance)*
- [ ] **Error handling and graceful degradation** — When Metriport sends non-conformant bundles (it happens), quarantine and continue, don't crash. *(Reliability)*
- [ ] **Terminology translation** — ICD-10 → SNOMED → OMOP concept mapping must handle all common terminologies. Test with real-world variety. *(Interoperability)*
- [ ] **Provenance tracking** — Every data element traces back to specific FHIR resource + element path. "This lab value came from Observation/abc123.valueQuantity." *(Lineage)*

---

## QA Engineer

The QA Engineer cares about test coverage, regression testing, and knowing when something breaks.

- [ ] **Golden dataset testing** — Fixed input documents with clinician-validated expected outputs. 200+ annotated notes, 50+ trial criteria, 200+ patient profiles. *(Foundation)*
- [ ] **OMOP mapping regression suite** — 500+ curated term-to-concept mappings. Run on every vocabulary update and every PR that touches mapping code. *(Regression)*
- [ ] **Eligibility logic test framework** — Property-based tests: clearly eligible, clearly ineligible, boundary cases (age=18 exactly), missing data, conflicting data, complex boolean AND/OR/NOT. *(Logic testing)*
- [ ] **Load testing** — Performance under realistic concurrent user loads. What happens with 100 simultaneous webhook deliveries? 1000 concurrent API requests? *(Performance)*
- [ ] **End-to-end pipeline tests** — Document ingestion through NLP through OMOP mapping through fact building through eligibility evaluation. Run on every deploy. *(Integration)*
- [ ] **Security testing** — OWASP Top 10 testing, PHI access audit verification, compliance testing for HIPAA technical safeguards. *(Security)*

---

## COO

*Reference: Sanjeev Gumber (Commure), Bruce Gottlieb (Flatiron)*

The COO cares about operational reliability, cost efficiency, and scale planning.

- [ ] **SLA definitions** — Response time for webhook ingestion (<500ms), NLP processing (<5s per document), trial matching API (<2s), knowledge graph query (<1s). *(Operations)*
- [ ] **Cost per patient processed** — Infrastructure cost modeling. What does it cost to ingest, extract, map, match one patient? How does it scale? *(Economics)*
- [ ] **Capacity planning** — Model for 10K, 100K, 1M patients. What's the infrastructure cost at each tier? Where are the bottlenecks? *(Planning)*
- [ ] **Incident response runbooks** — Data pipeline stall, NLP degradation, FHIR webhook outage, database failover, auth system failure. *(Operations)*
- [ ] **Disaster recovery** — RPO/RTO defined and tested. Backup encryption. Multi-region capability assessment. *(Reliability)*

---

## CLO / Compliance Officer

*Reference: Daniel Brian (Commure/Athelas CLO)*

The Compliance Officer cares about not getting sued and not getting fined.

- [ ] **BAA framework** — Business Associate Agreement templates for all data sharing relationships. Required for every entity that touches PHI. *(HIPAA)*
- [ ] **Consent management system** — Opt-in at GDPR/MHMDA level. Washington My Health My Data Act has no revenue threshold and private right of action. *(Privacy)*
- [ ] **Data use agreements** — Template frameworks for sharing de-identified data with pharma partners. Different templates for different use cases (research, commercial, regulatory). *(Legal)*
- [ ] **Right-to-deletion** — GDPR, CCPA, MHMDA all require this. Cascade through clinical facts, KG nodes. Flag (don't delete) audit logs. *(Privacy)*
- [ ] **Audit trail for 21 CFR Part 11** — Secure, time-stamped, immutable. Previously recorded information must NOT be obscured by changes. No user (including admins) can modify audit trails. *(Regulatory)*
- [ ] **IRB compliance framework** — When does trial matching require IRB review? HIPAA preparatory-to-research allows internal screening, but external disclosure needs IRB waiver. *(Research compliance)*
- [ ] **State privacy law compliance** — Patchwork: Washington MHMDA, Nevada SB 370, Connecticut amendments, CCPA/CPRA. Default to highest standard (GDPR/MHMDA-level opt-in). *(Legal)*

---

## DevOps / SRE

The DevOps engineer cares about infrastructure as code, observability, and not getting paged at 3am.

- [ ] **Infrastructure as code** — All infrastructure defined in Terraform/Pulumi. No manual configuration. Reproducible environments. *(DevOps)*
- [ ] **Observability stack** — Metrics, logs, traces for every service. Especially NLP pipeline and webhook processing. Prometheus + Grafana or Datadog. *(Monitoring)*
- [ ] **Auto-scaling** — NLP processing must scale with document ingestion volume. Queue-based scaling for burst webhook delivery. *(Reliability)*
- [ ] **Secret rotation** — Automated rotation for database credentials, API keys, webhook secrets. No secret >90 days. *(Security)*
- [ ] **Cost monitoring** — Per-service cost attribution. Alert on spend anomalies. Know what NLP compute costs per document. *(Economics)*
- [ ] **Container hardening** — Non-root users, read-only filesystems, minimal base images, capability drops, image signing, digest pinning. *(Security)*
- [ ] **Network segmentation** — Docker network isolation: frontend-net, backend-net, data-net, queue-net. *(Security)*

---

## Head of Partnerships / BD

The BD lead cares about how we sell to pharma and what they require.

- [ ] **Pharma RFP response template** — Pre-built responses for standard Tier 1 requirements: HIPAA, SOC 2, 21 CFR Part 11, EHR integration, de-identification, consent management, audit logging. *(Sales enablement)*
- [ ] **EDC/CTMS integration roadmap** — Medidata Rave, Veeva Vault, Oracle. These are pharma RFP Tier 1 requirements. Can't sell without them. *(Integration)*
- [ ] **Published enrollment metrics** — Screen-to-enroll ratio, time-to-FPFV (First Patient First Visit), screen failure rates. Sponsors won't pay without proof. *(Credibility)*
- [ ] **Site network strategy** — Partner with health systems and academic medical centers. The federated data network IS the competitive moat (TriNetX model: 220+ HCOs, 150M EHRs). *(Moat)*
- [ ] **Data licensing program design** — De-identified dataset access for pharma researchers. Subscription model ($200K-$1.5M/yr). Highest margin revenue stream in the industry. *(Revenue)*
- [ ] **Diversity enrollment capabilities** — FDORA DAP compliance tools. Both a regulatory requirement and a sales differentiator. Post-Dec 2025 mandate. *(Compliance + sales)*

---

## Priority Summary

| Priority | Focus | Roles Involved |
|----------|-------|---------------|
| **Week 1-2** | Security fundamentals (credentials, TLS, auth, CORS, network) | CISO, DevOps |
| **Month 1** | Audit logging, RBAC, CI/CD scanning, FHIR validation, data lineage | CISO, VP Eng, Data Eng, FHIR Specialist |
| **Month 2-3** | Clinical validation foundation, explainability, screen failure analytics, consent management | CMO, VP Data Science, VP Product, Compliance |
| **Month 3-6** | Golden datasets, NLP regression, eligibility testing, fairness audits, regulatory determination | QA, NLP Eng, Data Scientist, VP Quality |
| **Month 6-12** | SOC 2, validation studies, data licensing, EDC integration, model governance | CISO, CMO, CSO, VP Product, BD |
| **Month 12-18** | HITRUST, published results, SaMD contingency, federated data network | VP Quality, CSO, CEO, BD |

---

*Generated from research swarm: org-researcher, security-researcher, quality-researcher, product-researcher. February 2026.*
