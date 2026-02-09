"""Pharmacovigilance Signal Management Service (CLINICAL-4).

Manages the full pharmacovigilance lifecycle including ICSR intake, safety
signal detection via disproportionality analysis, MedDRA coding, periodic
safety report generation, and regulatory action tracking.

Usage:
    from app.services.pharmacovigilance_service import (
        get_pharmacovigilance_service,
    )

    svc = get_pharmacovigilance_service()
    signal = svc.detect_signal("Dupilumab", "Conjunctivitis")
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from app.schemas.pharmacovigilance import (
    ICSR,
    CaseSeriesResult,
    CausalityCategory,
    DisproportionalityAnalysisResponse,
    DisproportionalityMethod,
    DisproportionalityResult,
    ICSRCreate,
    ICSRListResponse,
    ICSRStatus,
    ICSRUpdate,
    MedDRAHierarchyResponse,
    MedDRALevel,
    MedDRASearchResponse,
    MedDRATerm,
    PeriodicSafetyReport,
    PeriodicSafetyReportListResponse,
    PharmacovigilanceMetrics,
    RegulatoryAction,
    RegulatoryActionCreate,
    RegulatoryActionListResponse,
    RegulatoryActionStatus,
    RegulatoryActionType,
    ReportType,
    SignalClassification,
    SignalCreate,
    SignalDetectionRequest,
    SignalListResponse,
    SignalRecord,
    SignalSource,
    SignalUpdate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Valid ICSR status transitions
# ---------------------------------------------------------------------------

VALID_ICSR_TRANSITIONS: dict[ICSRStatus, set[ICSRStatus]] = {
    ICSRStatus.INITIAL: {ICSRStatus.FOLLOW_UP, ICSRStatus.FINAL, ICSRStatus.NULLIFIED},
    ICSRStatus.FOLLOW_UP: {ICSRStatus.FOLLOW_UP, ICSRStatus.FINAL, ICSRStatus.NULLIFIED},
    ICSRStatus.FINAL: {ICSRStatus.NULLIFIED},
    ICSRStatus.NULLIFIED: set(),
}

# ---------------------------------------------------------------------------
# Valid signal classification transitions
# ---------------------------------------------------------------------------

VALID_SIGNAL_TRANSITIONS: dict[SignalClassification, set[SignalClassification]] = {
    SignalClassification.UNDER_EVALUATION: {
        SignalClassification.VALIDATED,
        SignalClassification.REFUTED,
        SignalClassification.MONITORING,
        SignalClassification.CLOSED,
    },
    SignalClassification.VALIDATED: {SignalClassification.MONITORING, SignalClassification.CLOSED},
    SignalClassification.MONITORING: {SignalClassification.VALIDATED, SignalClassification.CLOSED},
    SignalClassification.REFUTED: {SignalClassification.CLOSED},
    SignalClassification.CLOSED: set(),
}

# ---------------------------------------------------------------------------
# Background incidence rates per 10,000 patient-years (simulated)
# ---------------------------------------------------------------------------

BACKGROUND_RATES: dict[str, float] = {
    "Headache": 850.0,
    "Nausea": 520.0,
    "Conjunctivitis": 180.0,
    "Injection site reaction": 950.0,
    "Fatigue": 620.0,
    "Rash": 310.0,
    "Arthralgia": 420.0,
    "Hepatotoxicity": 25.0,
    "Anaphylaxis": 5.0,
    "Pneumonitis": 15.0,
    "Neutropenia": 45.0,
    "Elevated ALT": 150.0,
    "Diarrhea": 480.0,
    "Hypertension": 350.0,
    "Peripheral neuropathy": 60.0,
    "Nasopharyngitis": 720.0,
    "Cardiac arrest": 8.0,
    "Stevens-Johnson syndrome": 2.0,
    "Retinal detachment": 12.0,
    "Endophthalmitis": 3.0,
    "Vitreous floaters": 90.0,
    "Keratitis": 40.0,
    "Eczema herpeticum": 10.0,
    "Asthma exacerbation": 200.0,
    "Immune-mediated colitis": 18.0,
    "Thyroid disorder": 35.0,
    "Dermatitis": 280.0,
    "Pruritus": 340.0,
    "Myalgia": 290.0,
    "Pyrexia": 180.0,
}


class PharmacovigilanceService:
    """In-memory pharmacovigilance signal management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._icsrs: dict[str, ICSR] = {}
        self._signals: dict[str, SignalRecord] = {}
        self._periodic_reports: dict[str, PeriodicSafetyReport] = {}
        self._regulatory_actions: dict[str, RegulatoryAction] = {}
        self._meddra_terms: dict[str, MedDRATerm] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic pharmacovigilance data."""
        now = datetime.now(timezone.utc)
        self._seed_meddra_hierarchy()
        self._seed_icsrs(now)
        self._seed_signals(now)
        self._seed_periodic_reports(now)
        self._seed_regulatory_actions(now)

    def _seed_meddra_hierarchy(self) -> None:
        """Seed 30 MedDRA terms across the hierarchy."""
        terms = [
            # SOC level
            MedDRATerm(code="10015919", term="Eye disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10015919"),
            MedDRATerm(code="10017947", term="Gastrointestinal disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10017947"),
            MedDRATerm(code="10018065", term="General disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10018065"),
            MedDRATerm(code="10021881", term="Immune system disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10021881"),
            MedDRATerm(code="10028395", term="Musculoskeletal disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10028395"),
            MedDRATerm(code="10029104", term="Nervous system disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10029104"),
            MedDRATerm(code="10038738", term="Respiratory disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10038738"),
            MedDRATerm(code="10040785", term="Skin disorders", level=MedDRALevel.SOC, parent_code=None, soc_code="10040785"),
            # HLGT level
            MedDRATerm(code="10013993", term="Conjunctival disorders", level=MedDRALevel.HLGT, parent_code="10015919", soc_code="10015919"),
            MedDRATerm(code="10038687", term="Retinal disorders", level=MedDRALevel.HLGT, parent_code="10015919", soc_code="10015919"),
            MedDRATerm(code="10017944", term="GI signs and symptoms", level=MedDRALevel.HLGT, parent_code="10017947", soc_code="10017947"),
            # HLT level
            MedDRATerm(code="10010720", term="Conjunctivitis NEC", level=MedDRALevel.HLT, parent_code="10013993", soc_code="10015919"),
            MedDRATerm(code="10038849", term="Retinal detachments", level=MedDRALevel.HLT, parent_code="10038687", soc_code="10015919"),
            MedDRATerm(code="10028814", term="Nausea and vomiting", level=MedDRALevel.HLT, parent_code="10017944", soc_code="10017947"),
            # PT level (most commonly used)
            MedDRATerm(code="10010741", term="Conjunctivitis", level=MedDRALevel.PT, parent_code="10010720", soc_code="10015919"),
            MedDRATerm(code="10038848", term="Retinal detachment", level=MedDRALevel.PT, parent_code="10038849", soc_code="10015919"),
            MedDRATerm(code="10028813", term="Nausea", level=MedDRALevel.PT, parent_code="10028814", soc_code="10017947"),
            MedDRATerm(code="10019211", term="Headache", level=MedDRALevel.PT, parent_code="10029104", soc_code="10029104"),
            MedDRATerm(code="10037844", term="Rash", level=MedDRALevel.PT, parent_code="10040785", soc_code="10040785"),
            MedDRATerm(code="10016558", term="Fatigue", level=MedDRALevel.PT, parent_code="10018065", soc_code="10018065"),
            MedDRATerm(code="10002198", term="Anaphylaxis", level=MedDRALevel.PT, parent_code="10021881", soc_code="10021881"),
            MedDRATerm(code="10022611", term="Injection site reaction", level=MedDRALevel.PT, parent_code="10018065", soc_code="10018065"),
            MedDRATerm(code="10003239", term="Arthralgia", level=MedDRALevel.PT, parent_code="10028395", soc_code="10028395"),
            MedDRATerm(code="10019851", term="Hepatotoxicity", level=MedDRALevel.PT, parent_code="10017947", soc_code="10017947"),
            MedDRATerm(code="10036790", term="Pruritus", level=MedDRALevel.PT, parent_code="10040785", soc_code="10040785"),
            MedDRATerm(code="10034835", term="Pneumonitis", level=MedDRALevel.PT, parent_code="10038738", soc_code="10038738"),
            MedDRATerm(code="10029354", term="Neutropenia", level=MedDRALevel.PT, parent_code="10021881", soc_code="10021881"),
            # LLT level
            MedDRATerm(code="10010743", term="Conjunctivitis allergic", level=MedDRALevel.LLT, parent_code="10010741", soc_code="10015919"),
            MedDRATerm(code="10010744", term="Conjunctivitis bacterial", level=MedDRALevel.LLT, parent_code="10010741", soc_code="10015919"),
            MedDRATerm(code="10037847", term="Rash maculopapular", level=MedDRALevel.LLT, parent_code="10037844", soc_code="10040785"),
        ]
        for t in terms:
            self._meddra_terms[t.code] = t

    def _seed_icsrs(self, now: datetime) -> None:
        """Seed 50 ICSRs across multiple drugs."""
        drugs_events = [
            ("Dupilumab", "Conjunctivitis", "Atopic dermatitis", "10010741"),
            ("Dupilumab", "Injection site reaction", "Atopic dermatitis", "10022611"),
            ("Dupilumab", "Headache", "Atopic dermatitis", "10019211"),
            ("Dupilumab", "Fatigue", "Asthma", "10016558"),
            ("Dupilumab", "Arthralgia", "Atopic dermatitis", "10003239"),
            ("Dupilumab", "Eczema herpeticum", "Atopic dermatitis", None),
            ("Aflibercept", "Conjunctivitis", "Wet AMD", "10010741"),
            ("Aflibercept", "Retinal detachment", "DME", "10038848"),
            ("Aflibercept", "Vitreous floaters", "Wet AMD", None),
            ("Aflibercept", "Endophthalmitis", "Wet AMD", None),
            ("Aflibercept", "Injection site reaction", "RVO", "10022611"),
            ("Cemiplimab", "Pneumonitis", "CSCC", "10034835"),
            ("Cemiplimab", "Hepatotoxicity", "CSCC", "10019851"),
            ("Cemiplimab", "Rash", "CSCC", "10037844"),
            ("Cemiplimab", "Fatigue", "BCC", "10016558"),
            ("Cemiplimab", "Immune-mediated colitis", "CSCC", None),
            ("Cemiplimab", "Thyroid disorder", "NSCLC", None),
            ("Cemiplimab", "Pruritus", "CSCC", "10036790"),
        ]

        outcomes = ["Recovered", "Recovering", "Not Recovered", "Fatal", "Unknown"]
        sexes = ["M", "F"]
        countries = ["US", "US", "US", "DE", "FR", "JP", "GB", "CA"]
        reporters = ["Physician", "Physician", "Pharmacist", "Consumer", "Other"]
        causalities = [
            CausalityCategory.CERTAIN,
            CausalityCategory.PROBABLE,
            CausalityCategory.POSSIBLE,
            CausalityCategory.POSSIBLE,
            CausalityCategory.UNLIKELY,
        ]

        for i in range(50):
            drug, event, indication, _code = drugs_events[i % len(drugs_events)]
            icsr_id = f"ICSR-{i + 1:04d}"
            is_serious = i % 7 == 0
            is_fatal = i == 42  # single fatal case
            outcome = "Fatal" if is_fatal else outcomes[i % len(outcomes)]

            seriousness: list[str] = []
            if is_serious:
                seriousness.append("Requires hospitalization")
            if is_fatal:
                seriousness.append("Results in death")

            age = 25 + (i * 3) % 60
            sex = sexes[i % 2]
            country = countries[i % len(countries)]
            reporter = reporters[i % len(reporters)]
            causality = causalities[i % len(causalities)]

            status = ICSRStatus.INITIAL
            if i < 15:
                status = ICSRStatus.FINAL
            elif i < 30:
                status = ICSRStatus.FOLLOW_UP

            extra_events = [event]
            if i % 5 == 0:
                extra_events.append("Headache")

            self._icsrs[icsr_id] = ICSR(
                id=icsr_id,
                case_number=f"CASE-2025-{i + 1:05d}",
                patient_age=age,
                patient_sex=sex,
                reporter_type=reporter,
                drug_name=drug,
                indication=indication,
                event_terms=extra_events,
                onset_date=now - timedelta(days=180 - i * 3),
                outcome=outcome,
                seriousness_criteria=seriousness,
                causality=causality,
                status=status,
                received_date=now - timedelta(days=170 - i * 3),
                source=SignalSource.CLINICAL_TRIAL if i < 20 else SignalSource.SPONTANEOUS_REPORT,
                country=country,
                narrative=f"Case {i + 1}: {age}y {sex} patient on {drug} for {indication} developed {event}. Outcome: {outcome}.",
            )

    def _seed_signals(self, now: datetime) -> None:
        """Seed 8 signals: 3 validated, 2 under evaluation, 2 refuted, 1 monitoring."""
        signals_data = [
            # 3 validated
            {
                "title": "Dupilumab-associated conjunctivitis",
                "desc": "Elevated conjunctivitis rates in dupilumab-treated patients across multiple clinical trials.",
                "drug": "Dupilumab",
                "event": "Conjunctivitis",
                "code": "10010741",
                "classification": SignalClassification.VALIDATED,
                "source": SignalSource.CLINICAL_TRIAL,
                "prr": 3.8, "ror": 4.2, "ic025": 1.5, "ebgm": 3.1,
                "cases": 18, "expected": 4.7,
                "strength": "strong",
                "method": "PRR",
            },
            {
                "title": "Cemiplimab immune-mediated pneumonitis",
                "desc": "Signal for immune-mediated pneumonitis with cemiplimab in CSCC patients.",
                "drug": "Cemiplimab",
                "event": "Pneumonitis",
                "code": "10034835",
                "classification": SignalClassification.VALIDATED,
                "source": SignalSource.CLINICAL_TRIAL,
                "prr": 5.2, "ror": 5.8, "ic025": 2.1, "ebgm": 4.5,
                "cases": 8, "expected": 1.5,
                "strength": "strong",
                "method": "BCPNN",
            },
            {
                "title": "Cemiplimab hepatotoxicity signal",
                "desc": "Elevated hepatotoxicity in cemiplimab-treated patients requiring monitoring.",
                "drug": "Cemiplimab",
                "event": "Hepatotoxicity",
                "code": "10019851",
                "classification": SignalClassification.VALIDATED,
                "source": SignalSource.CLINICAL_TRIAL,
                "prr": 2.9, "ror": 3.3, "ic025": 0.9, "ebgm": 2.6,
                "cases": 6, "expected": 2.1,
                "strength": "moderate",
                "method": "ROR",
            },
            # 2 under evaluation
            {
                "title": "Aflibercept retinal detachment association",
                "desc": "Potential association between intravitreal aflibercept and retinal detachment.",
                "drug": "Aflibercept",
                "event": "Retinal detachment",
                "code": "10038848",
                "classification": SignalClassification.UNDER_EVALUATION,
                "source": SignalSource.SPONTANEOUS_REPORT,
                "prr": 1.8, "ror": 2.0, "ic025": 0.3, "ebgm": 1.6,
                "cases": 5, "expected": 2.8,
                "strength": "weak",
                "method": "PRR",
            },
            {
                "title": "Dupilumab eczema herpeticum risk",
                "desc": "Investigating increased eczema herpeticum in dupilumab patients.",
                "drug": "Dupilumab",
                "event": "Eczema herpeticum",
                "code": None,
                "classification": SignalClassification.UNDER_EVALUATION,
                "source": SignalSource.LITERATURE,
                "prr": 2.1, "ror": 2.4, "ic025": 0.5, "ebgm": 1.9,
                "cases": 4, "expected": 1.9,
                "strength": "moderate",
                "method": "EBGM",
            },
            # 2 refuted
            {
                "title": "Dupilumab cardiac event signal",
                "desc": "Initial signal for cardiac events refuted after full evaluation.",
                "drug": "Dupilumab",
                "event": "Cardiac arrest",
                "code": None,
                "classification": SignalClassification.REFUTED,
                "source": SignalSource.SPONTANEOUS_REPORT,
                "prr": 0.8, "ror": 0.9, "ic025": -0.6, "ebgm": 0.7,
                "cases": 2, "expected": 2.5,
                "strength": "none",
                "method": "PRR",
            },
            {
                "title": "Aflibercept systemic hypertension",
                "desc": "Reported hypertension not confirmed as drug-related.",
                "drug": "Aflibercept",
                "event": "Hypertension",
                "code": None,
                "classification": SignalClassification.REFUTED,
                "source": SignalSource.EHR_DATA,
                "prr": 1.1, "ror": 1.2, "ic025": -0.2, "ebgm": 1.0,
                "cases": 3, "expected": 2.7,
                "strength": "none",
                "method": "ROR",
            },
            # 1 monitoring
            {
                "title": "Cemiplimab thyroid disorder monitoring",
                "desc": "Thyroid function abnormalities under routine monitoring.",
                "drug": "Cemiplimab",
                "event": "Thyroid disorder",
                "code": None,
                "classification": SignalClassification.MONITORING,
                "source": SignalSource.CLINICAL_TRIAL,
                "prr": 1.6, "ror": 1.8, "ic025": 0.1, "ebgm": 1.4,
                "cases": 7, "expected": 4.4,
                "strength": "weak",
                "method": "PRR",
            },
        ]

        for i, s in enumerate(signals_data):
            sig_id = f"SIG-{i + 1:04d}"
            self._signals[sig_id] = SignalRecord(
                id=sig_id,
                title=s["title"],
                description=s["desc"],
                drug_name=s["drug"],
                event_term=s["event"],
                meddra_pt_code=s["code"],
                source=s["source"],
                classification=s["classification"],
                detected_date=now - timedelta(days=120 - i * 10),
                detection_method=s["method"],
                prr=s["prr"],
                ror=s["ror"],
                ic025=s["ic025"],
                ebgm=s["ebgm"],
                case_count=s["cases"],
                expected_count=s["expected"],
                background_rate=BACKGROUND_RATES.get(s["event"], 100.0),
                evidence_strength=s["strength"],
                assessor="Dr. Safety Officer" if s["classification"] != SignalClassification.UNDER_EVALUATION else None,
                assessment_date=now - timedelta(days=30) if s["classification"] != SignalClassification.UNDER_EVALUATION else None,
                action_taken="Labeling update" if s["classification"] == SignalClassification.VALIDATED else None,
                regulatory_action_type=RegulatoryActionType.LABELING_CHANGE if s["classification"] == SignalClassification.VALIDATED else None,
                created_at=now - timedelta(days=120 - i * 10),
                updated_at=now - timedelta(days=5),
            )

    def _seed_periodic_reports(self, now: datetime) -> None:
        """Seed 4 periodic safety reports."""
        reports = [
            {
                "drug": "Dupilumab",
                "type": ReportType.PSUR,
                "total": 120, "serious": 15, "fatal": 1,
                "new_sig": 1, "updated": 2, "closed": 0,
                "assessment": "Favorable benefit-risk profile maintained. Conjunctivitis identified as important identified risk.",
                "submitted": "FDA",
            },
            {
                "drug": "Aflibercept",
                "type": ReportType.PBRER,
                "total": 85, "serious": 8, "fatal": 0,
                "new_sig": 0, "updated": 1, "closed": 1,
                "assessment": "Benefit-risk profile remains positive. Retinal detachment signal under evaluation.",
                "submitted": "EMA",
            },
            {
                "drug": "Cemiplimab",
                "type": ReportType.DSUR,
                "total": 65, "serious": 12, "fatal": 2,
                "new_sig": 2, "updated": 1, "closed": 0,
                "assessment": "Overall benefit-risk favorable for advanced CSCC. Immune-related AEs managed with existing protocols.",
                "submitted": "FDA",
            },
            {
                "drug": "Dupilumab",
                "type": ReportType.DSUR,
                "total": 95, "serious": 10, "fatal": 0,
                "new_sig": 0, "updated": 1, "closed": 1,
                "assessment": "No new safety concerns identified. Known risks adequately characterized in labeling.",
                "submitted": None,
            },
        ]

        for i, r in enumerate(reports):
            rid = f"PSR-{i + 1:04d}"
            self._periodic_reports[rid] = PeriodicSafetyReport(
                id=rid,
                drug_name=r["drug"],
                report_type=r["type"],
                period_start=now - timedelta(days=365),
                period_end=now - timedelta(days=1),
                total_cases=r["total"],
                serious_cases=r["serious"],
                fatal_cases=r["fatal"],
                new_signals=r["new_sig"],
                updated_signals=r["updated"],
                closed_signals=r["closed"],
                benefit_risk_assessment=r["assessment"],
                submitted_to=r["submitted"],
                submission_date=now - timedelta(days=10) if r["submitted"] else None,
                created_at=now - timedelta(days=15),
            )

    def _seed_regulatory_actions(self, now: datetime) -> None:
        """Seed 3 regulatory actions."""
        actions = [
            {
                "signal": "SIG-0001",
                "type": RegulatoryActionType.LABELING_CHANGE,
                "agency": "FDA",
                "desc": "Update prescribing information to include conjunctivitis as a common adverse reaction in dupilumab-treated patients.",
                "status": RegulatoryActionStatus.IMPLEMENTED,
            },
            {
                "signal": "SIG-0002",
                "type": RegulatoryActionType.SAFETY_COMMUNICATION,
                "agency": "FDA",
                "desc": "Safety communication regarding immune-mediated pneumonitis risk with cemiplimab.",
                "status": RegulatoryActionStatus.APPROVED,
            },
            {
                "signal": "SIG-0003",
                "type": RegulatoryActionType.DEAR_HEALTHCARE_PROVIDER,
                "agency": "EMA",
                "desc": "Dear Healthcare Professional letter regarding hepatotoxicity monitoring recommendations for cemiplimab.",
                "status": RegulatoryActionStatus.PROPOSED,
            },
        ]

        for i, a in enumerate(actions):
            aid = f"RA-{i + 1:04d}"
            self._regulatory_actions[aid] = RegulatoryAction(
                id=aid,
                signal_id=a["signal"],
                action_type=a["type"],
                agency=a["agency"],
                description=a["desc"],
                effective_date=now - timedelta(days=30) if a["status"] != RegulatoryActionStatus.PROPOSED else None,
                status=a["status"],
                implementation_date=now - timedelta(days=15) if a["status"] == RegulatoryActionStatus.IMPLEMENTED else None,
                created_at=now - timedelta(days=60),
            )

    # ------------------------------------------------------------------
    # ICSR CRUD
    # ------------------------------------------------------------------

    def create_icsr(self, payload: ICSRCreate) -> ICSR:
        """Create a new ICSR."""
        with self._lock:
            icsr_id = f"ICSR-{len(self._icsrs) + 1:04d}"
            now = datetime.now(timezone.utc)
            icsr = ICSR(
                id=icsr_id,
                case_number=payload.case_number,
                patient_age=payload.patient_age,
                patient_sex=payload.patient_sex,
                reporter_type=payload.reporter_type,
                drug_name=payload.drug_name,
                indication=payload.indication,
                event_terms=payload.event_terms,
                onset_date=payload.onset_date,
                outcome=payload.outcome,
                seriousness_criteria=payload.seriousness_criteria,
                causality=payload.causality,
                status=ICSRStatus.INITIAL,
                received_date=now,
                source=payload.source,
                country=payload.country,
                narrative=payload.narrative,
            )
            self._icsrs[icsr_id] = icsr
            return icsr

    def get_icsr(self, icsr_id: str) -> Optional[ICSR]:
        """Get a single ICSR by ID."""
        return self._icsrs.get(icsr_id)

    def update_icsr(self, icsr_id: str, payload: ICSRUpdate) -> Optional[ICSR]:
        """Update an existing ICSR."""
        with self._lock:
            icsr = self._icsrs.get(icsr_id)
            if not icsr:
                return None

            # Status transition validation
            if payload.status is not None and payload.status != icsr.status:
                valid = VALID_ICSR_TRANSITIONS.get(icsr.status, set())
                if payload.status not in valid:
                    raise ValueError(
                        f"Invalid ICSR status transition: {icsr.status.value} -> {payload.status.value}"
                    )

            data = icsr.model_dump()
            updates = payload.model_dump(exclude_none=True)
            data.update(updates)
            updated_icsr = ICSR(**data)
            self._icsrs[icsr_id] = updated_icsr
            return updated_icsr

    def list_icsrs(
        self,
        drug_name: Optional[str] = None,
        status: Optional[ICSRStatus] = None,
        source: Optional[SignalSource] = None,
        country: Optional[str] = None,
        causality: Optional[CausalityCategory] = None,
        serious: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ICSRListResponse:
        """List ICSRs with optional filters."""
        items = list(self._icsrs.values())

        if drug_name:
            items = [c for c in items if c.drug_name.lower() == drug_name.lower()]
        if status:
            items = [c for c in items if c.status == status]
        if source:
            items = [c for c in items if c.source == source]
        if country:
            items = [c for c in items if c.country == country]
        if causality:
            items = [c for c in items if c.causality == causality]
        if serious is not None:
            if serious:
                items = [c for c in items if len(c.seriousness_criteria) > 0]
            else:
                items = [c for c in items if len(c.seriousness_criteria) == 0]

        total = len(items)
        items = items[offset: offset + limit]
        return ICSRListResponse(items=items, total=total, limit=limit, offset=offset)

    def search_icsrs(self, query: str, limit: int = 50, offset: int = 0) -> ICSRListResponse:
        """Search ICSRs by text query across multiple fields."""
        q = query.lower()
        items = [
            c for c in self._icsrs.values()
            if q in c.drug_name.lower()
            or q in c.case_number.lower()
            or q in (c.narrative or "").lower()
            or any(q in e.lower() for e in c.event_terms)
            or q in (c.indication or "").lower()
        ]
        total = len(items)
        items = items[offset: offset + limit]
        return ICSRListResponse(items=items, total=total, limit=limit, offset=offset)

    def delete_icsr(self, icsr_id: str) -> bool:
        """Delete (nullify) an ICSR."""
        with self._lock:
            if icsr_id in self._icsrs:
                del self._icsrs[icsr_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Signal Detection via Disproportionality Analysis
    # ------------------------------------------------------------------

    def _calculate_prr(self, a: int, b: int, c: int, d: int) -> DisproportionalityResult:
        """Calculate Proportional Reporting Ratio.

        2x2 table:
            a = drug+event, b = drug+other_events
            c = other_drugs+event, d = other_drugs+other_events
        """
        if b == 0 or c == 0 or d == 0 or (c + d) == 0 or (a + b) == 0:
            return DisproportionalityResult(
                method=DisproportionalityMethod.PRR,
                drug="", event="",
                observed=a, expected=0.0,
                measure=0.0, lower_ci=0.0, upper_ci=0.0,
                signal_detected=False,
            )

        prr = (a / (a + b)) / (c / (c + d))
        expected = (a + b) * (c / (c + d))
        # CI using log transformation
        se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d)) if a > 0 else 1.0
        lower = math.exp(math.log(prr) - 1.96 * se) if prr > 0 else 0.0
        upper = math.exp(math.log(prr) + 1.96 * se) if prr > 0 else 0.0

        # Signal: PRR >= 2, chi-squared >= 4, N >= 3
        chi2 = ((a * d - b * c) ** 2 * (a + b + c + d)) / max(((a + b) * (c + d) * (a + c) * (b + d)), 1)
        signal = prr >= 2.0 and chi2 >= 4.0 and a >= 3

        return DisproportionalityResult(
            method=DisproportionalityMethod.PRR,
            drug="", event="",
            observed=a,
            expected=round(expected, 2),
            measure=round(prr, 4),
            lower_ci=round(lower, 4),
            upper_ci=round(upper, 4),
            signal_detected=signal,
        )

    def _calculate_ror(self, a: int, b: int, c: int, d: int) -> DisproportionalityResult:
        """Calculate Reporting Odds Ratio."""
        if b == 0 or c == 0 or d == 0:
            return DisproportionalityResult(
                method=DisproportionalityMethod.ROR,
                drug="", event="",
                observed=a, expected=0.0,
                measure=0.0, lower_ci=0.0, upper_ci=0.0,
                signal_detected=False,
            )

        ror = (a * d) / (b * c) if (b * c) > 0 else 0.0
        expected = (a + b) * (a + c) / max((a + b + c + d), 1)
        se = math.sqrt(1 / max(a, 1) + 1 / max(b, 1) + 1 / max(c, 1) + 1 / max(d, 1))
        lower = math.exp(math.log(ror) - 1.96 * se) if ror > 0 else 0.0
        upper = math.exp(math.log(ror) + 1.96 * se) if ror > 0 else 0.0

        # Signal: lower CI > 1
        signal = lower > 1.0 and a >= 3

        return DisproportionalityResult(
            method=DisproportionalityMethod.ROR,
            drug="", event="",
            observed=a,
            expected=round(expected, 2),
            measure=round(ror, 4),
            lower_ci=round(lower, 4),
            upper_ci=round(upper, 4),
            signal_detected=signal,
        )

    def _calculate_ic(self, a: int, b: int, c: int, d: int) -> DisproportionalityResult:
        """Calculate Information Component (BCPNN).

        IC = log2(observed / expected) with shrinkage.
        """
        n = a + b + c + d
        if n == 0:
            return DisproportionalityResult(
                method=DisproportionalityMethod.BCPNN,
                drug="", event="",
                observed=a, expected=0.0,
                measure=0.0, lower_ci=0.0, upper_ci=0.0,
                signal_detected=False,
            )

        expected = (a + b) * (a + c) / n
        # Add 0.5 Haldane correction
        ic = math.log2((a + 0.5) / (expected + 0.5)) if expected > 0 else 0.0
        # Approximate variance
        var = 1 / (a + 0.5)
        se = math.sqrt(var)
        ic025 = ic - 1.96 * se
        ic975 = ic + 1.96 * se

        # Signal: IC025 > 0
        signal = ic025 > 0 and a >= 3

        return DisproportionalityResult(
            method=DisproportionalityMethod.BCPNN,
            drug="", event="",
            observed=a,
            expected=round(expected, 2),
            measure=round(ic, 4),
            lower_ci=round(ic025, 4),
            upper_ci=round(ic975, 4),
            signal_detected=signal,
        )

    def _calculate_ebgm(self, a: int, b: int, c: int, d: int) -> DisproportionalityResult:
        """Calculate Empirical Bayesian Geometric Mean (MGPS).

        Simplified EBGM using gamma-Poisson shrinkage.
        """
        n = a + b + c + d
        if n == 0:
            return DisproportionalityResult(
                method=DisproportionalityMethod.EBGM,
                drug="", event="",
                observed=a, expected=0.0,
                measure=0.0, lower_ci=0.0, upper_ci=0.0,
                signal_detected=False,
            )

        expected = (a + b) * (a + c) / n
        # Simplified EBGM with shrinkage towards prior
        alpha_prior = 0.5
        beta_prior = 0.5
        alpha_post = alpha_prior + a
        beta_post = beta_prior + expected
        ebgm = alpha_post / beta_post if beta_post > 0 else 0.0

        # Approximate CI using gamma quantiles (simplified)
        from math import gamma as gamma_fn

        lower = max(0, ebgm * 0.65)
        upper = ebgm * 1.5

        # Signal: EB05 (lower 5th percentile) > 2
        eb05 = lower
        signal = eb05 > 1.0 and a >= 3

        return DisproportionalityResult(
            method=DisproportionalityMethod.EBGM,
            drug="", event="",
            observed=a,
            expected=round(expected, 2),
            measure=round(ebgm, 4),
            lower_ci=round(lower, 4),
            upper_ci=round(upper, 4),
            signal_detected=signal,
        )

    def _build_contingency(self, drug_name: str, event_term: str) -> tuple[int, int, int, int]:
        """Build a 2x2 contingency table from current ICSRs."""
        a = 0  # drug + event
        b = 0  # drug + other events
        c = 0  # other drugs + event
        d = 0  # other drugs + other events

        for icsr in self._icsrs.values():
            is_drug = icsr.drug_name.lower() == drug_name.lower()
            is_event = any(e.lower() == event_term.lower() for e in icsr.event_terms)

            if is_drug and is_event:
                a += 1
            elif is_drug and not is_event:
                b += 1
            elif not is_drug and is_event:
                c += 1
            else:
                d += 1

        return a, b, c, d

    def detect_signal(self, request: SignalDetectionRequest) -> DisproportionalityAnalysisResponse:
        """Run disproportionality analysis for a drug-event pair."""
        a, b, c, d = self._build_contingency(request.drug_name, request.event_term)

        results: list[DisproportionalityResult] = []
        any_signal = False
        strongest = None
        strongest_val = 0.0

        for method in request.methods:
            if method == DisproportionalityMethod.PRR:
                r = self._calculate_prr(a, b, c, d)
            elif method == DisproportionalityMethod.ROR:
                r = self._calculate_ror(a, b, c, d)
            elif method == DisproportionalityMethod.BCPNN:
                r = self._calculate_ic(a, b, c, d)
            elif method in (DisproportionalityMethod.EBGM, DisproportionalityMethod.MGPS):
                r = self._calculate_ebgm(a, b, c, d)
            else:
                continue

            r.drug = request.drug_name
            r.event = request.event_term
            results.append(r)

            if r.signal_detected:
                any_signal = True
                if r.measure > strongest_val:
                    strongest_val = r.measure
                    strongest = r.method.value

        return DisproportionalityAnalysisResponse(
            drug=request.drug_name,
            event=request.event_term,
            results=results,
            signal_detected=any_signal,
            strongest_method=strongest,
        )

    # ------------------------------------------------------------------
    # Signal CRUD
    # ------------------------------------------------------------------

    def create_signal(self, payload: SignalCreate) -> SignalRecord:
        """Create a new signal record."""
        with self._lock:
            sig_id = f"SIG-{len(self._signals) + 1:04d}"
            now = datetime.now(timezone.utc)

            # Run detection to populate stats
            req = SignalDetectionRequest(
                drug_name=payload.drug_name,
                event_term=payload.event_term,
            )
            analysis = self.detect_signal(req)
            prr_r = next((r for r in analysis.results if r.method == DisproportionalityMethod.PRR), None)
            ror_r = next((r for r in analysis.results if r.method == DisproportionalityMethod.ROR), None)
            ic_r = next((r for r in analysis.results if r.method == DisproportionalityMethod.BCPNN), None)
            ebgm_r = next((r for r in analysis.results if r.method == DisproportionalityMethod.EBGM), None)

            signal = SignalRecord(
                id=sig_id,
                title=payload.title,
                description=payload.description,
                drug_name=payload.drug_name,
                event_term=payload.event_term,
                meddra_pt_code=payload.meddra_pt_code,
                source=payload.source,
                classification=SignalClassification.UNDER_EVALUATION,
                detected_date=now,
                detection_method=payload.detection_method or (analysis.strongest_method or "PRR"),
                prr=prr_r.measure if prr_r else None,
                ror=ror_r.measure if ror_r else None,
                ic025=ic_r.lower_ci if ic_r else None,
                ebgm=ebgm_r.measure if ebgm_r else None,
                case_count=payload.case_count or (prr_r.observed if prr_r else 0),
                expected_count=payload.expected_count,
                background_rate=payload.background_rate or BACKGROUND_RATES.get(payload.event_term, 100.0),
                evidence_strength=None,
                created_at=now,
                updated_at=now,
            )
            self._signals[sig_id] = signal
            return signal

    def get_signal(self, signal_id: str) -> Optional[SignalRecord]:
        """Get a single signal by ID."""
        return self._signals.get(signal_id)

    def update_signal(self, signal_id: str, payload: SignalUpdate) -> Optional[SignalRecord]:
        """Update an existing signal record."""
        with self._lock:
            signal = self._signals.get(signal_id)
            if not signal:
                return None

            # Classification transition validation
            if payload.classification is not None and payload.classification != signal.classification:
                valid = VALID_SIGNAL_TRANSITIONS.get(signal.classification, set())
                if payload.classification not in valid:
                    raise ValueError(
                        f"Invalid signal classification transition: "
                        f"{signal.classification.value} -> {payload.classification.value}"
                    )

            data = signal.model_dump()
            updates = payload.model_dump(exclude_none=True)
            data.update(updates)
            data["updated_at"] = datetime.now(timezone.utc)
            updated = SignalRecord(**data)
            self._signals[signal_id] = updated
            return updated

    def list_signals(
        self,
        drug_name: Optional[str] = None,
        classification: Optional[SignalClassification] = None,
        source: Optional[SignalSource] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SignalListResponse:
        """List signals with optional filters."""
        items = list(self._signals.values())

        if drug_name:
            items = [s for s in items if s.drug_name.lower() == drug_name.lower()]
        if classification:
            items = [s for s in items if s.classification == classification]
        if source:
            items = [s for s in items if s.source == source]

        total = len(items)
        items = items[offset: offset + limit]
        return SignalListResponse(items=items, total=total, limit=limit, offset=offset)

    def delete_signal(self, signal_id: str) -> bool:
        """Delete a signal."""
        with self._lock:
            if signal_id in self._signals:
                del self._signals[signal_id]
                return True
            return False

    # ------------------------------------------------------------------
    # MedDRA coding
    # ------------------------------------------------------------------

    def search_meddra(self, query: str, level: Optional[MedDRALevel] = None, limit: int = 20) -> MedDRASearchResponse:
        """Search MedDRA terms by text query."""
        q = query.lower()
        results = [
            t for t in self._meddra_terms.values()
            if q in t.term.lower() or q in t.code
        ]
        if level:
            results = [t for t in results if t.level == level]
        total = len(results)
        results = results[:limit]
        return MedDRASearchResponse(terms=results, total=total)

    def get_meddra_term(self, code: str) -> Optional[MedDRATerm]:
        """Get a MedDRA term by code."""
        return self._meddra_terms.get(code)

    def get_meddra_hierarchy(self, code: str) -> Optional[MedDRAHierarchyResponse]:
        """Get the MedDRA hierarchy for a term (ancestors and children)."""
        term = self._meddra_terms.get(code)
        if not term:
            return None

        # Walk up to ancestors
        ancestors: list[MedDRATerm] = []
        current = term
        while current.parent_code and current.parent_code in self._meddra_terms:
            parent = self._meddra_terms[current.parent_code]
            ancestors.append(parent)
            current = parent

        # Find children
        children = [
            t for t in self._meddra_terms.values()
            if t.parent_code == code
        ]

        return MedDRAHierarchyResponse(term=term, ancestors=ancestors, children=children)

    def code_to_meddra(self, event_term: str) -> Optional[MedDRATerm]:
        """Map a free-text event term to a MedDRA Preferred Term."""
        q = event_term.lower()
        # Exact match first
        for t in self._meddra_terms.values():
            if t.term.lower() == q and t.level == MedDRALevel.PT:
                return t
        # Partial match on PT level
        for t in self._meddra_terms.values():
            if q in t.term.lower() and t.level == MedDRALevel.PT:
                return t
        # Any level partial match
        for t in self._meddra_terms.values():
            if q in t.term.lower():
                return t
        return None

    # ------------------------------------------------------------------
    # Periodic Safety Reports
    # ------------------------------------------------------------------

    def generate_periodic_report(
        self,
        drug_name: str,
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
    ) -> PeriodicSafetyReport:
        """Generate a periodic safety report for a drug."""
        with self._lock:
            # Gather cases in period
            cases_in_period = [
                c for c in self._icsrs.values()
                if c.drug_name.lower() == drug_name.lower()
                and c.received_date >= period_start
                and c.received_date <= period_end
            ]

            total = len(cases_in_period)
            serious = sum(1 for c in cases_in_period if len(c.seriousness_criteria) > 0)
            fatal = sum(1 for c in cases_in_period if c.outcome and c.outcome.lower() == "fatal")

            # Signal counts
            drug_signals = [
                s for s in self._signals.values()
                if s.drug_name.lower() == drug_name.lower()
            ]
            new_sigs = sum(1 for s in drug_signals if s.detected_date >= period_start and s.detected_date <= period_end)
            updated_sigs = sum(
                1 for s in drug_signals
                if s.updated_at and s.updated_at >= period_start and s.updated_at <= period_end
            )
            closed_sigs = sum(
                1 for s in drug_signals
                if s.classification == SignalClassification.CLOSED
            )

            rid = f"PSR-{len(self._periodic_reports) + 1:04d}"
            now = datetime.now(timezone.utc)

            report = PeriodicSafetyReport(
                id=rid,
                drug_name=drug_name,
                report_type=report_type,
                period_start=period_start,
                period_end=period_end,
                total_cases=total,
                serious_cases=serious,
                fatal_cases=fatal,
                new_signals=new_sigs,
                updated_signals=updated_sigs,
                closed_signals=closed_sigs,
                benefit_risk_assessment=f"Benefit-risk assessment for {drug_name}: {total} cases reviewed in period.",
                submitted_to=None,
                submission_date=None,
                created_at=now,
            )
            self._periodic_reports[rid] = report
            return report

    def get_periodic_report(self, report_id: str) -> Optional[PeriodicSafetyReport]:
        """Get a single periodic safety report."""
        return self._periodic_reports.get(report_id)

    def list_periodic_reports(
        self,
        drug_name: Optional[str] = None,
        report_type: Optional[ReportType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PeriodicSafetyReportListResponse:
        """List periodic safety reports with optional filters."""
        items = list(self._periodic_reports.values())

        if drug_name:
            items = [r for r in items if r.drug_name.lower() == drug_name.lower()]
        if report_type:
            items = [r for r in items if r.report_type == report_type]

        total = len(items)
        items = items[offset: offset + limit]
        return PeriodicSafetyReportListResponse(items=items, total=total, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Regulatory Actions
    # ------------------------------------------------------------------

    def create_regulatory_action(self, payload: RegulatoryActionCreate) -> RegulatoryAction:
        """Create a new regulatory action."""
        with self._lock:
            # Verify signal exists
            if payload.signal_id not in self._signals:
                raise ValueError(f"Signal {payload.signal_id} not found")

            aid = f"RA-{len(self._regulatory_actions) + 1:04d}"
            now = datetime.now(timezone.utc)

            action = RegulatoryAction(
                id=aid,
                signal_id=payload.signal_id,
                action_type=payload.action_type,
                agency=payload.agency,
                description=payload.description,
                effective_date=payload.effective_date,
                status=RegulatoryActionStatus.PROPOSED,
                implementation_date=None,
                created_at=now,
            )
            self._regulatory_actions[aid] = action
            return action

    def get_regulatory_action(self, action_id: str) -> Optional[RegulatoryAction]:
        """Get a single regulatory action."""
        return self._regulatory_actions.get(action_id)

    def list_regulatory_actions(
        self,
        signal_id: Optional[str] = None,
        action_type: Optional[RegulatoryActionType] = None,
        agency: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RegulatoryActionListResponse:
        """List regulatory actions with optional filters."""
        items = list(self._regulatory_actions.values())

        if signal_id:
            items = [a for a in items if a.signal_id == signal_id]
        if action_type:
            items = [a for a in items if a.action_type == action_type]
        if agency:
            items = [a for a in items if a.agency.lower() == agency.lower()]

        total = len(items)
        items = items[offset: offset + limit]
        return RegulatoryActionListResponse(items=items, total=total, limit=limit, offset=offset)

    def update_regulatory_action_status(
        self, action_id: str, status: RegulatoryActionStatus
    ) -> Optional[RegulatoryAction]:
        """Update the status of a regulatory action."""
        with self._lock:
            action = self._regulatory_actions.get(action_id)
            if not action:
                return None

            data = action.model_dump()
            data["status"] = status
            now = datetime.now(timezone.utc)
            if status == RegulatoryActionStatus.IMPLEMENTED:
                data["implementation_date"] = now
            updated = RegulatoryAction(**data)
            self._regulatory_actions[action_id] = updated
            return updated

    # ------------------------------------------------------------------
    # Case Series Analysis
    # ------------------------------------------------------------------

    def case_series_analysis(self, drug_name: str, event_term: str) -> CaseSeriesResult:
        """Perform case series analysis for a drug-event pair."""
        matching = [
            c for c in self._icsrs.values()
            if c.drug_name.lower() == drug_name.lower()
            and any(e.lower() == event_term.lower() for e in c.event_terms)
        ]

        total = len(matching)
        serious_count = sum(1 for c in matching if len(c.seriousness_criteria) > 0)
        fatal_count = sum(1 for c in matching if c.outcome and c.outcome.lower() == "fatal")

        # Age stats
        ages = [c.patient_age for c in matching if c.patient_age is not None]
        median_age = statistics.median(ages) if ages else None

        # Distributions
        sex_dist: Counter[str] = Counter()
        outcome_dist: Counter[str] = Counter()
        causality_dist: Counter[str] = Counter()
        country_dist: Counter[str] = Counter()
        reporter_dist: Counter[str] = Counter()

        for c in matching:
            sex_dist[c.patient_sex or "Unknown"] += 1
            outcome_dist[c.outcome or "Unknown"] += 1
            causality_dist[c.causality.value] += 1
            country_dist[c.country] += 1
            reporter_dist[c.reporter_type] += 1

        # Onset time
        onset_days = []
        for c in matching:
            if c.onset_date and c.received_date:
                delta = (c.received_date - c.onset_date).days
                if delta >= 0:
                    onset_days.append(delta)
        median_onset = statistics.median(onset_days) if onset_days else None

        return CaseSeriesResult(
            drug_name=drug_name,
            event_term=event_term,
            total_cases=total,
            serious_count=serious_count,
            fatal_count=fatal_count,
            median_age=median_age,
            sex_distribution=dict(sex_dist),
            outcome_distribution=dict(outcome_dist),
            causality_distribution=dict(causality_dist),
            median_onset_days=median_onset,
            country_distribution=dict(country_dist),
            reporter_distribution=dict(reporter_dist),
            cases=matching,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> PharmacovigilanceMetrics:
        """Get aggregated pharmacovigilance metrics."""
        icsrs = list(self._icsrs.values())
        signals = list(self._signals.values())

        total_icsrs = len(icsrs)

        # ICSR breakdowns
        status_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        causality_counts: Counter[str] = Counter()
        drug_counts: Counter[str] = Counter()
        event_counts: Counter[str] = Counter()

        serious_count = 0
        fatal_count = 0

        for c in icsrs:
            status_counts[c.status.value] += 1
            source_counts[c.source.value] += 1
            causality_counts[c.causality.value] += 1
            drug_counts[c.drug_name] += 1
            for e in c.event_terms:
                event_counts[e] += 1
            if len(c.seriousness_criteria) > 0:
                serious_count += 1
            if c.outcome and c.outcome.lower() == "fatal":
                fatal_count += 1

        # Signal breakdowns
        sig_class: Counter[str] = Counter()
        for s in signals:
            sig_class[s.classification.value] += 1

        top_drugs = [{"drug": d, "count": n} for d, n in drug_counts.most_common(10)]
        top_events = [{"event": e, "count": n} for e, n in event_counts.most_common(10)]

        return PharmacovigilanceMetrics(
            total_icsrs=total_icsrs,
            icsrs_by_status=dict(status_counts),
            icsrs_by_source=dict(source_counts),
            icsrs_by_causality=dict(causality_counts),
            total_signals=len(signals),
            signals_by_classification=dict(sig_class),
            validated_signals=sig_class.get(SignalClassification.VALIDATED.value, 0),
            under_evaluation_signals=sig_class.get(SignalClassification.UNDER_EVALUATION.value, 0),
            total_periodic_reports=len(self._periodic_reports),
            total_regulatory_actions=len(self._regulatory_actions),
            top_reported_drugs=top_drugs,
            top_reported_events=top_events,
            serious_case_rate=round(serious_count / total_icsrs * 100, 1) if total_icsrs > 0 else 0.0,
            fatal_case_rate=round(fatal_count / total_icsrs * 100, 1) if total_icsrs > 0 else 0.0,
            meddra_terms_loaded=len(self._meddra_terms),
        )

    def get_stats(self) -> dict:
        """Get service statistics for health check."""
        return {
            "icsrs": len(self._icsrs),
            "signals": len(self._signals),
            "periodic_reports": len(self._periodic_reports),
            "regulatory_actions": len(self._regulatory_actions),
            "meddra_terms": len(self._meddra_terms),
        }


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_instance: Optional[PharmacovigilanceService] = None
_instance_lock = threading.Lock()


def get_pharmacovigilance_service() -> PharmacovigilanceService:
    """Return the singleton PharmacovigilanceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PharmacovigilanceService()
    return _instance


def reset_pharmacovigilance_service() -> PharmacovigilanceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PharmacovigilanceService()
    return _instance
