# Deep Implementation Plan: VP Product, CDO, VP Data Science, Head of Partnerships

> Detailed implementation specs for every item in the HARDENING_PLAN.md sections for VP Product, CDO (Chief Data Officer), VP Data Science, and Head of Partnerships / BD.
> Each item includes: files to modify/create, implementation steps, acceptance criteria, effort estimate, and dependencies.

---

## Table of Contents

1. [VP Product](#1-vp-product)
2. [CDO / Chief Data Officer](#2-cdo--chief-data-officer)
3. [VP Data Science](#3-vp-data-science)
4. [Head of Partnerships / BD](#4-head-of-partnerships--bd)

---

## 1. VP Product

### 1.1 Clinical Coordinator UX Audit

**Goal**: Primary users are research nurses and clinical coordinators. One-click screening, clear eligibility explanations, override capabilities.

**Files to modify**:
- `frontend/src/app/trials/[id]/page.tsx` — trial detail page with screening UI
- `frontend/src/app/trials/page.tsx` — trials list page
- `frontend/src/components/ui/` — shared UI components (dialog, form, tooltip)
- `frontend/src/hooks/api/useTrials.ts` — trial API hooks
- `frontend/src/lib/api.ts` — API client (trial functions at lines ~3353-3402)

**Files to create**:
- `frontend/src/app/trials/[id]/screen/page.tsx` — dedicated screening workflow page
- `frontend/src/components/trials/ScreeningWizard.tsx` — step-by-step screening wizard
- `frontend/src/components/trials/PatientEligibilityCard.tsx` — per-patient eligibility card with override
- `frontend/src/components/trials/CriterionOverride.tsx` — override form for individual criteria
- `frontend/src/components/trials/QuickActions.tsx` — one-click action buttons (screen, enroll, exclude)
- `backend/app/schemas/trial.py` — add `CriterionOverride` schema (extend existing file)
- `backend/app/api/trials.py` — add override endpoint (extend existing file)

**Implementation steps**:
1. Audit the current trial detail page (`frontend/src/app/trials/[id]/page.tsx`, 703 lines). The Candidates tab currently shows a flat table of screening results with match scores. It lacks: one-click enrollment, override capability, inline explanations, and clinical coordinator-specific terminology.
2. Create `ScreeningWizard.tsx` component that guides coordinators through: (a) select patients or scan all, (b) review results grouped by eligibility tier (eligible / borderline / ineligible), (c) drill into per-criteria evidence, (d) apply overrides with mandatory reason text, (e) confirm enrollment actions.
3. Create `PatientEligibilityCard.tsx` that displays each patient with: match score bar, criteria-level pass/fail badges, evidence links (source document, fact IDs from `CriterionResult.evidence_fact_ids`), and action buttons (Enroll, Override, Exclude).
4. Add `CriterionOverride` to `backend/app/schemas/trial.py`:
   ```python
   class CriterionOverride(BaseModel):
       criterion_name: str
       override_status: str  # "PASS_OVERRIDE" | "FAIL_OVERRIDE"
       reason: str = Field(..., min_length=10)
       overridden_by: str
   ```
5. Add `POST /trials/{trial_id}/enrollments/{enrollment_id}/override` endpoint to `backend/app/api/trials.py` that: validates the override, updates `TrialEnrollment.criteria_met/criteria_failed`, logs an audit entry via `audit_service.log_access()`, and returns the updated enrollment.
6. Update `frontend/src/hooks/api/useTrials.ts` with `useOverrideEnrollment` mutation hook.
7. Replace the raw `<select>` status filter in `frontend/src/app/trials/page.tsx` (line 158-172) with a shadcn/ui `Select` component for visual consistency.

**Acceptance criteria**:
- Clinical coordinator can screen patients in 3 clicks or fewer from trials list
- Override modal requires minimum 10-character reason text
- All overrides are logged in audit trail (`audit_logs` table) with `phi_accessed=true`
- Borderline patients (match_score 0.5-0.8) are visually grouped separately from eligible (>0.8) and ineligible (<0.5)
- Mobile-responsive layout works on tablet devices (coordinators often use iPads)

**Effort estimate**: 5-7 days

**Dependencies**: None (builds on existing trial screening infrastructure)

---

### 1.2 Per-Match Explainability Engine

**Goal**: For each patient-trial pair, show which criteria matched/failed with links to source evidence. Pharma RFP Tier 2 requirement.

**Files to modify**:
- `backend/app/services/trial_eligibility_service.py` — `TrialEligibilityService._evaluate_criteria()` method (around line 300+) to enrich `CriterionResult` with evidence
- `backend/app/schemas/trial.py` — `CriterionResult` already has `evidence_fact_ids`, `confidence`, `details`, `weight` fields (lines 150-164)
- `frontend/src/app/trials/[id]/page.tsx` — Candidates tab to display per-criterion drill-down
- `frontend/src/components/provenance/` — existing provenance components (`CitationCard.tsx`, `ConfidenceBadge.tsx`, `ReasoningChain.tsx`)

**Files to create**:
- `frontend/src/components/trials/MatchExplanation.tsx` — per-match explanation panel
- `frontend/src/components/trials/CriterionEvidence.tsx` — single criterion with evidence links
- `frontend/src/components/trials/EvidenceModal.tsx` — modal showing source document text with highlighted spans
- `backend/app/services/match_explanation_service.py` — dedicated service for generating explanations
- `backend/app/api/trials.py` — add `GET /trials/{trial_id}/matches/{patient_id}/explanation` endpoint

**Implementation steps**:
1. Create `MatchExplanationService` in `backend/app/services/match_explanation_service.py` that:
   - Takes a `PatientEligibility` result and enriches each `CriterionResult` with:
     - Source document references (query `ClinicalFact` → `FactEvidence` → `Document` chain)
     - Text spans from the original clinical note (using `Mention.char_offset_begin/end` from `backend/app/models/mention.py`)
     - Confidence calibration using `ConfidenceLevel` from `backend/app/services/provenance_service.py` (lines 45-52)
   - Generates a plain-language summary for each criterion (e.g., "Patient has Atopic Dermatitis (ICD-10 L20.9) documented in progress note from 2024-12-15, confidence: HIGH")
   - Returns counterfactual hints: "Patient would match if [criterion X] were met"
2. Add `GET /trials/{trial_id}/matches/{patient_id}/explanation` endpoint to `backend/app/api/trials.py`.
3. Build `MatchExplanation.tsx` component that:
   - Renders inclusion criteria as green checkmarks / red X marks
   - Each criterion is expandable to show evidence documents
   - Links to source document viewer at `/documents/{documentId}`
   - Uses existing `ConfidenceBadge.tsx` component from `frontend/src/components/provenance/`
   - Uses existing `CitationCard.tsx` for source references
4. Build `EvidenceModal.tsx` that fetches document text and highlights the relevant span.
5. Wire the explanation panel into the Candidates tab of `frontend/src/app/trials/[id]/page.tsx`.

**Acceptance criteria**:
- Every patient-trial pair shows a breakdown of each criterion with pass/fail status
- Each criterion links to at least one source evidence document
- Evidence spans are highlighted in the source document viewer
- Plain-language summary is generated for clinician consumption
- Counterfactual hints appear for "borderline" patients (0.5 < match_score < 0.8)
- API response includes full audit trail data (fact IDs, document IDs, extraction method)

**Effort estimate**: 6-8 days

**Dependencies**: Data lineage tracking (CDO 2.1) should be in progress for full evidence chain

---

### 1.3 Screen Failure Analytics

**Goal**: Track screen-to-enroll ratios. The #1 ROI metric for pharma sponsors.

**Files to modify**:
- `backend/app/services/trial_eligibility_service.py` — add analytics methods to `TrialEligibilityService`
- `backend/app/schemas/trial.py` — add `ScreenFailureAnalytics` schema
- `backend/app/api/trials.py` — add analytics endpoint
- `frontend/src/app/trials/[id]/page.tsx` — add analytics tab

**Files to create**:
- `frontend/src/app/trials/[id]/analytics/page.tsx` — dedicated trial analytics page
- `frontend/src/components/trials/ScreenFailureChart.tsx` — screen failure breakdown visualization
- `frontend/src/components/trials/FunnelChart.tsx` — enrollment funnel visualization
- `frontend/src/components/trials/ConversionMetrics.tsx` — key conversion metrics cards
- `backend/app/schemas/trial.py` — extend with analytics schemas (same file)

**Implementation steps**:
1. Add `ScreenFailureAnalytics` schema to `backend/app/schemas/trial.py`:
   ```python
   class ScreenFailureAnalytics(BaseModel):
       trial_id: UUID
       total_screened: int
       total_eligible: int
       total_enrolled: int
       total_screen_failed: int
       screen_to_enroll_ratio: float  # enrolled / screened
       screen_failure_rate: float  # screen_failed / screened
       failure_reasons: dict[str, int]  # criterion_name -> count
       failure_by_criterion_type: dict[str, int]  # demographic, condition, measurement -> count
       time_to_enroll_days: float | None  # avg days from screening to enrollment
       cost_estimate: float | None  # estimated cost at $1,200/screen failure
       trend_data: list[dict]  # weekly/monthly conversion trends
   ```
2. Add `get_screen_failure_analytics(trial_id)` method to `TrialEligibilityService` that:
   - Aggregates enrollment records by status from `_EnrollmentRecord` / `TrialEnrollment` model
   - Counts failure reasons from `criteria_failed` JSON field
   - Calculates screen-to-enroll ratio and failure rate
   - Estimates cost impact using industry benchmark ($1,200/screen failure)
   - Computes time-to-enroll using `screening_date` and `enrollment_date` from `TrialEnrollment` model (lines 209-214)
3. Add `GET /trials/{trial_id}/analytics/screen-failures` endpoint.
4. Build `ScreenFailureChart.tsx` using a horizontal bar chart showing failure reasons ranked by frequency.
5. Build `FunnelChart.tsx` showing: Candidates -> Screened -> Eligible -> Enrolled -> Active -> Completed.
   - The `TrialDashboard` schema (lines 221-238 of `backend/app/schemas/trial.py`) already has all the funnel counts needed.
6. Build `ConversionMetrics.tsx` with key cards: screen-to-enroll ratio, avg time-to-enroll, estimated cost savings, comparison to industry benchmarks.
7. Add an "Analytics" tab to `frontend/src/app/trials/[id]/page.tsx` TabsList (currently has Overview, Eligibility Criteria, Candidates, Enrollment tabs at lines 208-226).

**Acceptance criteria**:
- Screen-to-enroll ratio displayed prominently on trial detail page
- Failure reasons ranked by frequency with counts
- Funnel visualization shows conversion at each stage
- Cost impact estimated using $1,200/screen failure benchmark
- Trend data available for weekly/monthly view
- Analytics exportable as CSV for sponsor reports

**Effort estimate**: 4-5 days

**Dependencies**: Enrollment data must exist (trial screening must have been run)

---

### 1.4 Knowledge Graph Visualization

**Goal**: Clinicians need intuitive patient timeline views, not raw graph data.

**Files to modify**:
- `frontend/src/components/KnowledgeGraph/` — existing graph components: `GraphCanvas.tsx`, `GraphNode.tsx`, `GraphEdge.tsx`, `index.tsx`, `types.ts`, `useGraphState.ts`
- `frontend/src/components/graph/` — existing canvas renderer: `CanvasRenderer.tsx`, `TemporalSlider.tsx`
- `frontend/src/app/patients/[patientId]/` — patient detail page
- `backend/app/services/patient_timeline.py` — `PatientTimelineService` (line 296)

**Files to create**:
- `frontend/src/components/trials/PatientTimeline.tsx` — chronological timeline view
- `frontend/src/components/trials/TimelineEvent.tsx` — individual event card
- `frontend/src/components/trials/TimelineFilter.tsx` — filter by domain (conditions, medications, labs, procedures)
- `frontend/src/app/trials/[id]/patient/[patientId]/page.tsx` — patient-in-trial context view
- `backend/app/api/patients.py` — extend with timeline endpoint (if not already present)

**Implementation steps**:
1. Review existing `PatientTimelineService` in `backend/app/services/patient_timeline.py` to understand the data structures returned.
2. Create `PatientTimeline.tsx` as a vertical chronological timeline that:
   - Displays clinical events ordered by date along a vertical axis
   - Color-codes by domain: conditions (orange), medications (blue), labs (green), procedures (purple), visits (gray)
   - Each event shows: date, event type, description, source document link, OMOP concept code
   - Uses the existing `TemporalSlider.tsx` from `frontend/src/components/graph/` for date range filtering
3. Create `TimelineFilter.tsx` with checkboxes for domain filtering (leverages `Domain` enum from `backend/app/schemas/base.py`).
4. Create patient-in-trial context page at `frontend/src/app/trials/[id]/patient/[patientId]/page.tsx` that:
   - Shows the patient timeline
   - Overlays trial eligibility criteria checkpoints on the timeline
   - Highlights which clinical events satisfy which criteria
5. Ensure the existing KG visualization (`frontend/src/components/KnowledgeGraph/`) can be toggled between graph view and timeline view.
6. Add a "View Timeline" link for each patient in the Candidates tab of the trial detail page.

**Acceptance criteria**:
- Patient timeline renders all clinical events chronologically
- Events are filterable by domain (condition, medication, lab, procedure)
- Trial eligibility criteria overlay shows pass/fail per event
- Timeline loads in <2 seconds for patients with up to 500 clinical facts
- Works alongside existing graph visualization (toggle between views)

**Effort estimate**: 6-8 days

**Dependencies**: Patient data must be loaded via FHIR import pipeline (`backend/app/services/fhir_import.py`)

---

### 1.5 Patient-Facing Screener

**Goal**: Landing pages, chat interfaces, self-service eligibility checks. Drives direct-to-patient recruitment channel.

**Files to modify**:
- `frontend/src/app/page.tsx` — landing page (or link from it)
- `backend/app/api/trials.py` — add public screening endpoint

**Files to create**:
- `frontend/src/app/screener/page.tsx` — public screener landing page
- `frontend/src/app/screener/[trialId]/page.tsx` — trial-specific screener
- `frontend/src/components/screener/ScreenerForm.tsx` — self-service eligibility form
- `frontend/src/components/screener/ScreenerResult.tsx` — eligibility result display
- `frontend/src/components/screener/ScreenerChat.tsx` — conversational eligibility check
- `backend/app/api/public_screening.py` — public API router (no auth required)
- `backend/app/schemas/trial.py` — add `PublicScreeningRequest` / `PublicScreeningResponse`
- `backend/app/services/public_screening_service.py` — simplified patient-facing screening logic

**Implementation steps**:
1. Create `PublicScreeningService` that:
   - Takes self-reported patient data (age, gender, conditions, medications) without requiring PHI
   - Evaluates against trial criteria using a simplified version of `TrialEligibilityService._evaluate_criteria()`
   - Returns plain-language eligibility result without exposing internal system details
   - Tracks conversion metrics (screener visits, completions, eligible results)
2. Create `public_screening.py` API router with:
   - `GET /public/trials` — list recruiting trials (public info only: name, description, criteria summary)
   - `POST /public/trials/{trial_id}/screen` — submit self-screening data
   - No authentication required, but rate-limited
3. Build `ScreenerForm.tsx` with:
   - Step-by-step form (age, gender, condition history, medications, lab values)
   - Each step corresponds to a criterion type from the trial's `inclusion_criteria`
   - Progress indicator
   - Plain-language questions (not clinical jargon)
4. Build `ScreenerResult.tsx` showing:
   - Eligible/Not eligible/More info needed
   - Plain-language explanation of each criterion
   - "Next Steps" section with site contact info
   - Disclaimer: "This is not a medical diagnosis. Please consult your healthcare provider."
5. Build `ScreenerChat.tsx` as an optional conversational interface using the existing `AssistantWidget.tsx` pattern from `frontend/src/components/AssistantWidget.tsx`.
6. Add `/screener` to `frontend/src/components/Sidebar.tsx` under Clinical Trials section (line 83-87).

**Acceptance criteria**:
- Patient can complete screening in under 5 minutes
- No PHI is collected (only self-reported, de-identified data)
- Plain-language results with no clinical jargon
- Disclaimer prominently displayed
- Rate limiting prevents abuse (100 requests/IP/hour)
- Conversion tracking: visits -> form starts -> completions -> eligible results

**Effort estimate**: 7-10 days

**Dependencies**: Trial data must exist with structured inclusion/exclusion criteria

---

### 1.6 Site Referral Orchestration

**Goal**: Route matched patients to appropriate trial sites.

**Files to modify**:
- `backend/app/models/trial.py` — add `TrialSite` model
- `backend/app/schemas/trial.py` — add site-related schemas
- `backend/app/services/trial_eligibility_service.py` — add site assignment logic
- `backend/app/api/trials.py` — add site management endpoints
- `frontend/src/app/trials/[id]/page.tsx` — add sites tab

**Files to create**:
- `frontend/src/components/trials/SiteManagement.tsx` — site list and management
- `frontend/src/components/trials/SiteAssignment.tsx` — patient-to-site assignment UI
- `frontend/src/components/trials/SiteMap.tsx` — geographic site distribution (optional)
- `backend/app/services/site_referral_service.py` — site matching and referral logic

**Implementation steps**:
1. Add `TrialSite` model to `backend/app/models/trial.py`:
   ```python
   class TrialSite(Base):
       __tablename__ = "trial_sites"
       trial_id: Mapped[str]  # FK to trials
       site_name: Mapped[str]
       site_code: Mapped[str]
       address: Mapped[str | None]
       city: Mapped[str | None]
       state: Mapped[str | None]
       zip_code: Mapped[str | None]
       principal_investigator: Mapped[str | None]
       contact_email: Mapped[str | None]
       contact_phone: Mapped[str | None]
       capacity: Mapped[int]  # max enrollment at this site
       current_enrollment: Mapped[int]
       status: Mapped[str]  # active, paused, closed
   ```
2. Create `SiteReferralService` that:
   - Matches patients to sites based on: geographic proximity (zip code), site capacity, site specialization
   - Generates referral records with patient ID, site ID, referral reason
   - Tracks referral status: pending, accepted, declined, enrolled
3. Add CRUD endpoints for sites under `POST/GET/PUT /trials/{trial_id}/sites`.
4. Add `POST /trials/{trial_id}/enrollments/{enrollment_id}/refer` endpoint.
5. Build `SiteManagement.tsx` showing site list with capacity bars, enrollment counts, and status.
6. Build `SiteAssignment.tsx` as a modal for assigning an eligible patient to a specific site.
7. Add "Sites" tab to the trial detail page.

**Acceptance criteria**:
- Sites can be added, edited, and deactivated per trial
- Patient referrals track from assignment through enrollment
- Capacity limits are enforced (cannot refer beyond site capacity)
- Referral notifications include patient eligibility summary

**Effort estimate**: 5-7 days

**Dependencies**: Trial enrollment infrastructure (existing)

---

### 1.7 Funnel Analytics Dashboard

**Goal**: Screen-fail reasons, conversion rates, time-to-enroll by trial, by site, by therapeutic area.

**Files to modify**:
- `frontend/src/app/dashboard/page.tsx` — currently uses mock data (line 30-58, 113-114). Replace with real API data
- `frontend/src/hooks/api/useAnalytics.ts` — add funnel analytics hooks
- `frontend/src/lib/api.ts` — add funnel analytics API functions
- `backend/app/api/trials.py` — add cross-trial analytics endpoints

**Files to create**:
- `frontend/src/app/trials/analytics/page.tsx` — cross-trial funnel analytics page
- `frontend/src/components/trials/FunnelDashboard.tsx` — main funnel dashboard component
- `frontend/src/components/trials/ConversionChart.tsx` — conversion rate charts
- `frontend/src/components/trials/TimeToEnrollChart.tsx` — time-to-enroll distribution
- `frontend/src/components/trials/TherapeuticAreaBreakdown.tsx` — analytics by therapeutic area
- `backend/app/services/trial_analytics_service.py` — cross-trial analytics service
- `backend/app/schemas/trial.py` — extend with `FunnelAnalytics` schema

**Implementation steps**:
1. Create `TrialAnalyticsService` in `backend/app/services/trial_analytics_service.py` that:
   - Aggregates enrollment data across all trials
   - Computes per-trial, per-site, per-therapeutic-area conversion rates
   - Calculates time-to-enroll distributions
   - Identifies top screen failure reasons across the platform
   - Generates weekly/monthly trend data
2. Add `FunnelAnalytics` schema to `backend/app/schemas/trial.py`:
   ```python
   class FunnelAnalytics(BaseModel):
       total_trials: int
       total_screened: int
       total_eligible: int
       total_enrolled: int
       overall_conversion_rate: float
       avg_time_to_enroll_days: float
       by_trial: list[TrialConversion]
       by_therapeutic_area: dict[str, TrialConversion]
       by_site: list[SiteConversion]
       top_failure_reasons: list[FailureReason]
       trend_data: list[TrendPoint]
   ```
3. Add `GET /trials/analytics/funnel` endpoint.
4. Build `FunnelDashboard.tsx` with:
   - Top-level KPI cards (total screened, enrolled, conversion rate, avg time-to-enroll)
   - Funnel visualization (candidates -> screened -> eligible -> enrolled)
   - Filter by trial, therapeutic area, date range
5. Build `ConversionChart.tsx` showing per-trial conversion rates as a bar chart.
6. Build `TimeToEnrollChart.tsx` showing distribution of days from screening to enrollment.
7. Add navigation link in `frontend/src/components/Sidebar.tsx` under "Clinical Trials" section (line 82-87): `{ title: "Trial Analytics", href: "/trials/analytics", icon: BarChart3 }`.
8. Replace mock data in `frontend/src/app/dashboard/page.tsx` with real data from `useDashboardStats()` hook (which already exists in `frontend/src/hooks/api/useAnalytics.ts` line 107-117 but isn't used on the dashboard page).

**Acceptance criteria**:
- Cross-trial funnel analytics page shows real data
- Conversion rates computed correctly (enrolled / screened)
- Data filterable by trial, therapeutic area, site, date range
- Dashboard page uses real API data instead of mock data
- Analytics exportable as CSV/PDF for sponsor reports

**Effort estimate**: 5-7 days

**Dependencies**: Screen failure analytics (1.3), site referral orchestration (1.6) for per-site data

---

### 1.8 FDORA Diversity Enrollment Tools

**Goal**: Tracking, reporting, and active enrollment goal monitoring for DAP compliance. Effective Dec 2025.

**Files to modify**:
- `backend/app/models/trial.py` — add diversity fields to `Trial` and `TrialEnrollment`
- `backend/app/schemas/trial.py` — add diversity schemas
- `backend/app/services/trial_eligibility_service.py` — add demographic analysis to screening
- `frontend/src/app/trials/[id]/page.tsx` — add diversity tab

**Files to create**:
- `frontend/src/components/trials/DiversityDashboard.tsx` — diversity monitoring dashboard
- `frontend/src/components/trials/DAPGoalTracker.tsx` — DAP enrollment goal progress
- `frontend/src/components/trials/DemographicBreakdown.tsx` — demographic distribution charts
- `backend/app/services/diversity_analytics_service.py` — diversity analytics and DAP compliance
- `backend/app/schemas/diversity.py` — diversity-specific schemas

**Implementation steps**:
1. Add to `Trial` model in `backend/app/models/trial.py`:
   ```python
   diversity_goals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
   # JSON structure: {"race": {"Black": 15, "Hispanic": 20, ...}, "sex": {"Female": 50}, "age": {"65+": 10}}
   ```
2. Add demographic fields to `TrialEnrollment` model:
   ```python
   patient_race: Mapped[str | None]
   patient_ethnicity: Mapped[str | None]
   patient_sex: Mapped[str | None]
   patient_age_at_enrollment: Mapped[int | None]
   patient_geography: Mapped[str | None]  # state/region
   ```
3. Create `DiversityAnalyticsService` that:
   - Computes enrollment demographics vs. DAP goals
   - Identifies underrepresented populations in real-time
   - Flags trials at risk of missing diversity goals
   - Generates DAP compliance reports in FDA-required format
   - Compares enrollment demographics against disease prevalence data
4. Build `DiversityDashboard.tsx` with:
   - Side-by-side comparison: DAP goals vs. actual enrollment
   - Progress bars for each demographic category
   - Alert badges for categories below target
   - Recommendation engine: "Consider increasing outreach to [demographic] in [region]"
5. Build `DAPGoalTracker.tsx` as a compact widget showing overall DAP compliance score.
6. Add "Diversity" tab to trial detail page.

**Acceptance criteria**:
- DAP goals can be set per trial (race, ethnicity, sex, age)
- Real-time tracking of enrollment demographics vs. goals
- Visual alerts when enrollment falls below target for any demographic
- DAP compliance report exportable in FDA-friendly format
- Demographic data sourced from FHIR Patient resource (already imported via `fhir_import.py`)

**Effort estimate**: 6-8 days

**Dependencies**: Patient demographic data from FHIR import pipeline

---

### 1.9 Protocol Optimization Feedback

**Goal**: Use matching data to recommend I/E criteria changes that reduce screen failures.

**Files to create**:
- `backend/app/services/protocol_optimization_service.py` — criteria optimization recommendations
- `backend/app/schemas/trial.py` — add `ProtocolOptimization` schema
- `frontend/src/components/trials/ProtocolOptimization.tsx` — optimization recommendations UI
- `frontend/src/app/trials/[id]/optimize/page.tsx` — optimization recommendations page

**Implementation steps**:
1. Create `ProtocolOptimizationService` that:
   - Analyzes screen failure data across all screening runs for a trial
   - Identifies the "most exclusionary" criteria (criteria that fail the most patients)
   - Computes sensitivity analysis: "If criterion X were relaxed from [value] to [value], N additional patients would be eligible"
   - Generates recommendations ranked by impact (number of additional patients unlocked)
   - Compares against industry benchmarks (screen failure rate > 40% = $1.2M wasted per study)
2. Add `GET /trials/{trial_id}/optimize` endpoint.
3. Build `ProtocolOptimization.tsx` showing:
   - Top criteria causing screen failures (bar chart)
   - "What-if" simulator: adjust criteria thresholds and see impact
   - Estimated cost savings from criteria relaxation
   - Disclaimer: "Protocol changes require sponsor and IRB approval"

**Acceptance criteria**:
- Top 5 most exclusionary criteria identified per trial
- Impact analysis shows number of additional patients per criteria change
- Cost savings estimated using $1,200/screen failure benchmark
- Recommendations are advisory only (cannot modify protocol automatically)

**Effort estimate**: 4-5 days

**Dependencies**: Screen failure analytics (1.3) must be implemented first

---

## 2. CDO / Chief Data Officer

### 2.1 Data Lineage Tracking

**Goal**: Every clinical fact must trace back to: source FHIR resource -> extraction method -> mention with offsets -> mapping confidence -> selected OMOP concept.

**Files to modify**:
- `backend/app/services/provenance_service.py` — existing provenance service (has `ExtractionMethod`, `ConfidenceLevel`, `SourceDocument` at lines 31-60). Extend with full lineage chain.
- `backend/app/services/provenance_db_service.py` — database-backed provenance
- `backend/app/models/provenance.py` — provenance ORM model
- `backend/app/models/clinical_fact.py` — ensure `ClinicalFact` and `FactEvidence` link to provenance
- `backend/app/services/fhir_import.py` — enrich imports with provenance records

**Files to create**:
- `backend/app/services/lineage_service.py` — end-to-end lineage chain builder
- `backend/app/schemas/lineage.py` — lineage chain schemas
- `backend/app/api/lineage.py` — lineage API endpoints
- `frontend/src/app/data-quality/lineage/page.tsx` — lineage explorer page
- `frontend/src/components/lineage/LineageChain.tsx` — visual lineage chain component
- `frontend/src/components/lineage/LineageGraph.tsx` — DAG visualization of data lineage

**Implementation steps**:
1. Create `LineageService` that:
   - For any `ClinicalFact`, constructs the full chain:
     - Source: FHIR Resource (type, ID, element path) or Document (text, char offsets)
     - Extraction: Method (rule-based, ML, LLM, FHIR import), model version, timestamp
     - Mention: Text span, assertion status, temporality, experiencer (from `Mention` model)
     - Mapping: Candidate OMOP concepts, confidence scores, selected concept (from `MentionConceptCandidate` model)
     - Fact: Final `ClinicalFact` with domain, OMOP concept, value
   - Stores lineage records in the `provenance` table
   - Links via `FactEvidence` model (from `backend/app/models/clinical_fact.py`)
2. Add lineage recording to the FHIR import pipeline:
   - In `FHIRImportService.import_patient_data()` (in `backend/app/services/fhir_import.py`), create provenance records for each imported fact
   - Record: FHIR resource type, resource ID, element path, import timestamp
3. Add lineage recording to the NLP extraction pipeline:
   - In the extraction pipeline (`backend/app/services/extraction_pipeline.py`), create provenance records
   - Record: extraction method, model version, mention offsets, assertion classification
4. Create API endpoints:
   - `GET /lineage/fact/{fact_id}` — full lineage chain for a clinical fact
   - `GET /lineage/patient/{patient_id}` — all lineage records for a patient
   - `GET /lineage/document/{document_id}` — all facts derived from a document
5. Build `LineageChain.tsx` showing a vertical step-by-step trace from source to fact.
6. Build `LineageGraph.tsx` showing a DAG of how multiple sources contribute to facts.

**Acceptance criteria**:
- Every clinical fact has a complete lineage chain (source -> extraction -> mention -> mapping -> fact)
- Lineage is queryable by fact ID, patient ID, or document ID
- FHIR imports record source resource type + element path
- NLP extractions record model version + extraction method
- Lineage chain renders visually in the frontend

**Effort estimate**: 8-10 days

**Dependencies**: Provenance model and service already exist; FHIR import pipeline exists

---

### 2.2 Data Quality Dashboard

**Goal**: Completeness, consistency, accuracy, timeliness metrics.

**Files to modify**:
- `backend/app/services/data_quality_service.py` — existing OHDSI-style DQD service (has `DQDCategory`, `DQDSubcategory` enums). Extend with dashboard aggregation.
- `backend/app/services/data_completeness_service.py` — existing `DataCompletenessService` (line 127). Wire into dashboard.
- `frontend/src/app/data-quality/page.tsx` — existing data quality page. Enhance with dashboard.

**Files to create**:
- `frontend/src/components/data-quality/QualityDashboard.tsx` — main quality dashboard
- `frontend/src/components/data-quality/CompletenessCard.tsx` — per-table completeness scorecard
- `frontend/src/components/data-quality/ConsistencyChecks.tsx` — consistency check results
- `frontend/src/components/data-quality/TimelinessMetrics.tsx` — data freshness tracking
- `backend/app/api/data_quality.py` — dedicated DQ API (if not existing)

**Implementation steps**:
1. Extend `DataQualityService` to compute aggregate dashboard metrics:
   - Per-table completeness scores (leveraging `DataCompletenessService` with `TABLE_FIELDS` definitions)
   - Cross-table consistency checks (e.g., every condition_occurrence references a valid person_id)
   - Timeliness: time from document ingestion to fact availability
   - Accuracy: comparison against known gold standard values (when available)
2. Add API endpoint `GET /data-quality/dashboard` returning all four dimensions.
3. Build `QualityDashboard.tsx` with:
   - Overall quality score (composite of completeness, consistency, accuracy, timeliness)
   - Per-dimension drill-down with traffic light indicators (green/yellow/red)
   - Trend over time (weekly snapshots)
4. Build `CompletenessCard.tsx` showing per-OMOP-table completeness percentages.
5. Wire into `frontend/src/app/data-quality/page.tsx`.

**Acceptance criteria**:
- Dashboard shows completeness, consistency, accuracy, timeliness metrics
- Per-table OMOP completeness breakdown (person, condition, drug, measurement, etc.)
- Traffic light indicators for each metric dimension
- Historical trend data available (requires periodic quality snapshots)

**Effort estimate**: 5-6 days

**Dependencies**: Existing DQ service and completeness service

---

### 2.3 OHDSI Data Quality Checks

**Goal**: Run Achilles and DataQualityDashboard on OMOP output.

**Files to modify**:
- `backend/app/services/data_quality_service.py` — already implements OHDSI-style checks. Extend to cover full DQD check catalog.

**Files to create**:
- `backend/app/services/achilles_runner.py` — Achilles analysis runner
- `backend/app/api/ohdsi.py` — OHDSI-specific API endpoints
- `frontend/src/app/data-quality/ohdsi/page.tsx` — OHDSI DQD results viewer

**Implementation steps**:
1. Implement Achilles-equivalent analysis in `achilles_runner.py`:
   - Person-level characterizations: demographics, observation period, conditions, drugs, procedures
   - Database-level characterizations: record counts, concept distributions
   - Store results in standard Achilles results table format
2. Map existing DQD checks in `data_quality_service.py` to OHDSI DQD check IDs.
3. Add `GET /ohdsi/achilles/run` and `GET /ohdsi/dqd/results` endpoints.
4. Build frontend viewer that renders DQD results in the standard OHDSI format.

**Acceptance criteria**:
- Achilles-equivalent analyses produce standard output format
- DQD checks cover all three categories (completeness, conformance, plausibility)
- Results viewable in frontend with pass/fail/warning status
- Results exportable in OHDSI standard JSON format for sharing with research partners

**Effort estimate**: 8-10 days

**Dependencies**: OMOP-mapped data must exist in the system

---

### 2.4 De-identification Pipeline

**Goal**: Expert determination or Safe Harbor compliance before data sharing.

**Files to create**:
- `backend/app/services/deidentification_service.py` — PHI detection and removal
- `backend/app/schemas/deidentification.py` — de-id request/response schemas
- `backend/app/api/deidentification.py` — de-id API endpoints
- `frontend/src/app/exports/deidentify/page.tsx` — de-identification workflow UI

**Implementation steps**:
1. Create `DeidentificationService` with two modes:
   - **Safe Harbor**: Remove all 18 HIPAA identifiers (names, dates, locations, etc.)
     - Leverage existing PHI detection patterns from `backend/app/services/audit_service.py` (lines 56-60: SSN, MRN regex patterns)
     - Add patterns for: names, addresses, dates, phone numbers, email, URLs, IP addresses, biometric IDs, serial numbers, photos, account numbers
     - Date shifting: Replace exact dates with shifted dates (random offset per patient, consistent within patient)
     - Geographic generalization: Replace zip codes with first 3 digits (if population > 20K)
   - **Expert Determination**: Flag records that need expert review, provide risk assessment score
2. Apply de-identification to:
   - Clinical fact exports (remove patient_id, replace with de-identified ID)
   - Document text (redact PHI spans)
   - FHIR resource exports (remove identifying elements)
   - Knowledge graph exports (anonymize patient nodes)
3. Add audit logging for all de-identification operations.
4. Build frontend workflow for: select data scope -> choose method -> preview -> confirm -> export.

**Acceptance criteria**:
- Safe Harbor method removes all 18 HIPAA identifier types
- Date shifting is consistent per patient (same offset for all dates)
- De-identified data cannot be re-identified through combination
- Audit trail records: who requested, what data, which method, when
- Output available in OMOP CDM, FHIR, and CSV formats

**Effort estimate**: 8-10 days

**Dependencies**: PHI detection patterns (existing in audit_service), FHIR export pipeline

---

### 2.5 Multimodal Data Integration Plan

**Goal**: Clinical notes + lab results + imaging + genomics coalesce in the knowledge graph.

**Files to modify**:
- `backend/app/models/knowledge_graph.py` — extend `KGNode` with multimodal type support
- `backend/app/schemas/knowledge_graph.py` — extend `NodeType` enum
- `backend/app/services/graph_builder.py` — extend graph builder for multimodal data
- `backend/app/services/fhir_import.py` — extend to handle imaging and genomics FHIR resources

**Files to create**:
- `backend/app/services/multimodal_integration_service.py` — multimodal data fusion
- `frontend/src/components/KnowledgeGraph/MultimodalNode.tsx` — multimodal node rendering

**Implementation steps**:
1. Extend `NodeType` enum in `backend/app/schemas/knowledge_graph.py` to include: `IMAGING_STUDY`, `GENOMIC_VARIANT`, `BIOMARKER`, `PATHOLOGY_REPORT`.
2. Create `MultimodalIntegrationService` that:
   - Ingests imaging references (DICOM metadata via FHIR ImagingStudy)
   - Ingests genomic data (VCF via FHIR MolecularSequence/GenomicStudy)
   - Links imaging and genomic data to patient KG nodes
   - Creates cross-modal edges (e.g., genomic variant -> condition, imaging finding -> condition)
3. Extend `FHIRImportService` to handle: `ImagingStudy`, `MolecularSequence`, `Specimen` resources.
4. Build `MultimodalNode.tsx` with distinct visual representations for each data type.

**Acceptance criteria**:
- KG supports imaging, genomic, and biomarker node types
- FHIR ImagingStudy and MolecularSequence resources can be imported
- Cross-modal edges link genomic variants to conditions and medications
- Multimodal nodes render distinctly in the KG visualization

**Effort estimate**: 10-14 days

**Dependencies**: KG builder, FHIR import pipeline, Node type system

---

### 2.6 Data Completeness Scoring Per Patient

**Goal**: For trial matching, know whether you have enough data to make a confident determination.

**Files to modify**:
- `backend/app/services/data_completeness_service.py` — extend with per-patient scoring
- `backend/app/services/trial_eligibility_service.py` — integrate completeness score into screening
- `backend/app/schemas/trial.py` — add completeness fields to `PatientEligibility`
- `frontend/src/app/trials/[id]/page.tsx` — display completeness indicator

**Files to create**:
- `frontend/src/components/trials/DataCompletenessIndicator.tsx` — visual completeness badge

**Implementation steps**:
1. Add per-patient completeness scoring to `DataCompletenessService`:
   - For each patient, compute: % of criteria with evaluable data
   - Score dimensions: demographic data, condition history, medication history, lab results, procedure history
   - Return per-criterion data availability: HAS_DATA / MISSING / PARTIAL
2. Integrate into `TrialEligibilityService._evaluate_patient()`:
   - When data is missing for a criterion, mark as `UNKNOWN` (not `FAIL`)
   - Add `data_completeness_score` field to `PatientEligibility` (existing schema at line 167-180)
   - Separate "NOT MET" (data exists, criterion failed) from "UNKNOWN" (insufficient data)
3. Build `DataCompletenessIndicator.tsx` as a circular progress badge showing % data available.
4. Display in the Candidates tab: patients with low completeness get a yellow warning badge.

**Acceptance criteria**:
- Each patient-trial pair has a data completeness score (0-100%)
- "UNKNOWN" and "NOT MET" are clearly distinguished in UI
- Patients with <50% data completeness are flagged
- Per-criterion data availability shown in match explanation

**Effort estimate**: 3-4 days

**Dependencies**: Data completeness service (existing), trial eligibility service (existing)

---

### 2.7 Competitive Data Moat Strategy

**Goal**: Document how we build proprietary data assets. This is a strategic document, not code.

**Files to create**:
- `docs/strategy/data_moat.md` — data moat strategy document

**Implementation steps**:
1. Document the current data asset: what data exists, how much, from how many sources.
2. Analyze competitive approaches:
   - TriNetX: federated network (220+ HCOs, 150M EHRs)
   - Tempus: multimodal (genomic + clinical + imaging)
   - Komodo: claims data (330M patients)
3. Propose our differentiation strategy based on current architecture capabilities.
4. Define data acquisition roadmap: which health systems to target, data sharing agreements needed.

**Acceptance criteria**:
- Strategy document completed with competitive analysis
- Clear differentiation thesis articulated
- Data acquisition roadmap with prioritized targets

**Effort estimate**: 2-3 days (strategy document, no code)

**Dependencies**: None

---

## 3. VP Data Science

### 3.1 Model Evaluation Framework

**Goal**: Standardized precision/recall/F1 measurement for NLP extraction per entity type.

**Files to modify**:
- `backend/app/services/model_registry_service.py` — existing `ModelRegistry` with `ModelVersion.metrics` (line 53). Extend with evaluation framework.
- `backend/app/services/nlp_ensemble.py` — NLP ensemble service to instrument with evaluation hooks

**Files to create**:
- `backend/app/services/model_evaluation_service.py` — standardized evaluation framework
- `backend/app/schemas/model_evaluation.py` — evaluation result schemas
- `backend/app/api/model_evaluation.py` — evaluation API endpoints
- `frontend/src/app/analytics/models/evaluation/page.tsx` — model evaluation dashboard
- `frontend/src/components/models/EvaluationReport.tsx` — evaluation report component
- `frontend/src/components/models/ConfusionMatrix.tsx` — per-entity confusion matrix
- `backend/tests/test_model_evaluation.py` — evaluation framework tests

**Implementation steps**:
1. Create `ModelEvaluationService` that:
   - Takes a model ID + annotated test dataset (gold standard)
   - Runs the model on test inputs
   - Computes per-entity-type metrics:
     - Conditions: precision, recall, F1
     - Medications: precision, recall, F1
     - Lab values: precision, recall, F1 + MAE for numeric values
     - Procedures: precision, recall, F1
   - Computes aggregate metrics: macro-F1, micro-F1, weighted-F1
   - Generates confidence intervals (bootstrap)
   - Stores results in `ModelVersion.metrics`
2. Define evaluation schemas:
   ```python
   class EntityEvaluation(BaseModel):
       entity_type: str  # condition, medication, lab_value, procedure
       true_positives: int
       false_positives: int
       false_negatives: int
       precision: float
       recall: float
       f1: float
       support: int  # number of gold standard examples

   class ModelEvaluationResult(BaseModel):
       model_id: str
       model_version: str
       evaluation_date: datetime
       dataset_name: str
       dataset_size: int
       per_entity: list[EntityEvaluation]
       macro_f1: float
       micro_f1: float
       weighted_f1: float
       confidence_interval_95: tuple[float, float]
   ```
3. Add API endpoints: `POST /models/{model_id}/evaluate`, `GET /models/{model_id}/evaluations`.
4. Build evaluation dashboard showing per-entity metrics with bar charts and confusion matrices.

**Acceptance criteria**:
- Evaluation runs on annotated test dataset and produces per-entity-type metrics
- Results stored in model registry with version tracking
- Confidence intervals computed via bootstrap
- Dashboard shows precision/recall/F1 per entity type
- Evaluation can be triggered from UI or API

**Effort estimate**: 6-8 days

**Dependencies**: Model registry service (existing), annotated test datasets (need to be created - see 3.2)

---

### 3.2 Gold Standard Datasets

**Goal**: Clinician-annotated corpora for NLP validation. Minimum 200 documents, two annotators per document, Cohen's kappa > 0.75.

**Files to create**:
- `backend/app/services/annotation_service.py` — annotation management service
- `backend/app/models/annotation.py` — annotation ORM models
- `backend/app/schemas/annotation.py` — annotation schemas
- `backend/app/api/annotations.py` — annotation API endpoints
- `frontend/src/app/nlp/annotations/page.tsx` — annotation workbench
- `frontend/src/components/annotations/AnnotationEditor.tsx` — clinical text annotation UI
- `frontend/src/components/annotations/InterAnnotatorAgreement.tsx` — IAA metrics display
- `backend/app/services/iaa_calculator.py` — inter-annotator agreement calculator

**Implementation steps**:
1. Create `Annotation` model:
   ```python
   class Annotation(Base):
       __tablename__ = "annotations"
       document_id: Mapped[str]  # FK to documents
       annotator_id: Mapped[str]
       annotation_set: Mapped[str]  # gold standard set name
       spans: Mapped[list[dict]]  # [{start, end, label, text, attributes}]
       created_at: Mapped[datetime]
       status: Mapped[str]  # draft, submitted, adjudicated
   ```
2. Create `AnnotationService` that:
   - Assigns documents to annotators (round-robin, ensuring 2+ per document)
   - Computes inter-annotator agreement (Cohen's kappa for 2 annotators, Fleiss' kappa for 3+)
   - Manages adjudication workflow (resolve disagreements)
   - Exports gold standard datasets in standard formats (CoNLL, BRAT, JSON)
3. Create `IAACalculator` service:
   - Token-level agreement for entity spans
   - Cohen's kappa per entity type
   - Confusion matrices between annotators
4. Build `AnnotationEditor.tsx`:
   - Display clinical note text
   - Select text spans and assign entity labels (condition, medication, lab, procedure)
   - Add attributes (assertion, temporality, experiencer) — matching `Mention` model attributes
   - Keyboard shortcuts for efficient annotation
5. Build `InterAnnotatorAgreement.tsx` showing kappa scores per entity type.

**Acceptance criteria**:
- Annotation workbench supports span-level entity annotation
- Two annotators per document enforced
- Cohen's kappa computed and displayed per entity type
- Adjudication workflow resolves disagreements
- Gold standard exportable in CoNLL and JSON formats
- Target: 200+ annotated documents

**Effort estimate**: 10-14 days

**Dependencies**: Documents must exist in the system

---

### 3.3 A/B Testing Infrastructure

**Goal**: Compare NLP model versions on same input data with audit trail.

**Files to modify**:
- `backend/app/services/model_registry_service.py` — extend with experiment tracking
- `backend/app/services/nlp_ensemble.py` — add model version routing

**Files to create**:
- `backend/app/services/ab_testing_service.py` — A/B test management
- `backend/app/models/experiment.py` — experiment ORM model
- `backend/app/schemas/experiment.py` — experiment schemas
- `backend/app/api/experiments.py` — experiment API endpoints
- `frontend/src/app/analytics/models/experiments/page.tsx` — experiment dashboard
- `frontend/src/components/models/ExperimentComparison.tsx` — side-by-side model comparison

**Implementation steps**:
1. Create `Experiment` model:
   ```python
   class Experiment(Base):
       __tablename__ = "experiments"
       name: Mapped[str]
       description: Mapped[str | None]
       model_a_id: Mapped[str]  # control model
       model_b_id: Mapped[str]  # challenger model
       traffic_split: Mapped[float]  # % going to model B (0.0-1.0)
       status: Mapped[str]  # draft, running, completed, cancelled
       start_date: Mapped[datetime | None]
       end_date: Mapped[datetime | None]
       metrics: Mapped[dict | None]  # aggregated results
   ```
2. Create `ABTestingService` that:
   - Creates experiments with control/challenger model assignment
   - Routes documents to model versions based on traffic split
   - Maintains audit trail: which model version produced each extraction
   - Computes statistical significance (two-sample proportion test for binary outcomes)
   - Supports multi-armed bandit for continuous optimization
3. Add audit trail field to extraction outputs:
   - In NLP extraction results, record `model_version_id` and `experiment_id`
4. Build `ExperimentComparison.tsx` showing side-by-side metrics for A vs B.

**Acceptance criteria**:
- Experiments can be created with two model versions and configurable traffic split
- Every extraction records which model version produced it
- Statistical significance calculated and displayed
- Experiment results include per-entity-type metrics comparison
- Experiment can be stopped early if challenger is clearly better/worse

**Effort estimate**: 7-9 days

**Dependencies**: Model registry (existing), model evaluation framework (3.1)

---

### 3.4 Drift Detection

**Goal**: Monitor NLP performance degradation over time.

**Files to create**:
- `backend/app/services/drift_detection_service.py` — statistical drift detection
- `backend/app/schemas/drift.py` — drift detection schemas
- `backend/app/api/drift.py` — drift monitoring API
- `frontend/src/app/analytics/models/drift/page.tsx` — drift monitoring dashboard
- `frontend/src/components/models/DriftChart.tsx` — drift trend visualization
- `frontend/src/components/models/DriftAlert.tsx` — drift alert component

**Implementation steps**:
1. Create `DriftDetectionService` implementing three drift types:
   - **Input drift**: Monitor changes in input data distribution (document length, vocabulary, entity density)
     - Use KL divergence or Population Stability Index (PSI)
     - Compare current week's data against baseline distribution
   - **Concept drift**: Monitor changes in entity type distributions, new terminology
     - Track frequency of unmapped concepts
     - Detect new abbreviations or terminology not seen in training
   - **Performance drift**: Monitor extraction quality over time
     - Compare model confidence scores against baseline
     - Track override rates (clinician corrections) as a proxy for quality
2. Implement weekly drift monitoring jobs:
   - Compute drift metrics per entity type
   - Store results with timestamp for trend tracking
   - Trigger alerts when drift exceeds thresholds (configurable per metric)
3. Build `DriftChart.tsx` showing drift metrics over time with threshold lines.
4. Build `DriftAlert.tsx` showing active drift alerts with severity levels.

**Acceptance criteria**:
- Input drift detected via PSI with configurable threshold (default: 0.1 = warning, 0.25 = critical)
- Concept drift tracked via unmapped concept rate
- Performance drift tracked via confidence score distribution
- Weekly drift reports generated automatically
- Alerts fire when drift exceeds thresholds

**Effort estimate**: 5-7 days

**Dependencies**: Model evaluation framework (3.1) for baseline metrics, existing NLP pipeline

---

### 3.5 Explainability for All Stakeholders

**Goal**: Clinicians need criteria-level pass/fail. Sponsors need aggregate match quality. Patients need plain-language. Regulators need full audit trail.

**Files to modify**:
- `backend/app/schemas/trial.py` — `CriterionResult` (lines 150-164) already has evidence fields. Extend with per-stakeholder views.
- `backend/app/services/trial_eligibility_service.py` — add explanation generation
- VP Product 1.2 (Per-Match Explainability Engine) — extends the same infrastructure

**Files to create**:
- `backend/app/services/explanation_service.py` — multi-audience explanation generator
- `backend/app/schemas/explanation.py` — explanation schemas per audience
- `frontend/src/components/trials/ClinicalExplanation.tsx` — clinician view
- `frontend/src/components/trials/SponsorExplanation.tsx` — sponsor/aggregate view
- `frontend/src/components/trials/PatientExplanation.tsx` — patient-facing plain language
- `frontend/src/components/trials/RegulatoryExplanation.tsx` — full audit trail view

**Implementation steps**:
1. Create `ExplanationService` with four rendering modes:
   - **Clinician**: criteria-level pass/fail with confidence badges, evidence links, source document references. Uses `CriterionResult` directly.
   - **Sponsor**: aggregate match quality metrics, criteria sensitivity analysis, per-criterion failure rates. SHAP-like contribution scores showing which criteria drive the match score.
   - **Patient**: plain-language template-based explanations. "Based on your reported conditions, you may be eligible for this trial because..." No clinical codes or technical details.
   - **Regulator**: full audit trail including model version, algorithm ID, data snapshot timestamp, all evidence chain, override history. Formatted for 21 CFR Part 11 compliance.
2. Generate explanations at screening time and store as part of `TrialEnrollment` record.
3. Build each frontend component rendering the appropriate explanation view.
4. Add audience selector to the match detail page.

**Acceptance criteria**:
- Four distinct explanation views generated per match
- Clinician view shows criteria pass/fail with evidence
- Sponsor view shows aggregate metrics with SHAP-like contributions
- Patient view uses plain language (6th grade reading level)
- Regulatory view includes full audit trail with timestamps and model versions

**Effort estimate**: 6-8 days

**Dependencies**: Per-match explainability engine (VP Product 1.2), audit logging infrastructure

---

### 3.6 Fairness Audit Framework

**Goal**: Match rates by race, ethnicity, sex, age, geography.

**Files to create**:
- `backend/app/services/fairness_audit_service.py` — fairness metrics computation
- `backend/app/schemas/fairness.py` — fairness audit schemas
- `backend/app/api/fairness.py` — fairness API endpoints
- `frontend/src/app/analytics/fairness/page.tsx` — fairness dashboard
- `frontend/src/components/fairness/DemographicParity.tsx` — demographic parity charts
- `frontend/src/components/fairness/FairnessReport.tsx` — comprehensive fairness report
- `backend/tests/test_fairness_audit.py` — fairness audit tests

**Implementation steps**:
1. Create `FairnessAuditService` that computes:
   - **Demographic parity**: match rates per demographic group (race, ethnicity, sex, age band, geography)
   - **Equal opportunity**: true positive rates per group (requires ground truth)
   - **Predictive parity**: precision per group
   - **Statistical parity difference**: max difference in match rates between groups
   - **Disparate impact ratio**: min(group_match_rate) / max(group_match_rate). Alert if < 0.8 (four-fifths rule)
2. Run fairness audits:
   - Per-trial: compare match rates across demographics for a single trial
   - Platform-wide: aggregate fairness metrics across all trials
   - Per-model: compare fairness metrics between model versions (ties into A/B testing 3.3)
3. Add `GET /fairness/audit/trial/{trial_id}` and `GET /fairness/audit/platform` endpoints.
4. Build `DemographicParity.tsx` showing match rates by group as grouped bar chart.
5. Build `FairnessReport.tsx` as a printable PDF-ready report for regulatory submissions.
6. Schedule quarterly automated fairness audits.

**Acceptance criteria**:
- Demographic parity computed per trial and platform-wide
- Disparate impact ratio tracked with alert at < 0.8 threshold
- Fairness report exportable for FDA regulatory submissions
- Fairness metrics stored historically for trend analysis
- Per-model fairness comparison available through experiment infrastructure

**Effort estimate**: 6-8 days

**Dependencies**: Patient demographic data from FHIR import, trial screening results

---

### 3.7 Model Governance Framework

**Goal**: Model registry, validation protocol, bias audit schedule, drift monitoring, incident response, retraining schedule, model cards.

**Files to modify**:
- `backend/app/services/model_registry_service.py` — existing service with `ModelVersion`, `ModelStage` (lines 23-58). Extend with governance workflow.

**Files to create**:
- `backend/app/services/model_governance_service.py` — governance lifecycle management
- `backend/app/models/model_governance.py` — governance ORM models (approval records, audit schedule)
- `backend/app/schemas/model_governance.py` — governance schemas
- `backend/app/api/model_governance.py` — governance API endpoints
- `frontend/src/app/analytics/models/governance/page.tsx` — governance dashboard
- `frontend/src/components/models/ModelCard.tsx` — model card renderer
- `frontend/src/components/models/GovernanceTimeline.tsx` — governance lifecycle timeline
- `docs/templates/model_card_template.md` — model card template

**Implementation steps**:
1. Create `ModelGovernanceService` that manages:
   - **Model lifecycle**: development -> staging -> production -> archived (using existing `ModelStage` enum)
   - **Approval workflow**: stage transitions require approval with documented rationale
   - **Validation protocol**: holdout evaluation required before promotion to production
   - **Bias audit schedule**: quarterly automated fairness audit (ties into 3.6)
   - **Drift monitoring schedule**: weekly automated drift detection (ties into 3.4)
   - **Incident response**: model failure workflow with severity levels and response SLAs
   - **Retraining schedule**: quarterly or triggered by drift detection
2. Create model card template including:
   - Model purpose and intended use
   - Training data description and demographics
   - Performance metrics per entity type
   - Fairness metrics per demographic group
   - Limitations and known failure modes
   - Version history
3. Build governance dashboard showing:
   - All models with current stage and last validation date
   - Upcoming audit schedule
   - Active incidents
   - Model cards for all production models

**Acceptance criteria**:
- All production models have model cards
- Stage transitions require documented approval
- Quarterly bias audits scheduled and tracked
- Weekly drift monitoring active with alerting
- Incident response workflow documented with SLAs
- Retraining triggered automatically when drift exceeds threshold

**Effort estimate**: 8-10 days

**Dependencies**: Model registry (existing), fairness audits (3.6), drift detection (3.4)

---

### 3.8 Experiment Tracking

**Goal**: MLflow-equivalent for NLP model versioning. Reproducible results.

**Files to modify**:
- `backend/app/services/model_registry_service.py` — extend `ModelVersion` with full experiment tracking

**Files to create**:
- `backend/app/services/experiment_tracking_service.py` — experiment run management
- `backend/app/models/experiment_run.py` — experiment run ORM model
- `backend/app/schemas/experiment_tracking.py` — run schemas
- `frontend/src/app/analytics/models/runs/page.tsx` — experiment runs list
- `frontend/src/components/models/RunComparison.tsx` — multi-run comparison view
- `frontend/src/components/models/RunMetrics.tsx` — per-run metrics detail

**Implementation steps**:
1. Create `ExperimentRun` model:
   ```python
   class ExperimentRun(Base):
       __tablename__ = "experiment_runs"
       experiment_name: Mapped[str]
       run_name: Mapped[str]
       model_type: Mapped[str]
       parameters: Mapped[dict]  # hyperparameters
       metrics: Mapped[dict]  # training and eval metrics
       artifacts: Mapped[dict]  # model file paths, data versions
       tags: Mapped[dict]  # custom metadata
       git_commit: Mapped[str | None]
       data_version: Mapped[str | None]  # hash of training data
       status: Mapped[str]  # running, completed, failed
       start_time: Mapped[datetime]
       end_time: Mapped[datetime | None]
       duration_seconds: Mapped[float | None]
   ```
2. Create `ExperimentTrackingService` that:
   - Logs training runs with parameters, metrics, and artifacts
   - Computes data version hashes for reproducibility
   - Records git commit hash at training time
   - Supports run comparison (select N runs, compare metrics)
   - Ensures reproducibility: "Same input document must produce identical extraction results across versions"
3. Build `RunComparison.tsx` with parallel coordinates chart comparing runs.
4. Build `RunMetrics.tsx` showing detailed metrics for a single run.

**Acceptance criteria**:
- Training runs logged with parameters, metrics, artifacts, data version
- Git commit hash recorded for each run
- Runs are reproducible (same data version + same parameters = same results)
- Multi-run comparison available in UI
- Runs searchable by experiment name, model type, date range

**Effort estimate**: 5-7 days

**Dependencies**: Model registry (existing)

---

## 4. Head of Partnerships / BD

### 4.1 Pharma RFP Response Template

**Goal**: Pre-built responses for standard Tier 1 requirements.

**Files to create**:
- `docs/rfp/pharma_rfp_template.md` — master RFP response template
- `docs/rfp/sections/hipaa.md` — HIPAA compliance response
- `docs/rfp/sections/soc2.md` — SOC 2 readiness response
- `docs/rfp/sections/21cfr11.md` — 21 CFR Part 11 compliance
- `docs/rfp/sections/ehr_integration.md` — EHR integration capabilities
- `docs/rfp/sections/deidentification.md` — De-identification methodology
- `docs/rfp/sections/consent_management.md` — Consent management
- `docs/rfp/sections/audit_logging.md` — Audit logging capabilities
- `docs/rfp/sections/data_quality.md` — Data quality framework
- `docs/rfp/sections/matching_methodology.md` — Matching algorithm methodology

**Implementation steps**:
1. Create master template with sections covering all Tier 1 pharma RFP requirements:
   - HIPAA: Reference audit logging model (`backend/app/models/audit.py`), PHI detection patterns, access controls
   - SOC 2: Reference security infrastructure, TLS configuration, auth system
   - 21 CFR Part 11: Reference audit trails, electronic signatures (future), data integrity
   - EHR Integration: Reference Metriport/FHIR integration (`backend/app/services/fhir_import.py`, `backend/app/services/metriport_service.py`)
   - De-identification: Reference de-id pipeline (CDO 2.4)
   - Consent: Document consent management approach
   - Audit: Reference `AuditLog` model with 6+ year retention, immutability
   - Data Quality: Reference OHDSI DQD framework (`backend/app/services/data_quality_service.py`)
   - Matching: Reference `TrialEligibilityService`, `CriterionResult` with evidence chain
2. Each section includes:
   - Current capability (what exists today)
   - Roadmap items (planned enhancements with timelines)
   - Compliance certifications status
   - References to documentation/evidence

**Acceptance criteria**:
- All Tier 1 requirements have pre-written responses
- Responses reference actual system capabilities with evidence
- Template can be customized per RFP in < 4 hours
- Responses reviewed by legal/compliance

**Effort estimate**: 5-7 days (writing, not code)

**Dependencies**: Many sections depend on hardening items being completed or in progress

---

### 4.2 EDC/CTMS Integration Roadmap

**Goal**: Medidata Rave, Veeva Vault, Oracle. Pharma RFP Tier 1 requirements.

**Files to create**:
- `docs/integrations/edc_ctms_roadmap.md` — integration roadmap document
- `backend/app/services/edc_integration_service.py` — EDC integration abstraction layer
- `backend/app/schemas/edc.py` — EDC integration schemas
- `backend/app/api/integrations.py` — integration API endpoints

**Implementation steps**:
1. Design integration abstraction layer:
   ```python
   class EDCIntegrationService:
       """Abstract interface for EDC system integration."""
       async def push_enrollment(self, enrollment: EnrollmentResponse, target: str) -> dict
       async def pull_trial_definition(self, trial_id: str, source: str) -> TrialCreate
       async def sync_screening_results(self, results: ScreeningResponse, target: str) -> dict
   ```
2. Document integration approach for each EDC/CTMS:
   - **Medidata Rave**: REST API integration for subject enrollment, CRF data push
   - **Veeva Vault CTMS**: CDMS API for trial management, site enrollment tracking
   - **Oracle Clinical One**: REST API for randomization, enrollment management
3. Create roadmap with phases:
   - Phase 1 (Month 1-3): API abstraction layer, Medidata Rave connector (most common)
   - Phase 2 (Month 3-6): Veeva Vault connector
   - Phase 3 (Month 6-9): Oracle Clinical One connector
4. Define data mapping: our `TrialEnrollment` -> EDC enrollment record format.

**Acceptance criteria**:
- Integration abstraction layer designed with clear interface
- Medidata Rave connector specified with API endpoints and data mapping
- Roadmap with timeline for all three EDC systems
- Data mapping documented between our schemas and EDC formats

**Effort estimate**: 3-5 days (design + documentation), 15-20 days per connector implementation

**Dependencies**: Trial enrollment infrastructure (existing)

---

### 4.3 Published Enrollment Metrics

**Goal**: Screen-to-enroll ratio, time-to-FPFV, screen failure rates. Sponsors won't pay without proof.

**Files to modify**:
- VP Product 1.3 (Screen Failure Analytics) and 1.7 (Funnel Analytics Dashboard) provide the underlying data
- `frontend/src/app/trials/analytics/page.tsx` — from VP Product 1.7

**Files to create**:
- `backend/app/services/enrollment_metrics_export_service.py` — metrics export for external publishing
- `frontend/src/app/trials/metrics-report/page.tsx` — publishable metrics report page
- `frontend/src/components/trials/MetricsReport.tsx` — formatted metrics report for sponsors
- `docs/metrics/enrollment_benchmarks.md` — benchmark metrics documentation

**Implementation steps**:
1. Create `EnrollmentMetricsExportService` that:
   - Aggregates platform-wide enrollment metrics
   - Computes benchmark metrics: screen-to-enroll ratio, time-to-FPFV, screen failure rate, diversity enrollment rates
   - Generates publishable report format (PDF-ready HTML)
   - Anonymizes/aggregates data so no PHI is exposed
2. Build `MetricsReport.tsx` as a printable report component with:
   - Executive summary with key metrics
   - Per-therapeutic-area breakdown
   - Trend charts (monthly)
   - Comparison to industry benchmarks
   - De-identified case studies
3. Create benchmark documentation showing platform performance vs. industry averages.

**Acceptance criteria**:
- Publishable metrics report available for external sharing
- No PHI exposed in reports (all data aggregated/anonymized)
- Metrics include: screen-to-enroll, time-to-FPFV, screen failure rate, diversity enrollment
- Reports exportable as PDF
- Industry benchmark comparison included

**Effort estimate**: 4-5 days

**Dependencies**: Screen failure analytics (VP Product 1.3), funnel analytics (VP Product 1.7)

---

### 4.4 Site Network Strategy

**Goal**: Partner with health systems. The federated data network IS the competitive moat.

**Files to create**:
- `docs/strategy/site_network_strategy.md` — site network strategy document
- `docs/templates/site_partnership_agreement.md` — partnership agreement template
- `docs/templates/data_sharing_framework.md` — data sharing framework

**Implementation steps**:
1. Document site network strategy:
   - Target site types: academic medical centers, community health systems, specialty clinics
   - Value proposition to sites: free analytics, trial matching, enrollment support
   - Data contribution model: federated (data stays at site) vs. centralized (data moves to platform)
   - Reference TriNetX model: 220+ HCOs participate free in exchange for analytics access
2. Create partnership agreement templates:
   - BAA (Business Associate Agreement) — required for any PHI sharing
   - DUA (Data Use Agreement) — for research data sharing
   - Site activation agreement — for trial enrollment at partner sites
3. Define onboarding process:
   - Technical: FHIR integration setup (leveraging existing `FHIRImportService`)
   - Legal: BAA/DUA execution
   - Operational: Site training, workflow integration

**Acceptance criteria**:
- Strategy document completed with target site profiles
- Partnership agreement templates ready for legal review
- Onboarding process documented with timeline estimates
- Value proposition articulated for different site types

**Effort estimate**: 3-5 days (strategy + templates, no code)

**Dependencies**: FHIR integration capability (existing)

---

### 4.5 Data Licensing Program Design

**Goal**: De-identified dataset access for pharma researchers. $200K-$1.5M/yr. Highest margin revenue stream.

**Files to modify**:
- CDO 2.4 (De-identification Pipeline) — required foundation
- `backend/app/services/bulk_export_service.py` — existing bulk export service

**Files to create**:
- `backend/app/services/data_licensing_service.py` — data licensing management
- `backend/app/models/data_license.py` — licensing ORM models
- `backend/app/schemas/data_license.py` — licensing schemas
- `backend/app/api/data_licensing.py` — licensing API endpoints
- `frontend/src/app/admin/data-licensing/page.tsx` — licensing management UI
- `docs/legal/data_licensing_agreement.md` — template licensing agreement

**Implementation steps**:
1. Create `DataLicense` model:
   ```python
   class DataLicense(Base):
       __tablename__ = "data_licenses"
       licensee_name: Mapped[str]  # pharma company name
       license_type: Mapped[str]  # research, commercial, regulatory
       datasets_included: Mapped[list[str]]  # which datasets are licensed
       patient_count: Mapped[int]  # approximate patient count in licensed dataset
       start_date: Mapped[datetime]
       end_date: Mapped[datetime]
       annual_fee: Mapped[float]
       deidentification_method: Mapped[str]  # safe_harbor, expert_determination
       usage_restrictions: Mapped[dict]  # what the licensee can/cannot do
       status: Mapped[str]  # draft, active, expired, revoked
   ```
2. Create `DataLicensingService` that:
   - Manages license lifecycle (create, activate, renew, revoke)
   - Generates de-identified dataset exports (leveraging CDO 2.4 de-id pipeline)
   - Tracks data access by licensees
   - Computes dataset statistics for pricing (patient count, condition coverage, date range)
   - Generates usage reports for licensees
3. Design tiered pricing:
   - **Standard**: De-identified clinical data, conditions + medications + demographics. $200K-$500K/yr
   - **Premium**: Standard + lab results + procedures + temporal relationships. $500K-$1M/yr
   - **Enterprise**: Premium + knowledge graph access + custom queries + API access. $1M-$1.5M/yr
4. Build licensing management UI for internal administration.

**Acceptance criteria**:
- Licensing lifecycle managed (create, activate, renew, revoke)
- De-identified datasets generated on demand
- Access tracked per licensee for compliance
- Tiered pricing structure documented
- Template licensing agreement ready for legal review

**Effort estimate**: 7-10 days (code) + legal review time

**Dependencies**: De-identification pipeline (CDO 2.4)

---

### 4.6 Diversity Enrollment Capabilities

**Goal**: FDORA DAP compliance tools. Both regulatory and sales differentiator.

This item is covered by VP Product 1.8 (FDORA Diversity Enrollment Tools). The BD perspective adds:

**Additional files to create**:
- `docs/compliance/fdora_dap_capabilities.md` — external-facing capability document
- `docs/rfp/sections/diversity_enrollment.md` — RFP response section for diversity capabilities

**Additional implementation steps**:
1. Create external-facing capability document showing:
   - How the platform supports DAP goal setting
   - Real-time diversity monitoring features
   - Enrollment optimization for underrepresented populations
   - Reporting capabilities for FDA submission
2. Add diversity enrollment section to pharma RFP template (4.1).
3. Include diversity metrics in published enrollment metrics (4.3).

**Acceptance criteria**:
- External capability document ready for pharma sales conversations
- RFP section addresses all FDORA DAP requirements
- Published metrics include diversity enrollment data

**Effort estimate**: 2-3 days (documentation, leveraging VP Product 1.8 implementation)

**Dependencies**: VP Product 1.8 (FDORA Diversity Enrollment Tools)

---

## Cross-Cutting Dependencies

| Item | Blocks | Blocked By |
|------|--------|------------|
| CDO 2.1 (Data Lineage) | VP Product 1.2 (Explainability), Data Science 3.5 (Explainability) | None |
| CDO 2.4 (De-identification) | BD 4.5 (Data Licensing) | Audit service (existing) |
| VP Product 1.3 (Screen Failure Analytics) | VP Product 1.9 (Protocol Optimization), BD 4.3 (Published Metrics) | Trial screening (existing) |
| VP Product 1.7 (Funnel Analytics) | BD 4.3 (Published Metrics) | VP Product 1.3, 1.6 |
| VP Product 1.8 (Diversity Tools) | BD 4.6 (Diversity Capabilities) | FHIR demographics (existing) |
| Data Science 3.1 (Model Evaluation) | Data Science 3.3 (A/B Testing), 3.4 (Drift), 3.7 (Governance) | Data Science 3.2 (Gold Standard) |
| Data Science 3.6 (Fairness Audit) | Data Science 3.7 (Governance) | Patient demographics, screening results |

## Implementation Priority Order

### Phase 1: Foundation (Weeks 1-4)
1. CDO 2.1 — Data Lineage Tracking (8-10 days)
2. VP Product 1.3 — Screen Failure Analytics (4-5 days)
3. CDO 2.6 — Data Completeness Scoring (3-4 days)
4. VP Product 1.1 — Clinical Coordinator UX Audit (5-7 days)

### Phase 2: Core Features (Weeks 5-10)
5. VP Product 1.2 — Per-Match Explainability Engine (6-8 days)
6. CDO 2.2 — Data Quality Dashboard (5-6 days)
7. VP Product 1.7 — Funnel Analytics Dashboard (5-7 days)
8. Data Science 3.1 — Model Evaluation Framework (6-8 days)
9. VP Product 1.4 — Knowledge Graph Visualization (6-8 days)

### Phase 3: Advanced Capabilities (Weeks 11-18)
10. VP Product 1.8 — FDORA Diversity Enrollment Tools (6-8 days)
11. Data Science 3.2 — Gold Standard Datasets (10-14 days)
12. CDO 2.4 — De-identification Pipeline (8-10 days)
13. VP Product 1.5 — Patient-Facing Screener (7-10 days)
14. VP Product 1.6 — Site Referral Orchestration (5-7 days)
15. Data Science 3.6 — Fairness Audit Framework (6-8 days)
16. Data Science 3.4 — Drift Detection (5-7 days)

### Phase 4: Partnerships & Governance (Weeks 19-26)
17. BD 4.1 — Pharma RFP Response Template (5-7 days)
18. BD 4.3 — Published Enrollment Metrics (4-5 days)
19. BD 4.5 — Data Licensing Program Design (7-10 days)
20. Data Science 3.3 — A/B Testing Infrastructure (7-9 days)
21. Data Science 3.7 — Model Governance Framework (8-10 days)
22. Data Science 3.8 — Experiment Tracking (5-7 days)
23. CDO 2.3 — OHDSI Data Quality Checks (8-10 days)
24. VP Product 1.9 — Protocol Optimization Feedback (4-5 days)

### Phase 5: Strategic (Weeks 27+)
25. CDO 2.5 — Multimodal Data Integration (10-14 days)
26. CDO 2.7 — Competitive Data Moat Strategy (2-3 days)
27. BD 4.2 — EDC/CTMS Integration Roadmap (3-5 days design + 15-20 days per connector)
28. BD 4.4 — Site Network Strategy (3-5 days)
29. BD 4.6 — Diversity Enrollment Capabilities (2-3 days)
30. Data Science 3.5 — Multi-Stakeholder Explainability (6-8 days)

## Total Effort Estimate

| Section | Items | Total Days |
|---------|-------|-----------|
| VP Product | 9 items | 48-62 days |
| CDO | 7 items | 44-56 days |
| VP Data Science | 8 items | 53-71 days |
| Head of Partnerships | 6 items | 24-35 days |
| **Total** | **30 items** | **169-224 days** |

With 2-3 engineers per track working in parallel across all four sections, estimated calendar time: **6-9 months** for full implementation.

---

*Generated from codebase analysis of /Users/alexstinard/projects/brainstorm/jan-14-2026. February 2026.*
