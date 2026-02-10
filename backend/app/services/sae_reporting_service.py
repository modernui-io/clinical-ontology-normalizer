"""SAE Regulatory Reporting Service (CLINICAL-SAE).

Manages serious adverse event (SAE) regulatory reporting: intake, expedited
reporting (7-day/15-day), regulatory authority submission, MedWatch/CIOMS
form generation, causality assessment, narrative writing, and safety metrics.

Usage:
    from app.services.sae_reporting_service import get_sae_reporting_service

    svc = get_sae_reporting_service()
    reports = svc.list_sae_reports()
    metrics = svc.get_sae_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.sae_reporting import (
    CausalityAssessment,
    CausalityRecord,
    CausalityRecordCreate,
    CIOMSForm,
    MedWatchForm,
    RegulatoryAuthority,
    RegulatorySubmission,
    RegulatorySubmissionCreate,
    ReportingTimeline,
    ReportType,
    SAEMetrics,
    SAENarrative,
    SAEOutcome,
    SAEReport,
    SAEReportCreate,
    SAEReportUpdate,
    SAESeriousness,
    SAEStatus,
    TrialSafetySummary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Reporting timeline durations
TIMELINE_HOURS = {
    ReportingTimeline.SEVEN_DAY: 7 * 24,
    ReportingTimeline.FIFTEEN_DAY: 15 * 24,
    ReportingTimeline.THIRTY_DAY: 30 * 24,
}


def _determine_timeline(seriousness: SAESeriousness) -> ReportingTimeline:
    """Determine the reporting timeline based on seriousness criteria."""
    if seriousness == SAESeriousness.DEATH:
        return ReportingTimeline.SEVEN_DAY
    if seriousness == SAESeriousness.LIFE_THREATENING:
        return ReportingTimeline.SEVEN_DAY
    return ReportingTimeline.FIFTEEN_DAY


def _compute_deadline(awareness_date: datetime, timeline: ReportingTimeline) -> datetime:
    """Compute the reporting deadline from awareness date and timeline."""
    hours = TIMELINE_HOURS[timeline]
    return awareness_date + timedelta(hours=hours)


class SAEReportingService:
    """In-memory SAE Regulatory Reporting engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._reports: dict[str, SAEReport] = {}
        self._causality_records: dict[str, CausalityRecord] = {}
        self._regulatory_submissions: dict[str, RegulatorySubmission] = {}
        self._narratives: dict[str, SAENarrative] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic SAE reporting data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 10 SAE Reports across 3 trials ---

        # SAE-001: Aflibercept - Retinal detachment (EYLEA trial)
        # Submitted and acknowledged
        sae1_awareness = now - timedelta(days=60)
        sae1_timeline = ReportingTimeline.FIFTEEN_DAY
        sae1 = SAEReport(
            id="SAE-001",
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            subject_id="SUBJ-1001",
            report_type=ReportType.INITIAL,
            status=SAEStatus.ACKNOWLEDGED,
            seriousness=SAESeriousness.HOSPITALIZATION,
            outcome=SAEOutcome.RECOVERED,
            event_description="Patient developed acute retinal detachment in study eye requiring surgical repair. Hospitalized for 3 days. Event resolved with full visual recovery after vitrectomy.",
            event_term="Retinal detachment",
            study_drug="aflibercept",
            onset_date=now - timedelta(days=62),
            awareness_date=sae1_awareness,
            reporting_timeline=sae1_timeline,
            reporting_deadline=_compute_deadline(sae1_awareness, sae1_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=45),
        )

        # SAE-002: Aflibercept - Endophthalmitis (EYLEA trial)
        # Submitted, awaiting acknowledgment
        sae2_awareness = now - timedelta(days=30)
        sae2_timeline = ReportingTimeline.FIFTEEN_DAY
        sae2 = SAEReport(
            id="SAE-002",
            trial_id=EYLEA_TRIAL,
            site_id="SITE-102",
            subject_id="SUBJ-1042",
            report_type=ReportType.INITIAL,
            status=SAEStatus.SUBMITTED,
            seriousness=SAESeriousness.IMPORTANT_MEDICAL_EVENT,
            outcome=SAEOutcome.RECOVERING,
            event_description="Infectious endophthalmitis developed 48 hours post-intravitreal injection. Culture positive for Staphylococcus epidermidis. Treated with intravitreal antibiotics.",
            event_term="Endophthalmitis",
            study_drug="aflibercept",
            onset_date=now - timedelta(days=32),
            awareness_date=sae2_awareness,
            reporting_timeline=sae2_timeline,
            reporting_deadline=_compute_deadline(sae2_awareness, sae2_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=20),
        )

        # SAE-003: Dupilumab - Anaphylaxis (DUPIXENT trial)
        # 7-day expedited, submitted
        sae3_awareness = now - timedelta(days=45)
        sae3_timeline = ReportingTimeline.SEVEN_DAY
        sae3 = SAEReport(
            id="SAE-003",
            trial_id=DUPIXENT_TRIAL,
            site_id="SITE-103",
            subject_id="SUBJ-2015",
            report_type=ReportType.INITIAL,
            status=SAEStatus.SUBMITTED,
            seriousness=SAESeriousness.LIFE_THREATENING,
            outcome=SAEOutcome.RECOVERED,
            event_description="Anaphylactic reaction within 15 minutes of dupilumab subcutaneous injection. Presented with urticaria, angioedema, hypotension (BP 80/50), and bronchospasm. Treated with epinephrine, IV fluids, and corticosteroids in ED. Recovered within 6 hours.",
            event_term="Anaphylactic reaction",
            study_drug="dupilumab",
            onset_date=now - timedelta(days=46),
            awareness_date=sae3_awareness,
            reporting_timeline=sae3_timeline,
            reporting_deadline=_compute_deadline(sae3_awareness, sae3_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=45),
            updated_at=now - timedelta(days=38),
        )

        # SAE-004: Dupilumab - Severe eczema herpeticum (DUPIXENT trial)
        # In medical review
        sae4_awareness = now - timedelta(days=10)
        sae4_timeline = ReportingTimeline.FIFTEEN_DAY
        sae4 = SAEReport(
            id="SAE-004",
            trial_id=DUPIXENT_TRIAL,
            site_id="SITE-105",
            subject_id="SUBJ-2033",
            report_type=ReportType.INITIAL,
            status=SAEStatus.MEDICAL_REVIEW,
            seriousness=SAESeriousness.HOSPITALIZATION,
            outcome=SAEOutcome.RECOVERING,
            event_description="Severe disseminated eczema herpeticum requiring hospitalization for IV antiviral therapy. HSV-1 PCR positive. Extensive vesicular lesions covering 30% body surface area.",
            event_term="Eczema herpeticum",
            study_drug="dupilumab",
            onset_date=now - timedelta(days=12),
            awareness_date=sae4_awareness,
            reporting_timeline=sae4_timeline,
            reporting_deadline=_compute_deadline(sae4_awareness, sae4_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=8),
        )

        # SAE-005: Cemiplimab - Immune-related hepatitis (LIBTAYO trial)
        # Closed
        sae5_awareness = now - timedelta(days=90)
        sae5_timeline = ReportingTimeline.FIFTEEN_DAY
        sae5 = SAEReport(
            id="SAE-005",
            trial_id=LIBTAYO_TRIAL,
            site_id="SITE-106",
            subject_id="SUBJ-3008",
            report_type=ReportType.FINAL,
            status=SAEStatus.CLOSED,
            seriousness=SAESeriousness.HOSPITALIZATION,
            outcome=SAEOutcome.RECOVERED,
            event_description="Grade 3 immune-related hepatitis with ALT 15x ULN and AST 12x ULN. Study drug permanently discontinued. Treated with high-dose prednisone with taper over 8 weeks. Liver enzymes normalized.",
            event_term="Autoimmune hepatitis",
            study_drug="cemiplimab",
            onset_date=now - timedelta(days=95),
            awareness_date=sae5_awareness,
            reporting_timeline=sae5_timeline,
            reporting_deadline=_compute_deadline(sae5_awareness, sae5_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=90),
            updated_at=now - timedelta(days=30),
        )

        # SAE-006: Cemiplimab - Fatal pneumonitis (LIBTAYO trial)
        # 7-day, acknowledged
        sae6_awareness = now - timedelta(days=75)
        sae6_timeline = ReportingTimeline.SEVEN_DAY
        sae6 = SAEReport(
            id="SAE-006",
            trial_id=LIBTAYO_TRIAL,
            site_id="SITE-107",
            subject_id="SUBJ-3022",
            report_type=ReportType.FINAL,
            status=SAEStatus.ACKNOWLEDGED,
            seriousness=SAESeriousness.DEATH,
            outcome=SAEOutcome.FATAL,
            event_description="Grade 5 immune-related pneumonitis. Patient developed progressive dyspnea and hypoxia 8 weeks after cycle 4. CT showed bilateral ground-glass opacities. Despite high-dose corticosteroids, infliximab, and mechanical ventilation, patient expired on Day 72.",
            event_term="Pneumonitis",
            study_drug="cemiplimab",
            onset_date=now - timedelta(days=80),
            awareness_date=sae6_awareness,
            reporting_timeline=sae6_timeline,
            reporting_deadline=_compute_deadline(sae6_awareness, sae6_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=75),
            updated_at=now - timedelta(days=50),
        )

        # SAE-007: Cemiplimab - Immune-related colitis (LIBTAYO trial)
        # Draft, overdue
        sae7_awareness = now - timedelta(days=20)
        sae7_timeline = ReportingTimeline.FIFTEEN_DAY
        sae7 = SAEReport(
            id="SAE-007",
            trial_id=LIBTAYO_TRIAL,
            site_id="SITE-108",
            subject_id="SUBJ-3041",
            report_type=ReportType.INITIAL,
            status=SAEStatus.DRAFT,
            seriousness=SAESeriousness.HOSPITALIZATION,
            outcome=SAEOutcome.NOT_RECOVERED,
            event_description="Grade 3 immune-related colitis with bloody diarrhea (8-10 episodes/day). Colonoscopy confirmed severe mucosal inflammation. Study drug held. Initiated high-dose IV methylprednisolone.",
            event_term="Colitis",
            study_drug="cemiplimab",
            onset_date=now - timedelta(days=22),
            awareness_date=sae7_awareness,
            reporting_timeline=sae7_timeline,
            reporting_deadline=_compute_deadline(sae7_awareness, sae7_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=18),
        )

        # SAE-008: Aflibercept - Stroke (EYLEA trial)
        # 7-day, in medical review
        sae8_awareness = now - timedelta(days=5)
        sae8_timeline = ReportingTimeline.SEVEN_DAY
        sae8 = SAEReport(
            id="SAE-008",
            trial_id=EYLEA_TRIAL,
            site_id="SITE-104",
            subject_id="SUBJ-1078",
            report_type=ReportType.INITIAL,
            status=SAEStatus.MEDICAL_REVIEW,
            seriousness=SAESeriousness.LIFE_THREATENING,
            outcome=SAEOutcome.RECOVERING,
            event_description="Ischemic stroke (MCA territory) 10 days after intravitreal aflibercept injection. Patient presented with acute left hemiparesis and aphasia. MRI confirmed acute infarction. Treated with tPA within therapeutic window.",
            event_term="Cerebrovascular accident",
            study_drug="aflibercept",
            onset_date=now - timedelta(days=6),
            awareness_date=sae8_awareness,
            reporting_timeline=sae8_timeline,
            reporting_deadline=_compute_deadline(sae8_awareness, sae8_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=4),
        )

        # SAE-009: Dupilumab - Congenital anomaly report (DUPIXENT trial)
        # Draft
        sae9_awareness = now - timedelta(days=3)
        sae9_timeline = ReportingTimeline.FIFTEEN_DAY
        sae9 = SAEReport(
            id="SAE-009",
            trial_id=DUPIXENT_TRIAL,
            site_id="SITE-106",
            subject_id="SUBJ-2055",
            report_type=ReportType.INITIAL,
            status=SAEStatus.DRAFT,
            seriousness=SAESeriousness.CONGENITAL_ANOMALY,
            outcome=SAEOutcome.UNKNOWN,
            event_description="Pregnancy reported during trial participation. Ultrasound at 20 weeks gestation revealed ventricular septal defect in fetus. Patient had received 4 doses of dupilumab prior to pregnancy detection.",
            event_term="Ventricular septal defect",
            study_drug="dupilumab",
            onset_date=now - timedelta(days=5),
            awareness_date=sae9_awareness,
            reporting_timeline=sae9_timeline,
            reporting_deadline=_compute_deadline(sae9_awareness, sae9_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=2),
        )

        # SAE-010: Cemiplimab - Disability (LIBTAYO trial)
        # Submitted
        sae10_awareness = now - timedelta(days=40)
        sae10_timeline = ReportingTimeline.FIFTEEN_DAY
        sae10 = SAEReport(
            id="SAE-010",
            trial_id=LIBTAYO_TRIAL,
            site_id="SITE-105",
            subject_id="SUBJ-3055",
            report_type=ReportType.INITIAL,
            status=SAEStatus.SUBMITTED,
            seriousness=SAESeriousness.DISABILITY,
            outcome=SAEOutcome.NOT_RECOVERED,
            event_description="Immune-related peripheral neuropathy (Grade 3) with progressive bilateral lower extremity weakness. EMG/NCS consistent with axonal sensorimotor neuropathy. Patient now wheelchair-dependent.",
            event_term="Peripheral neuropathy",
            study_drug="cemiplimab",
            onset_date=now - timedelta(days=45),
            awareness_date=sae10_awareness,
            reporting_timeline=sae10_timeline,
            reporting_deadline=_compute_deadline(sae10_awareness, sae10_timeline),
            causality_records=[],
            regulatory_submissions=[],
            narrative=None,
            parent_report_id=None,
            created_at=now - timedelta(days=40),
            updated_at=now - timedelta(days=28),
        )

        for report in [sae1, sae2, sae3, sae4, sae5, sae6, sae7, sae8, sae9, sae10]:
            self._reports[report.id] = report

        # --- Causality Records ---
        causality_data = [
            {
                "id": "CR-001", "sae_report_id": "SAE-001", "assessor": "Investigator (Dr. Smith)",
                "assessment": CausalityAssessment.UNLIKELY_RELATED,
                "rationale": "Retinal detachment is a known complication of the underlying disease (diabetic retinopathy). Temporal relationship to study drug is coincidental.",
                "assessed_date": now - timedelta(days=58),
            },
            {
                "id": "CR-002", "sae_report_id": "SAE-001", "assessor": "Sponsor Medical Monitor",
                "assessment": CausalityAssessment.NOT_RELATED,
                "rationale": "No biological plausibility for aflibercept causing retinal detachment. Risk factor analysis indicates pre-existing tractional component.",
                "assessed_date": now - timedelta(days=55),
            },
            {
                "id": "CR-003", "sae_report_id": "SAE-002", "assessor": "Investigator (Dr. Patel)",
                "assessment": CausalityAssessment.POSSIBLY_RELATED,
                "rationale": "Endophthalmitis occurred 48 hours post-injection, which is within the established risk window for injection-related infections.",
                "assessed_date": now - timedelta(days=28),
            },
            {
                "id": "CR-004", "sae_report_id": "SAE-003", "assessor": "Investigator (Dr. Kim)",
                "assessment": CausalityAssessment.RELATED,
                "rationale": "Anaphylactic reaction occurred within minutes of dupilumab injection with clear temporal relationship and positive dechallenge.",
                "assessed_date": now - timedelta(days=44),
            },
            {
                "id": "CR-005", "sae_report_id": "SAE-003", "assessor": "Sponsor Medical Monitor",
                "assessment": CausalityAssessment.RELATED,
                "rationale": "Anaphylaxis is a known class effect of monoclonal antibodies. Temporal relationship and clinical presentation are consistent with drug-induced anaphylaxis.",
                "assessed_date": now - timedelta(days=42),
            },
            {
                "id": "CR-006", "sae_report_id": "SAE-005", "assessor": "Investigator (Dr. Chen)",
                "assessment": CausalityAssessment.RELATED,
                "rationale": "Immune-related hepatitis is a well-characterized adverse effect of PD-1 inhibitors. Onset timing and pattern consistent with checkpoint inhibitor-induced hepatotoxicity.",
                "assessed_date": now - timedelta(days=88),
            },
            {
                "id": "CR-007", "sae_report_id": "SAE-006", "assessor": "Investigator (Dr. Johnson)",
                "assessment": CausalityAssessment.RELATED,
                "rationale": "Fatal pneumonitis is a recognized serious risk of PD-1 blockade therapy. Onset after 4 cycles is consistent with published literature.",
                "assessed_date": now - timedelta(days=73),
            },
            {
                "id": "CR-008", "sae_report_id": "SAE-006", "assessor": "Sponsor Medical Monitor",
                "assessment": CausalityAssessment.RELATED,
                "rationale": "Pneumonitis pattern (bilateral GGO, timing post-cycle 4) is pathognomonic for immune checkpoint inhibitor pneumonitis. No alternative etiology identified.",
                "assessed_date": now - timedelta(days=70),
            },
            {
                "id": "CR-009", "sae_report_id": "SAE-008", "assessor": "Investigator (Dr. Williams)",
                "assessment": CausalityAssessment.POSSIBLY_RELATED,
                "rationale": "Anti-VEGF agents have a theoretical risk of arterial thromboembolic events. However, patient had pre-existing cardiovascular risk factors.",
                "assessed_date": now - timedelta(days=4),
            },
            {
                "id": "CR-010", "sae_report_id": "SAE-010", "assessor": "Investigator (Dr. Lee)",
                "assessment": CausalityAssessment.RELATED,
                "rationale": "Peripheral neuropathy is a recognized immune-related adverse event with PD-1 inhibitors. Progressive course and EMG findings consistent with drug-induced neuropathy.",
                "assessed_date": now - timedelta(days=38),
            },
        ]

        for cr_data in causality_data:
            cr = CausalityRecord(**cr_data)
            self._causality_records[cr.id] = cr

        # Attach causality records to reports
        for report_id, report in self._reports.items():
            crs = [c for c in self._causality_records.values() if c.sae_report_id == report_id]
            if crs:
                data = report.model_dump()
                data["causality_records"] = crs
                self._reports[report_id] = SAEReport(**data)

        # --- Regulatory Submissions ---
        submission_data = [
            {
                "id": "RS-001", "sae_report_id": "SAE-001", "authority": RegulatoryAuthority.FDA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=50),
                "acknowledgment_number": "FDA-2025-SAE-00421",
                "acknowledgment_date": now - timedelta(days=47),
            },
            {
                "id": "RS-002", "sae_report_id": "SAE-001", "authority": RegulatoryAuthority.EMA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=50),
                "acknowledgment_number": "EMA-SUSAR-2025-0198",
                "acknowledgment_date": now - timedelta(days=46),
            },
            {
                "id": "RS-003", "sae_report_id": "SAE-002", "authority": RegulatoryAuthority.FDA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=20),
                "acknowledgment_number": None, "acknowledgment_date": None,
            },
            {
                "id": "RS-004", "sae_report_id": "SAE-003", "authority": RegulatoryAuthority.FDA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=40),
                "acknowledgment_number": "FDA-2025-SAE-00534",
                "acknowledgment_date": now - timedelta(days=37),
            },
            {
                "id": "RS-005", "sae_report_id": "SAE-003", "authority": RegulatoryAuthority.HEALTH_CANADA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=40),
                "acknowledgment_number": "HC-SAE-2025-0087",
                "acknowledgment_date": now - timedelta(days=35),
            },
            {
                "id": "RS-006", "sae_report_id": "SAE-005", "authority": RegulatoryAuthority.FDA,
                "submission_type": ReportType.FINAL, "submitted_date": now - timedelta(days=35),
                "acknowledgment_number": "FDA-2025-SAE-00389",
                "acknowledgment_date": now - timedelta(days=32),
            },
            {
                "id": "RS-007", "sae_report_id": "SAE-005", "authority": RegulatoryAuthority.EMA,
                "submission_type": ReportType.FINAL, "submitted_date": now - timedelta(days=35),
                "acknowledgment_number": "EMA-SUSAR-2025-0167",
                "acknowledgment_date": now - timedelta(days=31),
            },
            {
                "id": "RS-008", "sae_report_id": "SAE-006", "authority": RegulatoryAuthority.FDA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=72),
                "acknowledgment_number": "FDA-2025-SAE-00356",
                "acknowledgment_date": now - timedelta(days=70),
            },
            {
                "id": "RS-009", "sae_report_id": "SAE-006", "authority": RegulatoryAuthority.EMA,
                "submission_type": ReportType.FINAL, "submitted_date": now - timedelta(days=55),
                "acknowledgment_number": "EMA-SUSAR-2025-0145",
                "acknowledgment_date": now - timedelta(days=52),
            },
            {
                "id": "RS-010", "sae_report_id": "SAE-006", "authority": RegulatoryAuthority.MHRA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=72),
                "acknowledgment_number": "MHRA-YC-2025-0034",
                "acknowledgment_date": now - timedelta(days=68),
            },
            {
                "id": "RS-011", "sae_report_id": "SAE-010", "authority": RegulatoryAuthority.FDA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=28),
                "acknowledgment_number": None, "acknowledgment_date": None,
            },
            {
                "id": "RS-012", "sae_report_id": "SAE-010", "authority": RegulatoryAuthority.PMDA,
                "submission_type": ReportType.INITIAL, "submitted_date": now - timedelta(days=28),
                "acknowledgment_number": "PMDA-SAE-2025-0012",
                "acknowledgment_date": now - timedelta(days=25),
            },
        ]

        for rs_data in submission_data:
            rs = RegulatorySubmission(**rs_data)
            self._regulatory_submissions[rs.id] = rs

        # Attach submissions to reports
        for report_id, report in self._reports.items():
            subs = [s for s in self._regulatory_submissions.values() if s.sae_report_id == report_id]
            if subs:
                data = report.model_dump()
                data["regulatory_submissions"] = subs
                self._reports[report_id] = SAEReport(**data)

        # --- Narratives ---
        narrative_data = [
            {
                "sae_report_id": "SAE-001",
                "initial_narrative": "A 67-year-old male subject (SUBJ-1001) enrolled in the aflibercept Phase III trial developed acute retinal detachment in the study eye on Day 45 of treatment. The patient presented with sudden onset of floaters and a curtain-like visual field defect. Fundoscopic examination confirmed rhegmatogenous retinal detachment. The patient underwent successful pars plana vitrectomy with gas tamponade and was hospitalized for 3 days. Visual acuity returned to baseline at 6-week follow-up.",
                "follow_up_narratives": [
                    "6-week follow-up: Visual acuity has returned to 20/40 (baseline 20/30). OCT shows attached retina with mild residual subretinal fluid. Patient has resumed study drug after ophthalmology clearance."
                ],
                "medical_review_notes": [
                    "Medical monitor review: Retinal detachment is a known complication of underlying diabetic retinopathy and not an expected effect of anti-VEGF therapy. Recommend classifying as not related to study drug."
                ],
            },
            {
                "sae_report_id": "SAE-003",
                "initial_narrative": "A 42-year-old female subject (SUBJ-2015) experienced anaphylactic reaction within 15 minutes of the 3rd dose of dupilumab 300mg SC. Symptoms included generalized urticaria, facial angioedema, hypotension (BP 80/50 mmHg), and audible wheezing. Emergency treatment was administered including IM epinephrine 0.3mg, IV normal saline bolus, IV diphenhydramine, and IV methylprednisolone. The patient was stabilized within 2 hours and observed in the ED for 6 hours before discharge. Study drug has been permanently discontinued.",
                "follow_up_narratives": [],
                "medical_review_notes": [
                    "Sponsor medical monitor: This event meets criteria for expedited 7-day reporting as life-threatening. Anaphylaxis to monoclonal antibodies is a recognized risk. Recommend updating the investigator brochure risk section.",
                    "Allergist consultation obtained: IgE-mediated hypersensitivity to dupilumab confirmed by skin prick testing."
                ],
            },
            {
                "sae_report_id": "SAE-005",
                "initial_narrative": "A 71-year-old male subject (SUBJ-3008) with advanced cutaneous squamous cell carcinoma developed immune-related hepatitis after cycle 6 of cemiplimab 350mg IV Q3W. Laboratory monitoring revealed ALT 750 U/L (15x ULN) and AST 600 U/L (12x ULN) with total bilirubin 2.1 mg/dL. Hepatitis panel negative for viral etiologies. Liver biopsy showed interface hepatitis with predominantly lymphocytic infiltrate consistent with immune-mediated injury.",
                "follow_up_narratives": [
                    "Week 4 update: ALT trending down to 120 U/L on prednisone 60mg daily taper. Bilirubin normalized.",
                    "Week 8 final: Complete normalization of liver enzymes. Prednisone tapered to 5mg daily. Study drug permanently discontinued per protocol."
                ],
                "medical_review_notes": [
                    "DSMB reviewed: Pattern consistent with immune checkpoint inhibitor hepatotoxicity. No signal above expected background rate for cemiplimab."
                ],
            },
            {
                "sae_report_id": "SAE-006",
                "initial_narrative": "A 68-year-old male subject (SUBJ-3022) with metastatic CSCC developed fatal immune-related pneumonitis 8 weeks after completing cycle 4 of cemiplimab 350mg IV Q3W. Initial presentation included progressive dyspnea (mMRC Grade 3), dry cough, and oxygen saturation of 85% on room air. CT chest showed extensive bilateral ground-glass opacities with interlobular septal thickening. Despite aggressive immunosuppression with methylprednisolone 2mg/kg, infliximab 5mg/kg, and mycophenolate mofetil, the patient progressed to respiratory failure requiring mechanical ventilation. The patient expired on study Day 72.",
                "follow_up_narratives": [
                    "Autopsy results: Diffuse alveolar damage with organizing pneumonia pattern. No evidence of infection. Findings consistent with severe immune-related pneumonitis."
                ],
                "medical_review_notes": [
                    "Sponsor safety team: Fatal pneumonitis is a known risk of PD-1 inhibitor therapy. Current incidence in the trial (1/45 = 2.2%) is within the expected range based on published data (1-3%).",
                    "DSMB emergency review: No recommendation to halt enrollment. Enhanced monitoring recommendations issued to all sites."
                ],
            },
        ]

        for n_data in narrative_data:
            narrative = SAENarrative(**n_data)
            self._narratives[n_data["sae_report_id"]] = narrative

        # Attach narratives to reports
        for report_id, report in self._reports.items():
            if report_id in self._narratives:
                data = report.model_dump()
                data["narrative"] = self._narratives[report_id]
                self._reports[report_id] = SAEReport(**data)

    # ------------------------------------------------------------------
    # SAE Report CRUD
    # ------------------------------------------------------------------

    def list_sae_reports(
        self,
        *,
        trial_id: str | None = None,
        status: SAEStatus | None = None,
        seriousness: SAESeriousness | None = None,
        study_drug: str | None = None,
    ) -> list[SAEReport]:
        """List SAE reports with optional filters."""
        with self._lock:
            result = list(self._reports.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        if seriousness is not None:
            result = [r for r in result if r.seriousness == seriousness]
        if study_drug is not None:
            result = [r for r in result if r.study_drug.lower() == study_drug.lower()]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_sae_report(self, report_id: str) -> SAEReport | None:
        """Get a single SAE report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def create_sae_report(self, payload: SAEReportCreate) -> SAEReport:
        """Create a new initial SAE report."""
        now = datetime.now(timezone.utc)
        report_id = f"SAE-{uuid4().hex[:8].upper()}"
        timeline = _determine_timeline(payload.seriousness)
        deadline = _compute_deadline(payload.awareness_date, timeline)

        narrative = SAENarrative(
            sae_report_id=report_id,
            initial_narrative=payload.initial_narrative,
            follow_up_narratives=[],
            medical_review_notes=[],
        )

        report = SAEReport(
            id=report_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            report_type=ReportType.INITIAL,
            status=SAEStatus.DRAFT,
            seriousness=payload.seriousness,
            outcome=payload.outcome,
            event_description=payload.event_description,
            event_term=payload.event_term,
            study_drug=payload.study_drug,
            onset_date=payload.onset_date,
            awareness_date=payload.awareness_date,
            reporting_timeline=timeline,
            reporting_deadline=deadline,
            causality_records=[],
            regulatory_submissions=[],
            narrative=narrative,
            parent_report_id=None,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._reports[report_id] = report
            self._narratives[report_id] = narrative
        logger.info("Created SAE report %s: %s", report_id, payload.event_term)
        return report

    def update_sae_report(self, report_id: str, payload: SAEReportUpdate) -> SAEReport | None:
        """Update an existing SAE report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = SAEReport(**data)
            self._reports[report_id] = updated
        return updated

    def delete_sae_report(self, report_id: str) -> bool:
        """Delete an SAE report. Returns True if deleted, False if not found."""
        with self._lock:
            if report_id in self._reports:
                del self._reports[report_id]
                self._narratives.pop(report_id, None)
                # Remove related causality records
                to_remove_cr = [
                    k for k, v in self._causality_records.items()
                    if v.sae_report_id == report_id
                ]
                for k in to_remove_cr:
                    del self._causality_records[k]
                # Remove related regulatory submissions
                to_remove_rs = [
                    k for k, v in self._regulatory_submissions.items()
                    if v.sae_report_id == report_id
                ]
                for k in to_remove_rs:
                    del self._regulatory_submissions[k]
                return True
            return False

    # ------------------------------------------------------------------
    # SAE Report Lifecycle
    # ------------------------------------------------------------------

    def submit_for_medical_review(self, report_id: str) -> SAEReport | None:
        """Transition report from draft to medical_review."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            if existing.status != SAEStatus.DRAFT:
                raise ValueError(
                    f"SAE report '{report_id}' cannot be submitted for medical review from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = SAEStatus.MEDICAL_REVIEW
            data["updated_at"] = now
            updated = SAEReport(**data)
            self._reports[report_id] = updated
        logger.info("SAE report %s submitted for medical review", report_id)
        return updated

    def approve_medical_review(self, report_id: str) -> SAEReport | None:
        """Approve medical review, transitioning to submitted status."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            if existing.status != SAEStatus.MEDICAL_REVIEW:
                raise ValueError(
                    f"SAE report '{report_id}' cannot be approved from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = SAEStatus.SUBMITTED
            data["updated_at"] = now
            updated = SAEReport(**data)
            self._reports[report_id] = updated
        logger.info("SAE report %s medical review approved, now submitted", report_id)
        return updated

    def submit_to_authority(
        self, report_id: str, payload: RegulatorySubmissionCreate
    ) -> RegulatorySubmission:
        """Create a regulatory submission for an SAE report."""
        sub_id = f"RS-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        with self._lock:
            report = self._reports.get(report_id)
            if report is None:
                raise ValueError(f"SAE report '{report_id}' not found")
            if report.status not in (SAEStatus.SUBMITTED, SAEStatus.ACKNOWLEDGED):
                raise ValueError(
                    f"SAE report '{report_id}' must be in submitted or acknowledged status to submit to authority, current status: '{report.status.value}'"
                )

            sub = RegulatorySubmission(
                id=sub_id,
                sae_report_id=report_id,
                authority=payload.authority,
                submission_type=payload.submission_type,
                submitted_date=payload.submitted_date,
                acknowledgment_number=payload.acknowledgment_number,
                acknowledgment_date=None,
            )
            self._regulatory_submissions[sub_id] = sub
            self._refresh_report_submissions(report_id)
            # Update report timestamp
            rpt = self._reports.get(report_id)
            if rpt:
                d = rpt.model_dump()
                d["updated_at"] = now
                self._reports[report_id] = SAEReport(**d)

        logger.info(
            "Submitted SAE %s to %s (submission %s)",
            report_id, payload.authority.value, sub_id,
        )
        return sub

    def record_acknowledgment(
        self,
        submission_id: str,
        acknowledgment_number: str,
        acknowledgment_date: datetime,
    ) -> RegulatorySubmission | None:
        """Record acknowledgment from a regulatory authority."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._regulatory_submissions.get(submission_id)
            if existing is None:
                return None

            data = existing.model_dump()
            data["acknowledgment_number"] = acknowledgment_number
            data["acknowledgment_date"] = acknowledgment_date
            updated = RegulatorySubmission(**data)
            self._regulatory_submissions[submission_id] = updated

            # If all submissions for this report are acknowledged, update report status
            report_id = existing.sae_report_id
            report = self._reports.get(report_id)
            if report and report.status == SAEStatus.SUBMITTED:
                all_subs = [
                    s for s in self._regulatory_submissions.values()
                    if s.sae_report_id == report_id
                ]
                if all_subs and all(s.acknowledgment_number is not None for s in all_subs):
                    rpt_data = report.model_dump()
                    rpt_data["status"] = SAEStatus.ACKNOWLEDGED
                    rpt_data["updated_at"] = now
                    self._reports[report_id] = SAEReport(**rpt_data)

            self._refresh_report_submissions(report_id)

        return updated

    def close_report(self, report_id: str) -> SAEReport | None:
        """Close an SAE report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            if existing.status not in (SAEStatus.ACKNOWLEDGED, SAEStatus.SUBMITTED):
                raise ValueError(
                    f"SAE report '{report_id}' cannot be closed from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = SAEStatus.CLOSED
            data["updated_at"] = now
            updated = SAEReport(**data)
            self._reports[report_id] = updated
        logger.info("Closed SAE report %s", report_id)
        return updated

    # ------------------------------------------------------------------
    # Follow-up and Final Reports
    # ------------------------------------------------------------------

    def create_follow_up_report(
        self, parent_report_id: str, payload: SAEReportCreate
    ) -> SAEReport:
        """Create a follow-up SAE report linked to a parent initial report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            parent = self._reports.get(parent_report_id)
            if parent is None:
                raise ValueError(f"Parent SAE report '{parent_report_id}' not found")

        report_id = f"SAE-{uuid4().hex[:8].upper()}"
        timeline = parent.reporting_timeline
        deadline = _compute_deadline(payload.awareness_date, timeline)

        narrative = SAENarrative(
            sae_report_id=report_id,
            initial_narrative=payload.initial_narrative,
            follow_up_narratives=[],
            medical_review_notes=[],
        )

        report = SAEReport(
            id=report_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            report_type=ReportType.FOLLOW_UP,
            status=SAEStatus.DRAFT,
            seriousness=payload.seriousness,
            outcome=payload.outcome,
            event_description=payload.event_description,
            event_term=payload.event_term,
            study_drug=payload.study_drug,
            onset_date=payload.onset_date,
            awareness_date=payload.awareness_date,
            reporting_timeline=timeline,
            reporting_deadline=deadline,
            causality_records=[],
            regulatory_submissions=[],
            narrative=narrative,
            parent_report_id=parent_report_id,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._reports[report_id] = report
            self._narratives[report_id] = narrative
        logger.info("Created follow-up SAE report %s for parent %s", report_id, parent_report_id)
        return report

    def create_final_report(
        self, parent_report_id: str, payload: SAEReportCreate
    ) -> SAEReport:
        """Create a final SAE report linked to a parent report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            parent = self._reports.get(parent_report_id)
            if parent is None:
                raise ValueError(f"Parent SAE report '{parent_report_id}' not found")

        report_id = f"SAE-{uuid4().hex[:8].upper()}"
        timeline = parent.reporting_timeline
        deadline = _compute_deadline(payload.awareness_date, timeline)

        narrative = SAENarrative(
            sae_report_id=report_id,
            initial_narrative=payload.initial_narrative,
            follow_up_narratives=[],
            medical_review_notes=[],
        )

        report = SAEReport(
            id=report_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            report_type=ReportType.FINAL,
            status=SAEStatus.DRAFT,
            seriousness=payload.seriousness,
            outcome=payload.outcome,
            event_description=payload.event_description,
            event_term=payload.event_term,
            study_drug=payload.study_drug,
            onset_date=payload.onset_date,
            awareness_date=payload.awareness_date,
            reporting_timeline=timeline,
            reporting_deadline=deadline,
            causality_records=[],
            regulatory_submissions=[],
            narrative=narrative,
            parent_report_id=parent_report_id,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._reports[report_id] = report
            self._narratives[report_id] = narrative
        logger.info("Created final SAE report %s for parent %s", report_id, parent_report_id)
        return report

    # ------------------------------------------------------------------
    # Causality Records
    # ------------------------------------------------------------------

    def list_causality_records(
        self, *, sae_report_id: str | None = None
    ) -> list[CausalityRecord]:
        """List causality records, optionally filtered by SAE report."""
        with self._lock:
            result = list(self._causality_records.values())
        if sae_report_id is not None:
            result = [c for c in result if c.sae_report_id == sae_report_id]
        return sorted(result, key=lambda c: c.assessed_date, reverse=True)

    def get_causality_record(self, record_id: str) -> CausalityRecord | None:
        """Get a single causality record."""
        with self._lock:
            return self._causality_records.get(record_id)

    def create_causality_record(
        self, report_id: str, payload: CausalityRecordCreate
    ) -> CausalityRecord:
        """Create a causality assessment record for an SAE report."""
        now = datetime.now(timezone.utc)
        record_id = f"CR-{uuid4().hex[:8].upper()}"
        with self._lock:
            report = self._reports.get(report_id)
            if report is None:
                raise ValueError(f"SAE report '{report_id}' not found")

            cr = CausalityRecord(
                id=record_id,
                sae_report_id=report_id,
                assessor=payload.assessor,
                assessment=payload.assessment,
                rationale=payload.rationale,
                assessed_date=now,
            )
            self._causality_records[record_id] = cr
            self._refresh_report_causality(report_id)

        logger.info("Created causality record %s for SAE %s", record_id, report_id)
        return cr

    # ------------------------------------------------------------------
    # Regulatory Submissions
    # ------------------------------------------------------------------

    def list_regulatory_submissions(
        self,
        *,
        sae_report_id: str | None = None,
        authority: RegulatoryAuthority | None = None,
    ) -> list[RegulatorySubmission]:
        """List regulatory submissions with optional filters."""
        with self._lock:
            result = list(self._regulatory_submissions.values())
        if sae_report_id is not None:
            result = [s for s in result if s.sae_report_id == sae_report_id]
        if authority is not None:
            result = [s for s in result if s.authority == authority]
        return sorted(result, key=lambda s: s.submitted_date, reverse=True)

    def get_regulatory_submission(self, submission_id: str) -> RegulatorySubmission | None:
        """Get a single regulatory submission."""
        with self._lock:
            return self._regulatory_submissions.get(submission_id)

    # ------------------------------------------------------------------
    # Reporting Deadlines
    # ------------------------------------------------------------------

    def check_reporting_deadlines(self) -> list[SAEReport]:
        """Return all reports approaching or past their deadline that are not yet submitted."""
        now = datetime.now(timezone.utc)
        with self._lock:
            result = []
            for report in self._reports.values():
                if report.status in (SAEStatus.DRAFT, SAEStatus.MEDICAL_REVIEW):
                    if report.reporting_deadline <= now + timedelta(hours=48):
                        result.append(report)
        return sorted(result, key=lambda r: r.reporting_deadline)

    def get_overdue_reports(self) -> list[SAEReport]:
        """Return all reports past their reporting deadline that have not been submitted."""
        now = datetime.now(timezone.utc)
        with self._lock:
            result = []
            for report in self._reports.values():
                if report.status in (SAEStatus.DRAFT, SAEStatus.MEDICAL_REVIEW):
                    if report.reporting_deadline < now:
                        result.append(report)
        return sorted(result, key=lambda r: r.reporting_deadline)

    # ------------------------------------------------------------------
    # Form Generation
    # ------------------------------------------------------------------

    def generate_medwatch_form(self, report_id: str) -> MedWatchForm | None:
        """Generate a MedWatch 3500A form from an SAE report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            report = self._reports.get(report_id)
            if report is None:
                return None

        seriousness_criteria = [report.seriousness.value]
        narrative_text = ""
        if report.narrative:
            narrative_text = report.narrative.initial_narrative

        return MedWatchForm(
            sae_report_id=report_id,
            form_version="3500A",
            patient_identifier=report.subject_id,
            patient_age=None,
            patient_sex=None,
            event_description=report.event_description,
            event_term=report.event_term,
            event_onset_date=report.onset_date,
            event_outcome=report.outcome.value,
            suspect_product=report.study_drug,
            dose_and_frequency="Per protocol",
            therapy_start_date=None,
            therapy_end_date=None,
            indication="Clinical trial",
            reporter_name="Sponsor Safety Team",
            reporter_type="pharmaceutical company",
            report_date=now,
            seriousness_criteria=seriousness_criteria,
            narrative_summary=narrative_text,
            generated_at=now,
        )

    def generate_cioms_form(self, report_id: str) -> CIOMSForm | None:
        """Generate a CIOMS I form from an SAE report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            report = self._reports.get(report_id)
            if report is None:
                return None

        seriousness_criteria = [report.seriousness.value]
        narrative_text = ""
        if report.narrative:
            narrative_text = report.narrative.initial_narrative

        return CIOMSForm(
            sae_report_id=report_id,
            form_version="CIOMS-I",
            reaction_onset_date=report.onset_date,
            reaction_end_date=None,
            reaction_description=report.event_description,
            reaction_outcome=report.outcome.value,
            seriousness_criteria=seriousness_criteria,
            suspect_drug=report.study_drug,
            daily_dose="Per protocol",
            route_of_administration="Per protocol",
            indication="Clinical trial",
            therapy_dates="Per protocol schedule",
            dechallenge=None,
            rechallenge=None,
            concomitant_medications=[],
            patient_initials=report.subject_id[:4],
            study_number=report.trial_id,
            reporter_country="US",
            date_of_report=now,
            sender_organization="Regeneron Pharmaceuticals",
            narrative_summary=narrative_text,
            generated_at=now,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_sae_metrics(self) -> SAEMetrics:
        """Compute aggregated SAE metrics across all trials."""
        now = datetime.now(timezone.utc)
        with self._lock:
            reports = list(self._reports.values())
            submissions = list(self._regulatory_submissions.values())
            causality_records = list(self._causality_records.values())

        by_seriousness: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_causality: dict[str, int] = {}
        reporting_times: list[float] = []
        overdue = 0

        for report in reports:
            by_seriousness[report.seriousness.value] = by_seriousness.get(report.seriousness.value, 0) + 1
            by_status[report.status.value] = by_status.get(report.status.value, 0) + 1

            if report.status in (SAEStatus.DRAFT, SAEStatus.MEDICAL_REVIEW):
                if report.reporting_deadline < now:
                    overdue += 1

            # Compute reporting time for submitted/acknowledged/closed
            if report.status in (SAEStatus.SUBMITTED, SAEStatus.ACKNOWLEDGED, SAEStatus.CLOSED):
                report_subs = [s for s in submissions if s.sae_report_id == report.id]
                if report_subs:
                    earliest_sub = min(report_subs, key=lambda s: s.submitted_date)
                    hours_diff = (earliest_sub.submitted_date - report.awareness_date).total_seconds() / 3600
                    reporting_times.append(hours_diff)

        for cr in causality_records:
            by_causality[cr.assessment.value] = by_causality.get(cr.assessment.value, 0) + 1

        avg_time = round(sum(reporting_times) / max(1, len(reporting_times)), 1) if reporting_times else 0.0

        submissions_by_authority: dict[str, int] = {}
        for sub in submissions:
            submissions_by_authority[sub.authority.value] = submissions_by_authority.get(sub.authority.value, 0) + 1

        return SAEMetrics(
            total_saes=len(reports),
            by_seriousness=by_seriousness,
            by_causality=by_causality,
            by_status=by_status,
            avg_reporting_time_hours=avg_time,
            overdue_reports=overdue,
            total_submissions=len(submissions),
            submissions_by_authority=submissions_by_authority,
        )

    def get_trial_safety_summary(self, trial_id: str) -> TrialSafetySummary:
        """Get safety summary for a specific trial."""
        now = datetime.now(timezone.utc)
        with self._lock:
            reports = [r for r in self._reports.values() if r.trial_id == trial_id]

        if not reports:
            return TrialSafetySummary(
                trial_id=trial_id,
                total_saes=0,
                by_seriousness={},
                by_outcome={},
                by_status={},
                overdue_reports=0,
                recent_saes=[],
            )

        by_seriousness: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_status: dict[str, int] = {}
        overdue = 0

        for report in reports:
            by_seriousness[report.seriousness.value] = by_seriousness.get(report.seriousness.value, 0) + 1
            by_outcome[report.outcome.value] = by_outcome.get(report.outcome.value, 0) + 1
            by_status[report.status.value] = by_status.get(report.status.value, 0) + 1

            if report.status in (SAEStatus.DRAFT, SAEStatus.MEDICAL_REVIEW):
                if report.reporting_deadline < now:
                    overdue += 1

        sorted_reports = sorted(reports, key=lambda r: r.created_at, reverse=True)

        return TrialSafetySummary(
            trial_id=trial_id,
            total_saes=len(reports),
            by_seriousness=by_seriousness,
            by_outcome=by_outcome,
            by_status=by_status,
            overdue_reports=overdue,
            recent_saes=sorted_reports[:5],
        )

    # ------------------------------------------------------------------
    # Narrative Management
    # ------------------------------------------------------------------

    def get_narrative(self, report_id: str) -> SAENarrative | None:
        """Get narrative for an SAE report."""
        with self._lock:
            return self._narratives.get(report_id)

    def add_follow_up_narrative(self, report_id: str, text: str) -> SAENarrative | None:
        """Add a follow-up narrative to an SAE report."""
        with self._lock:
            narrative = self._narratives.get(report_id)
            if narrative is None:
                return None
            data = narrative.model_dump()
            data["follow_up_narratives"].append(text)
            updated = SAENarrative(**data)
            self._narratives[report_id] = updated

            # Refresh narrative on report
            report = self._reports.get(report_id)
            if report:
                rpt_data = report.model_dump()
                rpt_data["narrative"] = updated
                rpt_data["updated_at"] = datetime.now(timezone.utc)
                self._reports[report_id] = SAEReport(**rpt_data)

        return updated

    def add_medical_review_note(self, report_id: str, note: str) -> SAENarrative | None:
        """Add a medical review note to an SAE narrative."""
        with self._lock:
            narrative = self._narratives.get(report_id)
            if narrative is None:
                return None
            data = narrative.model_dump()
            data["medical_review_notes"].append(note)
            updated = SAENarrative(**data)
            self._narratives[report_id] = updated

            # Refresh narrative on report
            report = self._reports.get(report_id)
            if report:
                rpt_data = report.model_dump()
                rpt_data["narrative"] = updated
                rpt_data["updated_at"] = datetime.now(timezone.utc)
                self._reports[report_id] = SAEReport(**rpt_data)

        return updated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_report_submissions(self, report_id: str) -> None:
        """Refresh embedded regulatory submissions on a report. Must hold _lock."""
        report = self._reports.get(report_id)
        if report is None:
            return
        subs = [s for s in self._regulatory_submissions.values() if s.sae_report_id == report_id]
        data = report.model_dump()
        data["regulatory_submissions"] = subs
        self._reports[report_id] = SAEReport(**data)

    def _refresh_report_causality(self, report_id: str) -> None:
        """Refresh embedded causality records on a report. Must hold _lock."""
        report = self._reports.get(report_id)
        if report is None:
            return
        crs = [c for c in self._causality_records.values() if c.sae_report_id == report_id]
        data = report.model_dump()
        data["causality_records"] = crs
        self._reports[report_id] = SAEReport(**data)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SAEReportingService | None = None
_instance_lock = threading.Lock()


def get_sae_reporting_service() -> SAEReportingService:
    """Return the singleton SAEReportingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SAEReportingService()
    return _instance


def reset_sae_reporting_service() -> SAEReportingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SAEReportingService()
    return _instance
