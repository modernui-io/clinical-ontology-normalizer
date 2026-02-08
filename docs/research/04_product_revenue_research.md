# Product & Revenue Hardening Research: Clinical Trial Patient Recruitment

## Executive Summary

Clinical trial patient recruitment is a $11B+ market growing to $22B+ by 2033, with trial matching software itself at ~$208M growing to ~$681M by 2034. The fundamental value proposition is clear: 80% of trials miss enrollment timelines, delays cost sponsors $500K-$8M per day in lost revenue, and per-patient recruitment costs range from $6,500 to $20,000+. AI-driven matching platforms are compressing enrollment timelines from 6-12 months to 6-8 weeks while reducing recruitment costs by 60-75%. This report analyzes the competitive landscape, pricing models, data science requirements, and partnership dynamics to inform product hardening decisions.

---

## 1. VP Product Perspective: Feature Differentiation & Pricing

### 1.1 Must-Have Features (Table Stakes)

Any platform competing in clinical trial matching must deliver these capabilities:

| Feature | Description | Why Table Stakes |
|---------|-------------|-----------------|
| **Protocol Ingestion & Criteria Normalization** | Parse I/E criteria from protocols into computable rules | Foundation of matching -- without this, no automation possible |
| **EHR Integration (Bi-directional)** | Read from Epic, Cerner, etc.; push alerts back into workflows | 90%+ of matching platforms are cloud-based with EHR integration |
| **NLP over Unstructured Notes** | Extract conditions, labs, meds from free-text clinical notes | Structured data alone misses 40-60% of eligible patients |
| **Real-Time Prescreening** | Continuous scanning of patient records against active trials | Sponsors expect automated flagging, not batch queries |
| **Patient-Facing Screeners** | Landing pages, chat interfaces, self-service eligibility checks | Drives direct-to-patient recruitment channel |
| **Site Referral Orchestration** | Route matched patients to appropriate trial sites | Operationalizes the match into actual enrollment |
| **Funnel Analytics** | Screen-fail reasons, conversion rates, time-to-enroll | Sponsors will not pay without measurable ROI |
| **HIPAA/GDPR Compliance** | De-identification, consent tracking, audit trails | Non-negotiable regulatory requirement |
| **21 CFR Part 11 Auditability** | Electronic signatures, audit logs for regulatory submissions | Required for any data that touches regulatory filings |

### 1.2 Differentiating Features (Competitive Moat)

| Feature | Description | Who Does It Best |
|---------|-------------|-----------------|
| **Genomic/Molecular Matching** | Match on biomarkers, mutations, gene expression | Tempus (multimodal data), Foundation Medicine |
| **Diversity & Equity Analytics** | FDORA DAP compliance, underrepresentation detection | Critical post-Dec 2025 mandate (see Section 4.4) |
| **Just-in-Time Site Activation** | Activate new sites in ~10 business days for identified patients | Tempus TIME platform |
| **Federated Data Queries** | Query across institutions without moving data | TriNetX (hub-and-spoke model) |
| **Protocol Optimization Feedback** | Use matching data to recommend I/E criteria changes | Reduces screen failures (currently $1.2M/study above 40%) |
| **Claims/RWD Integration** | Augment EHR with insurance claims for fuller picture | Komodo Health (330M+ patient map) |
| **Patient Navigation Services** | Concierge services, travel support, call centers | Operational differentiation, high switching costs |
| **Explainable Match Scores** | Show why a patient matched or was excluded, with provenance | FDA guidance increasingly requires this |
| **Multi-Site Network Orchestration** | Manage enrollment across 100+ sites with load balancing | Enterprise CRO/pharma requirement |

### 1.3 Pricing Models

The market uses several pricing approaches, often in combination:

**Model 1: SaaS Subscription (Platform Access)**
- Monthly/annual license for platform access
- Typically per-user or per-study pricing
- Example: Medidata Rave Lite -- scaled pricing based on trial complexity
- Veeva SiteVault CTMS -- free for sites with up to 20 concurrent studies (freemium)
- Range: $50K-$500K/year depending on module count and scale

**Model 2: Pay-for-Performance (Per Enrolled Patient)**
- Payment triggered only when patients actually enroll
- Aligns incentives between vendor and sponsor
- Reported range: $1,500-$15,000 per enrolled patient depending on therapeutic area
- Oncology and rare disease command premium pricing
- Most attractive to sponsors because it eliminates upfront risk

**Model 3: Data Licensing (Real-World Data)**
- De-identified clinical/molecular data sold to pharma for research
- Tempus: $81.3M in Q3 2025 data licensing revenue alone (37.6% YoY growth)
- TriNetX: Subscription fee from pharma/CROs to query federated network
- Komodo Health: Data licensing from 330M+ patient healthcare map
- This is the highest-margin revenue stream

**Model 4: Hybrid (Platform + Performance + Data)**
- Platform subscription for base access
- Per-enrollment fees for trial matching
- Data licensing for research insights
- This is the most common model among market leaders

**Model 5: Revenue Share on Enrollment**
- Percentage of site enrollment fees
- Less common but emerging in partnership models
- Typically 10-20% of the per-patient site fee ($20K-$70K in the US)

### 1.4 Product Maturity Framework

For a platform to be taken seriously by enterprise pharma sponsors:

| Maturity Level | Capabilities | Price Point |
|----------------|-------------|-------------|
| **Level 1: Cohort Discovery** | Basic I/E matching, structured data only | $50-100K/year |
| **Level 2: Smart Matching** | NLP + structured, real-time alerts, basic analytics | $100-250K/year |
| **Level 3: Full Recruitment** | Multi-channel (EHR + DTP + referral), site orchestration | $250K-1M/year |
| **Level 4: Intelligence Platform** | Data licensing, protocol optimization, diversity analytics | $1M+/year + data deals |
| **Level 5: Ecosystem** | Federated network, genomic matching, regulatory submission support | Enterprise custom pricing |

---

## 2. Head of Partnerships/BD Perspective: Selling to Pharma

### 2.1 How Market Leaders Sell

**Tempus AI (Public: TEM)**
- Model: Diagnostics + data licensing + trial matching (TIME platform)
- Sells to pharma through data licensing deals (Insights product)
- Q3 2025: $81.3M data & services revenue, 26.1% YoY growth
- Acquired Deep 6 AI (March 2025) to add 30M+ patients to trial network
- Key differentiator: Multimodal data (genomic + clinical + imaging)
- Go-to-market: Land with diagnostics, expand to data licensing and trial matching

**TriNetX**
- Model: Federated data network with subscription access
- Two-sided marketplace: HCOs contribute data, get analytics; pharma pays subscription to query
- 220+ HCOs across 30+ countries, 150M+ EHRs, 40+ industry sponsors
- HCOs participate for free in exchange for data contribution and analytics access
- Key differentiator: Federated model (data never leaves institutions)
- Go-to-market: Build HCO network first, then sell pharma subscriptions

**Flatiron Health (Roche subsidiary)**
- Model: Oncology EHR (OncoEMR) + real-world evidence curation + trial matching
- Acquired by Roche for $1.9B (2018)
- Clinical research business recently acquired by Paradigm Health
- Key differentiator: Deep oncology-specific data asset
- Go-to-market: EHR adoption at community oncology sites creates data flywheel
- Recently joined Veeva's Product Partner Program for EHR-to-EDC integration

**Medidata (Dassault Systemes, acquired for $5.8B in 2019)**
- Model: Enterprise SaaS for clinical trial management (Rave platform)
- 2,200+ customers, 1M+ registered users
- Rave Lite launched for early-stage trials with scaled pricing
- Key differentiator: End-to-end trial platform (EDC, CTMS, eCOA, safety)
- Go-to-market: Enterprise sales to top 50 pharma, CRO channel partnerships

**Veeva Systems (Public: VEEV)**
- Model: Cloud platform for life sciences (CRM + clinical + regulatory)
- SiteVault CTMS free for sites (market penetration strategy)
- Key differentiator: Ecosystem play -- CRM to clinical to regulatory
- Go-to-market: Land with CRM (Veeva Vault), expand to clinical operations

**Komodo Health (Private, $3.3B valuation)**
- Model: Healthcare data map (330M+ patients) + analytics platform
- Three offerings: data assets, AI analytics tools, targeted solutions
- Key differentiator: Broadest patient data coverage for claims/RWD
- Go-to-market: Data licensing for commercialization, expanding into trial design
- Partnering with Anervea.ai to build AI-native clinical research tools on their platform

**TrialScope (Citeline/Norstella)**
- Model: Clinical trial transparency and disclosure management
- Supports 13 of top 15 clinical trial sponsors
- Registry submission compliance (ClinicalTrials.gov, CTIS, EudraCT)
- Key differentiator: Regulatory compliance automation
- Go-to-market: Regulatory necessity -- sponsors must comply or face penalties

### 2.2 Pharma RFP Requirements for Trial Recruitment Tech

Based on vendor selection literature and industry practices, pharma RFPs typically evaluate:

**Tier 1: Mandatory (Eliminate if Missing)**
- HIPAA/GDPR compliance with documented controls
- 21 CFR Part 11 electronic records/signatures
- SOC 2 Type II certification
- EHR integration capability (Epic, Cerner at minimum)
- CTMS/EDC integration (Medidata, Oracle, Veeva)
- De-identification methodology (HIPAA Safe Harbor or Expert Determination)
- Patient consent management and tracking
- Data provenance and audit logging

**Tier 2: Strongly Preferred (Scored Heavily)**
- Therapeutic area expertise (especially oncology, rare disease, CNS)
- Proven enrollment metrics (screen-to-enroll ratio, time-to-FPFV)
- Site network breadth and activation speed
- Diversity enrollment capabilities (FDORA compliance)
- Real-time dashboards and enrollment forecasting
- Multi-language support for global trials
- Validated algorithms with published performance metrics

**Tier 3: Differentiators (Tiebreakers)**
- Federated data access (avoid data movement)
- Genomic/biomarker matching
- Patient navigation services
- Protocol optimization recommendations
- Decentralized trial support
- AI/ML explainability and bias documentation

### 2.3 SLA and Data Quality Guarantees

Pharma sponsors typically require:

| SLA Dimension | Typical Requirement |
|---------------|-------------------|
| **Uptime** | 99.9% platform availability |
| **Data Freshness** | EHR data updated within 24-48 hours |
| **Match Accuracy** | >85% precision for eligible patient identification |
| **Screen-to-Enroll Ratio** | Improvement over baseline (typically 2x target) |
| **Time to First Match** | <30 days from study activation |
| **Site Activation** | <10-15 business days from patient identification |
| **Response Time** | <4 hour response for critical issues |
| **Data Quality** | ALCOA+ compliance (Attributable, Legible, Contemporaneous, Original, Accurate) |

---

## 3. CFO/Revenue Perspective: Unit Economics & Market Sizing

### 3.1 Total Addressable Market (TAM)

| Market Segment | 2024/2025 Value | 2032/2033 Projection | CAGR |
|---------------|----------------|---------------------|------|
| **Clinical Trial Patient Recruitment Services** | $10.99-11.8B | $22.85B | ~8.5% |
| **Clinical Trials Matching Software** | $207.7M | $501-681M | ~14.1% |
| **AI-Based Clinical Trials** | $9.17B (2025) | $21.79B (2030) | ~18.8% |
| **Overall Clinical Trials Market** | $52.7B+ | Varies by source | ~6-8% |

### 3.2 Per-Patient Economics

**What Pharma Pays (Total Per-Patient Cost)**

| Phase | Avg Total Per-Patient Cost | Recruitment Portion (~20%) |
|-------|--------------------------|--------------------------|
| Phase I | $136,783 | ~$27,000 |
| Phase II | $129,777 | ~$26,000 |
| Phase III | $113,030 | ~$22,600 |

**Site Enrollment Fees (US)**
- Range: $20,000-$70,000 per patient
- Oncology premium: 30-40% above average
- Rare disease premium: Often 2-3x average

**Recruitment-Specific Costs**
- Average cost to recruit one patient: $6,533
- Average cost to replace a dropout: $19,533
- Online recruitment cost per enrollee: $72 (vs $199 offline)
- Average dropout rate: ~30% across all trials

**Screen Failure Cost**
- Average cost per screen failure: ~$1,200
- Cost per study when screen failure rate >40%: ~$1.2M
- AI matching reduces screen failures by estimated 30-50%

### 3.3 Revenue Model Economics for a Trial Matching Platform

**Per-Enrollment Revenue Opportunity**

Assuming a pay-for-performance model:

| Scenario | Per-Patient Fee | Trials/Year | Patients/Trial | Annual Revenue |
|----------|----------------|-------------|----------------|---------------|
| **Early Stage** | $2,000 | 20 | 50 | $2M |
| **Growth** | $3,500 | 100 | 100 | $35M |
| **Scale** | $5,000 | 300 | 150 | $225M |

**Data Licensing Revenue Opportunity**

| Scenario | Pharma Clients | Annual License | Annual Revenue |
|----------|---------------|---------------|---------------|
| **Early** | 5 | $200K | $1M |
| **Growth** | 20 | $500K | $10M |
| **Scale** | 50 | $1.5M | $75M |

**Blended Revenue Model (Realistic Growth Path)**

| Year | Platform SaaS | Per-Enrollment | Data Licensing | Total |
|------|-------------|---------------|---------------|-------|
| Y1 | $500K | $1M | $0 | $1.5M |
| Y2 | $2M | $5M | $500K | $7.5M |
| Y3 | $5M | $15M | $3M | $23M |
| Y4 | $10M | $35M | $10M | $55M |
| Y5 | $15M | $60M | $25M | $100M |

### 3.4 Cost of Delay: The Sponsor's Perspective

This is the core sales narrative:

- **Per-day delay cost (direct)**: ~$40,000
- **Per-day lost revenue (opportunity cost)**: $500,000-$8,000,000
- **Average enrollment delay**: 6+ months for 80% of trials
- **Screen failure waste**: $1.2M per study at >40% failure rate
- **Patient replacement cost**: $19,533 per dropout

A platform that accelerates enrollment by even 30 days saves a sponsor $1.2M-$240M depending on the drug's market potential. This makes even premium pricing ($5,000-$15,000 per enrolled patient) trivially justifiable for pharma sponsors.

### 3.5 Competitive Valuation Benchmarks

| Company | Valuation/Acquisition Price | Revenue Multiple (est.) | Key Asset |
|---------|---------------------------|----------------------|-----------|
| Tempus AI | ~$6B+ (public market cap) | ~10x revenue | Multimodal data + diagnostics |
| Flatiron Health | $1.9B (Roche, 2018) | ~15-20x revenue | Oncology EHR + RWE |
| Medidata | $5.8B (Dassault, 2019) | ~10x revenue | Enterprise trial platform |
| Komodo Health | $3.3B (Series E) | ~20-30x revenue | 330M patient data map |
| Deep 6 AI | ~$55-78M raised (acquired by Tempus) | Early stage | AI matching technology |
| TriNetX | Private (significant scale) | N/A | Federated network model |

---

## 4. Head of Data Science Perspective: AI/ML Hardening

### 4.1 Model Monitoring Requirements

**Matching Algorithm Monitoring**

| Metric | What to Monitor | Alert Threshold |
|--------|----------------|----------------|
| **Precision@K** | Of top-K matched patients, how many are truly eligible | Drop >5% from baseline |
| **Recall** | Of all eligible patients, how many does the system find | Drop >10% from baseline |
| **Screen-to-Enroll Ratio** | Downstream validation of match quality | Ratio degradation >15% |
| **Criteria Coverage** | % of I/E criteria the system can process computably | <80% for any new protocol |
| **NLP Extraction F1** | Entity/relation extraction accuracy on clinical notes | Drop >3% from validation set |
| **Latency** | Time from data update to match refresh | >24 hours |
| **Data Freshness** | Age of most recent EHR data in matching pipeline | >48 hours stale |

**Model Drift Detection**
- Input drift: Changes in patient population demographics, documentation patterns
- Concept drift: New clinical terminology, updated treatment guidelines
- Label drift: Changes in enrollment criteria interpretation across sites
- Recommended: Weekly drift monitoring with monthly revalidation

### 4.2 A/B Testing for Trial Matching Algorithms

**What to A/B Test**
- Matching algorithm variants (rule-based vs. ML ensemble vs. hybrid)
- Ranking/scoring functions for candidate prioritization
- NLP extraction models for unstructured data
- UI presentation of match results to clinicians
- Patient outreach messaging and channel selection

**A/B Testing Constraints in Clinical Context**
- Cannot randomize patient access to trials (ethical constraint)
- Can A/B test: ranking of matched trials, presentation format, outreach timing
- Must maintain audit trail of which algorithm version produced each match
- Need statistical rigor: minimum detectable effect, power analysis
- Recommend: Multi-armed bandit approach for continuous optimization

### 4.3 Fairness & Bias in Patient Selection

**Regulatory Landscape**

The FDA's January 2025 draft guidance on AI in drug development explicitly addresses bias:
- Representative Data requirement: Training data must reflect intended patient population across age, sex, race, ethnicity
- Algorithmic auditing: Sponsors must demonstrate how AI avoids discriminatory impacts
- Corrective training mechanisms: Must show ability to retrain/adjust when bias detected

**FDORA Diversity Action Plan (DAP) Requirements**

Effective December 23, 2025, sponsors of Phase 3 and pivotal studies must submit DAPs that include:
- Enrollment goals disaggregated by race, ethnicity, sex, and age
- Rationale and methodology for goals
- Measures to meet enrollment goals
- Monitoring plans for tracking progress

Note: The guidance was briefly removed from the FDA website in January 2025 following an executive order but was required to be restored by court order on February 11, 2025.

**Bias Mitigation Requirements for a Matching Platform**

| Dimension | Requirement | Implementation |
|-----------|-------------|---------------|
| **Demographic Parity** | Match rates should not vary significantly by race/ethnicity | Regular fairness audits on match output |
| **Equal Opportunity** | True positive rates consistent across subgroups | Subgroup-stratified evaluation metrics |
| **Geographic Equity** | Rural/urban populations have equal access | Site network coverage analysis |
| **Socioeconomic Factors** | Insurance status, income proxies don't bias matching | Feature importance analysis, counterfactual testing |
| **Language Access** | Non-English speakers are not systematically excluded | Multi-language NLP and outreach |
| **Historical Bias** | Past underrepresentation doesn't perpetuate | Calibration against disease prevalence data |

**Technical Implementation**

1. **Pre-processing**: Audit training data for representation gaps, oversample underrepresented groups
2. **In-processing**: Fairness constraints in optimization objective, adversarial debiasing
3. **Post-processing**: Calibrate match scores across demographic groups
4. **Monitoring**: Continuous fairness dashboards with automated alerts
5. **Documentation**: Model cards with fairness metrics for each algorithm version

### 4.4 Explainability Requirements

**Why Explainability Matters**
- FDA guidance requires traceability, provenance, and explainability for AI in drug development
- Clinicians need to understand why a patient was matched (or excluded) to trust the system
- Patients have a right to understand why they were recommended for a trial
- Regulatory submissions may require justification of AI-assisted decisions

**Explainability Framework**

| Stakeholder | What They Need | Technique |
|-------------|---------------|-----------|
| **Clinician** | Which criteria matched/failed, confidence level | Rule-based trace with NLP evidence spans |
| **Sponsor** | Aggregate match quality, criteria sensitivity | SHAP values, criteria contribution analysis |
| **Patient** | Plain-language explanation of eligibility | Template-based natural language generation |
| **Regulator** | Full audit trail, algorithm version, data provenance | Immutable logging, model versioning |
| **Data Scientist** | Feature importance, model behavior analysis | SHAP, LIME, attention visualization |

**Required Capabilities**
- Per-match explanation: For each patient-trial pair, show exactly which criteria matched/failed
- Evidence linking: Connect each criteria evaluation to source data (specific note, lab result, medication)
- Confidence scoring: Indicate certainty level for each criteria assessment
- Counterfactual explanations: "Patient would match if [lab value X] were below [threshold Y]"
- Version tracking: Which model version, feature set, and data snapshot produced each match

### 4.5 Model Governance Framework

| Component | Requirement | Frequency |
|-----------|-------------|-----------|
| **Model Registry** | Version control for all production models | Continuous |
| **Validation Protocol** | Holdout set evaluation before deployment | Every model update |
| **Bias Audit** | Demographic fairness analysis | Quarterly minimum |
| **Performance Review** | Precision/recall/F1 against gold standard | Monthly |
| **Drift Monitoring** | Statistical tests for input/output distribution shifts | Weekly |
| **Incident Response** | Documented process for model failures | As needed, reviewed quarterly |
| **Retraining Schedule** | Planned retraining with new data | Quarterly or triggered by drift |
| **Documentation** | Model cards, data sheets, decision logs | Updated with each release |

---

## 5. Competitive Intelligence: Company Deep Dives

### 5.1 Tempus AI

- **Founded**: 2015 by Eric Lefkofsky
- **Status**: Public (NASDAQ: TEM)
- **Revenue**: ~$700M+ annualized (2025), data licensing ~$81M/quarter
- **Key acquisition**: Deep 6 AI (March 2025) -- added 30M+ patients
- **Competitive moat**: Multimodal data (genomic + clinical + imaging + claims)
- **Revenue model**: Diagnostics (reimbursement) + data licensing (pharma) + trial matching (per-enrollment)
- **Network effect**: More diagnostics -> more data -> better insights -> more pharma licensing -> more diagnostics
- **Trial product**: TIME platform with just-in-time site activation (~10 business days)
- **Threat level**: High -- publicly funded, acquiring aggressively, multimodal data advantage

### 5.2 TriNetX

- **Founded**: 2013
- **Status**: Private (significant venture backing)
- **Network**: 220+ HCOs, 30+ countries, 150M+ EHRs, 40+ pharma sponsors
- **Revenue model**: Pharma subscription for network access; HCOs participate free for analytics
- **Competitive moat**: Federated architecture (data stays at institutions) + global scale
- **Key capability**: Real-time feasibility queries across the entire network
- **Threat level**: High for feasibility/protocol design; moderate for active recruitment

### 5.3 Komodo Health

- **Founded**: 2014
- **Status**: Private ($3.3B valuation at Series E)
- **Data asset**: 330M+ patient healthcare map (broadest claims/RWD coverage)
- **Revenue model**: Data licensing + analytics platform (MapLab)
- **Competitive moat**: Broadest patient data coverage in the US
- **Clinical trials play**: Partnering with Anervea.ai for AI-native clinical research tools
- **Threat level**: Moderate -- strong data asset but clinical trial matching is newer focus

### 5.4 Flatiron Health

- **Founded**: 2012
- **Status**: Roche subsidiary (acquired for $1.9B in 2018)
- **Revenue model**: Oncology EHR (OncoEMR) + real-world evidence curation
- **Recent change**: Clinical research business sold to Paradigm Health
- **Competitive moat**: Deep oncology data from community practice EHR network
- **Threat level**: Moderate -- oncology focus limits breadth; Paradigm acquisition creates uncertainty

### 5.5 Medidata (Dassault Systemes)

- **Founded**: 1999
- **Status**: Dassault subsidiary (acquired for $5.8B in 2019)
- **Revenue model**: Enterprise SaaS platform for trial management
- **Customers**: 2,200+ organizations, 1M+ users
- **Competitive moat**: Installed base in enterprise pharma; end-to-end platform
- **Key product**: Rave EDC/CTMS + Rave Lite for early-stage
- **Threat level**: High for platform/CTMS; lower for AI matching specifically

### 5.6 Veeva Systems

- **Founded**: 2007
- **Status**: Public (NYSE: VEEV, ~$35B market cap)
- **Revenue model**: Cloud SaaS subscription (CRM + Clinical + Regulatory + Quality)
- **Competitive moat**: Dominant life sciences CRM -> expanding into clinical
- **Key play**: SiteVault CTMS free for sites (land-and-expand into sponsor tools)
- **Threat level**: High long-term -- massive platform with resources to build/acquire matching

---

## 6. Product Hardening Recommendations

### 6.1 Immediate Priorities (0-6 Months)

1. **Matching Accuracy Benchmarking**: Establish gold-standard evaluation set and publish precision/recall metrics. Without published benchmarks, no pharma RFP can be won.

2. **Explainability Engine**: Build per-match explanations showing exactly which criteria matched/failed with source evidence. This is both a regulatory requirement and a sales enabler.

3. **Fairness Audit Framework**: Implement demographic parity monitoring and document bias mitigation. FDORA DAP requirements create both a regulatory obligation and a sales opportunity.

4. **Screen Failure Analytics**: Track and report screen-to-enroll ratios. This is the single most important ROI metric for sponsors.

5. **HIPAA/SOC 2 Compliance Documentation**: Without this, enterprise pharma will not engage.

### 6.2 Medium-Term (6-18 Months)

1. **Data Licensing Infrastructure**: Build de-identification pipeline and data access layer for pharma researchers. This is the highest-margin revenue stream.

2. **Site Network Development**: Partner with health systems and academic medical centers. The federated data network is the competitive moat (see TriNetX model).

3. **Multi-Therapeutic Expansion**: Move beyond initial therapeutic focus to demonstrate breadth.

4. **EDC/CTMS Integration**: Connect with Medidata, Veeva, Oracle for sponsor workflow integration.

5. **Diversity Enrollment Tools**: Build FDORA-compliant diversity tracking and reporting.

### 6.3 Long-Term (18+ Months)

1. **Federated Query Network**: Enable cross-institutional queries without data movement.

2. **Protocol Optimization Service**: Use matching data to recommend I/E criteria modifications.

3. **Genomic/Biomarker Matching**: Integrate molecular data for precision trial matching.

4. **International Expansion**: Multi-language, multi-regulatory support for global trials.

5. **Patient Navigation Platform**: Full-service recruitment including call center, travel support.

### 6.4 Pricing Strategy Recommendation

**Phase 1 (Market Entry)**: Platform SaaS + per-enrollment fees
- Low base subscription ($50-100K/year) to reduce adoption friction
- Per-enrolled-patient fees ($2,000-$5,000) aligned to value delivered
- Target: 10-20 trials, prove ROI

**Phase 2 (Scale)**: Add data licensing
- Once sufficient data is accumulated, begin pharma data licensing
- Annual subscriptions ($200K-$1M) for research data access
- Target: 5-10 pharma data licensing clients

**Phase 3 (Platform)**: Full ecosystem pricing
- Tiered platform subscriptions based on scale
- Performance-based enrollment fees
- Data licensing with premium analytics
- Protocol optimization consulting
- Target: $50M+ ARR

---

## 7. Key Metrics Dashboard for Leadership

### Revenue Metrics
- Monthly Recurring Revenue (MRR) / Annual Recurring Revenue (ARR)
- Revenue per enrolled patient
- Data licensing revenue as % of total
- Net revenue retention rate
- Customer acquisition cost (CAC) by segment

### Operational Metrics
- Patients matched per month
- Screen-to-enroll conversion rate
- Time from match to enrollment (days)
- Active trials on platform
- Site network size (institutions)
- EHR integrations active

### Quality Metrics
- Match precision@K
- NLP extraction F1 score
- Criteria coverage rate (% of I/E criteria computable)
- Fairness metrics by demographic group
- Model drift indicators

### Compliance Metrics
- HIPAA audit findings (target: zero)
- Consent tracking completeness
- Audit trail coverage
- Diversity enrollment goal achievement (FDORA)

---

## 8. Risk Factors

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **EHR vendor lock-in** | High | High | Support multiple EHR integrations (Epic, Cerner, Allscripts) |
| **Data privacy breach** | Medium | Critical | SOC 2, HIPAA, encryption, de-identification |
| **FDA regulatory changes** | Medium | High | Active regulatory monitoring, flexible architecture |
| **Big tech entry** | Medium | High | Build proprietary data network moat |
| **FDORA DAP enforcement changes** | Medium | Medium | Build diversity tools regardless of regulatory status |
| **Model bias litigation** | Low | Critical | Comprehensive fairness auditing, documentation |
| **Customer concentration** | High (early) | High | Diversify across pharma/biotech/CRO segments |
| **Reimbursement pressure** | Medium | Medium | Revenue diversification beyond per-enrollment |

---

## Sources

Market sizing and financial data drawn from Research and Markets, Grand View Research, Mordor Intelligence, Straits Research, SNS Insider, and Globe Newswire market reports (2024-2026). Company-specific data from Tempus AI SEC filings, PitchBook, CB Insights, Crunchbase, and company press releases. Regulatory guidance from FDA.gov, Federal Register, and legal analysis from Morgan Lewis, King & Spalding, Hogan Lovells, Foley & Lardner, and Ropes & Gray. Clinical trial cost data from ASPE/HHS, PMC/NIH publications, and Abacum. Vendor selection criteria from Applied Clinical Trials, Clinical Leader, and PPD. AI/ML governance from FDA draft guidance on AI for drug development (January 2025) and FDLI regulatory analysis.
