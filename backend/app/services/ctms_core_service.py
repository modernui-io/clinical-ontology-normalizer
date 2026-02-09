"""Clinical Trial Management System (CTMS) Core Service (CLINICAL-22).

Manages CTMS operations including trial lifecycle management, site activation and
enrollment tracking, patient/subject management with visit scheduling, visit window
compliance, source data verification, and CTMS operational metrics.

Usage:
    from app.services.ctms_core_service import (
        get_ctms_service,
    )

    svc = get_ctms_service()
    trials = svc.list_trials()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import random
import threading
from datetime import date, timedelta, timezone
from uuid import uuid4

from app.schemas.ctms_core import (
    CTMSMetrics,
    CTMSPatient,
    CTMSSite,
    CTMSTrial,
    CTMSVisit,
    PatientCreate,
    PatientStatus,
    PatientUpdate,
    SiteCreate,
    SiteStatus,
    SiteUpdate,
    StudyDesign,
    TherapeuticArea,
    TrialCreate,
    TrialPhase,
    TrialStatus,
    TrialUpdate,
    VisitCreate,
    VisitStatus,
    VisitUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Screen failure target rate ~25%
SCREEN_FAILURE_RATE_TARGET = 0.25


class CTMSService:
    """In-memory CTMS engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._trials: dict[str, CTMSTrial] = {}
        self._sites: dict[str, CTMSSite] = {}
        self._patients: dict[str, CTMSPatient] = {}
        self._visits: dict[str, CTMSVisit] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic CTMS data: 3 Regeneron trials, 15 sites, 50 patients, 120 visits."""
        rng = random.Random(42)  # Deterministic seeding

        # --- 3 Regeneron trials ---
        trials_data = [
            {
                "id": EYLEA_TRIAL,
                "protocol_number": "R1234-OPH-1553",
                "title": "EYLEA HD: A Phase 3 Study of High-Dose Aflibercept in Diabetic Macular Edema",
                "phase": TrialPhase.PHASE3,
                "status": TrialStatus.ENROLLING,
                "therapeutic_area": TherapeuticArea.OPHTHALMOLOGY,
                "study_design": StudyDesign.PARALLEL,
                "indication": "Diabetic Macular Edema (DME)",
                "sponsor": "Regeneron Pharmaceuticals",
                "start_date": date(2025, 3, 15),
                "estimated_end_date": date(2027, 9, 30),
                "actual_end_date": None,
                "target_enrollment": 300,
                "current_enrollment": 187,
                "countries": ["US", "UK", "DE", "JP", "AU"],
                "sites_planned": 8,
                "sites_active": 6,
                "primary_endpoint": "Change in BCVA from baseline at Week 48",
                "secondary_endpoints": [
                    "Proportion gaining >= 15 ETDRS letters at Week 48",
                    "Change in central subfield thickness on OCT at Week 48",
                    "Number of injections through Week 48",
                ],
                "regulatory_ids": {
                    "FDA IND": "IND-154832",
                    "EMA": "EU/1/25/1234",
                    "PMDA": "JP-CTN-2025-0042",
                },
            },
            {
                "id": DUPIXENT_TRIAL,
                "protocol_number": "R2468-IMM-2201",
                "title": "DUPIXENT ADVANCE: Dupilumab in Moderate-to-Severe COPD with Type 2 Inflammation",
                "phase": TrialPhase.PHASE3,
                "status": TrialStatus.ENROLLING,
                "therapeutic_area": TherapeuticArea.IMMUNOLOGY,
                "study_design": StudyDesign.PARALLEL,
                "indication": "Chronic Obstructive Pulmonary Disease (COPD) with Type 2 Inflammation",
                "sponsor": "Regeneron Pharmaceuticals / Sanofi",
                "start_date": date(2025, 1, 10),
                "estimated_end_date": date(2027, 6, 30),
                "actual_end_date": None,
                "target_enrollment": 450,
                "current_enrollment": 298,
                "countries": ["US", "CA", "UK", "FR", "DE", "ES", "IT"],
                "sites_planned": 10,
                "sites_active": 8,
                "primary_endpoint": "Annualized rate of moderate-to-severe COPD exacerbations over 52 weeks",
                "secondary_endpoints": [
                    "Change from baseline in pre-bronchodilator FEV1 at Week 12",
                    "Change from baseline in SGRQ total score at Week 52",
                    "Time to first moderate-to-severe COPD exacerbation",
                ],
                "regulatory_ids": {
                    "FDA IND": "IND-162491",
                    "EMA": "EU/1/25/2468",
                },
            },
            {
                "id": LIBTAYO_TRIAL,
                "protocol_number": "R3692-ONC-3301",
                "title": "LIBTAYO FRONTIER: Cemiplimab plus Chemotherapy in First-Line Advanced NSCLC",
                "phase": TrialPhase.PHASE3B,
                "status": TrialStatus.FULLY_ENROLLED,
                "therapeutic_area": TherapeuticArea.ONCOLOGY,
                "study_design": StudyDesign.ADAPTIVE,
                "indication": "Non-Small Cell Lung Cancer (NSCLC), First-Line Advanced",
                "sponsor": "Regeneron Pharmaceuticals / Sanofi",
                "start_date": date(2024, 9, 1),
                "estimated_end_date": date(2027, 3, 31),
                "actual_end_date": None,
                "target_enrollment": 200,
                "current_enrollment": 200,
                "countries": ["US", "CA", "UK", "DE", "AU", "KR"],
                "sites_planned": 7,
                "sites_active": 5,
                "primary_endpoint": "Overall survival (OS)",
                "secondary_endpoints": [
                    "Progression-free survival (PFS) per RECIST v1.1",
                    "Objective response rate (ORR)",
                    "Duration of response (DOR)",
                    "Patient-reported outcomes (EORTC QLQ-C30)",
                ],
                "regulatory_ids": {
                    "FDA IND": "IND-148205",
                    "EMA": "EU/1/24/3692",
                    "PMDA": "JP-CTN-2024-0188",
                },
            },
        ]

        for t in trials_data:
            self._trials[t["id"]] = CTMSTrial(**t)

        # --- 15 Sites (5 per trial, some shared PI names) ---
        site_templates = [
            # EYLEA trial sites
            ("CTMS-SITE-001", EYLEA_TRIAL, "001", "Bascom Palmer Eye Institute", "Dr. Maria Santos", "900 NW 17th St, Miami, FL", "US", SiteStatus.ACTIVE, date(2025, 4, 1), date(2025, 4, 20), 50, 38, 12),
            ("CTMS-SITE-002", EYLEA_TRIAL, "002", "Moorfields Eye Hospital", "Prof. James Crawford", "162 City Rd, London EC1V 2PD", "UK", SiteStatus.ENROLLING, date(2025, 4, 15), date(2025, 5, 3), 45, 35, 10),
            ("CTMS-SITE-003", EYLEA_TRIAL, "003", "Universitaetsklinikum Freiburg", "Dr. Klaus Weber", "Hugstetter Str. 55, Freiburg", "DE", SiteStatus.ENROLLING, date(2025, 5, 1), date(2025, 5, 18), 40, 28, 8),
            ("CTMS-SITE-004", EYLEA_TRIAL, "004", "Tokyo University Hospital Ophthalmology", "Dr. Yuki Tanaka", "7-3-1 Hongo, Bunkyo-ku, Tokyo", "JP", SiteStatus.ACTIVE, date(2025, 5, 15), date(2025, 6, 5), 35, 22, 7),
            ("CTMS-SITE-005", EYLEA_TRIAL, "005", "Royal Victorian Eye and Ear Hospital", "Dr. Sarah Chen", "32 Gisborne St, East Melbourne VIC", "AU", SiteStatus.ENROLLING, date(2025, 6, 1), date(2025, 6, 20), 30, 18, 5),
            # DUPIXENT trial sites
            ("CTMS-SITE-006", DUPIXENT_TRIAL, "006", "National Jewish Health", "Dr. Richard Barnes", "1400 Jackson St, Denver, CO", "US", SiteStatus.ENROLLING, date(2025, 2, 1), date(2025, 2, 15), 60, 48, 15),
            ("CTMS-SITE-007", DUPIXENT_TRIAL, "007", "University of Toronto Respiratory", "Dr. Patricia Nguyen", "200 Elizabeth St, Toronto, ON", "CA", SiteStatus.ENROLLING, date(2025, 2, 15), date(2025, 3, 1), 55, 42, 13),
            ("CTMS-SITE-008", DUPIXENT_TRIAL, "008", "Hopital Bichat-Claude Bernard", "Dr. Pierre Dubois", "46 Rue Henri Huchard, Paris", "FR", SiteStatus.ACTIVE, date(2025, 3, 1), date(2025, 3, 20), 50, 38, 12),
            ("CTMS-SITE-009", DUPIXENT_TRIAL, "009", "Hospital Clinic de Barcelona", "Dr. Elena Moreno", "C/ de Villarroel, 170, Barcelona", "ES", SiteStatus.ENROLLING, date(2025, 3, 15), date(2025, 4, 5), 45, 35, 10),
            ("CTMS-SITE-010", DUPIXENT_TRIAL, "010", "Charite Universitaetsmedizin Berlin", "Dr. Hans Mueller", "Chariteplatz 1, Berlin", "DE", SiteStatus.ACTIVE, date(2025, 4, 1), date(2025, 4, 18), 40, 25, 8),
            # LIBTAYO trial sites
            ("CTMS-SITE-011", LIBTAYO_TRIAL, "011", "Memorial Sloan Kettering Cancer Center", "Dr. Robert Kim", "1275 York Ave, New York, NY", "US", SiteStatus.CLOSED_TO_ENROLLMENT, date(2024, 10, 1), date(2024, 10, 15), 50, 50, 18),
            ("CTMS-SITE-012", LIBTAYO_TRIAL, "012", "Princess Margaret Cancer Centre", "Dr. Anne Thompson", "610 University Ave, Toronto, ON", "CA", SiteStatus.CLOSED_TO_ENROLLMENT, date(2024, 10, 15), date(2024, 11, 1), 40, 40, 14),
            ("CTMS-SITE-013", LIBTAYO_TRIAL, "013", "Royal Marsden Hospital", "Prof. David Wright", "Fulham Rd, London SW3 6JJ", "UK", SiteStatus.ACTIVE, date(2024, 11, 1), date(2024, 11, 20), 35, 35, 11),
            ("CTMS-SITE-014", LIBTAYO_TRIAL, "014", "Peter MacCallum Cancer Centre", "Dr. Lisa Park", "305 Grattan St, Melbourne VIC", "AU", SiteStatus.ACTIVE, date(2024, 11, 15), date(2024, 12, 5), 40, 40, 12),
            ("CTMS-SITE-015", LIBTAYO_TRIAL, "015", "Samsung Medical Center Oncology", "Dr. Min-Jae Lee", "81 Irwon-ro, Gangnam-gu, Seoul", "KR", SiteStatus.ACTIVE, date(2024, 12, 1), date(2024, 12, 15), 35, 35, 10),
        ]

        for s_data in site_templates:
            sid, trial_id, snum, name, pi, addr, country, status, act_date, fpd, target, enrolled, sf = s_data
            self._sites[sid] = CTMSSite(
                id=sid,
                trial_id=trial_id,
                site_number=snum,
                name=name,
                pi_name=pi,
                address=addr,
                country=country,
                status=status,
                activation_date=act_date,
                first_patient_date=fpd,
                enrollment_target=target,
                enrolled_count=enrolled,
                screen_failure_count=sf,
            )

        # --- 50 Patients (distributed across sites with ~25% screen failure rate) ---
        treatment_arms = {
            EYLEA_TRIAL: ["EYLEA HD 8mg q12w", "EYLEA 2mg q8w"],
            DUPIXENT_TRIAL: ["Dupilumab 300mg q2w", "Placebo q2w"],
            LIBTAYO_TRIAL: ["Cemiplimab + Chemo", "Chemo Alone", "Cemiplimab Mono"],
        }

        visit_names_by_trial = {
            EYLEA_TRIAL: ["Screening", "Baseline", "Week 4", "Week 8", "Week 12", "Week 16", "Week 24", "Week 36", "Week 48"],
            DUPIXENT_TRIAL: ["Screening", "Baseline", "Week 2", "Week 4", "Week 8", "Week 12", "Week 24", "Week 52"],
            LIBTAYO_TRIAL: ["Screening", "Baseline", "Cycle 1 Day 1", "Cycle 2 Day 1", "Cycle 3 Day 1", "Cycle 4 Day 1", "Week 12 Scan", "Week 24 Scan"],
        }

        patient_counter = 0
        visit_counter = 0

        sites_by_trial: dict[str, list[str]] = {}
        for sid, site in self._sites.items():
            sites_by_trial.setdefault(site.trial_id, []).append(sid)

        for trial_id, site_ids in sites_by_trial.items():
            arms = treatment_arms[trial_id]
            visit_schedule = visit_names_by_trial[trial_id]

            # Distribute ~17 patients per trial (50 total / 3 trials)
            patients_per_trial = 17 if trial_id != LIBTAYO_TRIAL else 16
            patients_per_site_base = patients_per_trial // len(site_ids)
            remainder = patients_per_trial % len(site_ids)

            for site_idx, site_id in enumerate(site_ids):
                n_patients = patients_per_site_base + (1 if site_idx < remainder else 0)

                for p_idx in range(n_patients):
                    patient_counter += 1
                    pid = f"CTMS-PAT-{patient_counter:04d}"
                    subj_num = f"SUBJ-{patient_counter:04d}"

                    # Determine status: ~25% screen failed, rest active/enrolled/completed
                    is_screen_failure = rng.random() < SCREEN_FAILURE_RATE_TARGET
                    screening_dt = date(2025, rng.randint(2, 10), rng.randint(1, 28))

                    if is_screen_failure:
                        status = PatientStatus.SCREEN_FAILED
                        rand_date = None
                        arm = None
                        current_visit = "Screening"
                        last_visit = screening_dt
                        withdrawal_reason = rng.choice([
                            "Inclusion criteria not met",
                            "Exclusion criterion: concomitant medication",
                            "Abnormal lab values at screening",
                            "Withdrew consent before randomization",
                        ])
                    else:
                        # Active patient
                        rand_date = screening_dt + timedelta(days=rng.randint(7, 21))
                        arm = rng.choice(arms)

                        if trial_id == LIBTAYO_TRIAL:
                            # Fully enrolled trial - patients further along
                            status_choice = rng.choice([
                                PatientStatus.ACTIVE, PatientStatus.ACTIVE,
                                PatientStatus.ACTIVE, PatientStatus.COMPLETED,
                                PatientStatus.WITHDRAWN,
                            ])
                        else:
                            status_choice = rng.choice([
                                PatientStatus.ACTIVE, PatientStatus.ACTIVE,
                                PatientStatus.ENROLLED,
                            ])

                        if status_choice == PatientStatus.WITHDRAWN:
                            status = PatientStatus.WITHDRAWN
                            withdrawal_reason = rng.choice([
                                "Adverse event",
                                "Withdrew consent",
                                "Lost to follow-up",
                                "Protocol deviation",
                            ])
                        else:
                            status = status_choice
                            withdrawal_reason = None

                        visit_progress = rng.randint(1, len(visit_schedule) - 1)
                        current_visit = visit_schedule[min(visit_progress, len(visit_schedule) - 1)]
                        last_visit = rand_date + timedelta(days=visit_progress * rng.randint(14, 35))

                    patient = CTMSPatient(
                        id=pid,
                        trial_id=trial_id,
                        site_id=site_id,
                        subject_number=subj_num,
                        screening_date=screening_dt,
                        randomization_date=rand_date,
                        treatment_arm=arm,
                        current_visit=current_visit,
                        last_visit_date=last_visit,
                        status=status,
                        withdrawal_reason=withdrawal_reason,
                    )
                    self._patients[pid] = patient

                    # --- Create visits for non-screen-failed patients ---
                    if not is_screen_failure and rand_date is not None:
                        n_visits = rng.randint(2, min(6, len(visit_schedule)))
                        for v_idx in range(n_visits):
                            visit_counter += 1
                            vid = f"CTMS-VIS-{visit_counter:04d}"
                            v_name = visit_schedule[v_idx]
                            sched_date = rand_date + timedelta(days=v_idx * rng.randint(14, 42))
                            window_start = sched_date - timedelta(days=3)
                            window_end = sched_date + timedelta(days=5)

                            # Determine actual date and status
                            if v_idx < n_visits - 1:
                                # Completed visits
                                offset = rng.randint(-2, 4)
                                actual = sched_date + timedelta(days=offset)
                                if window_start <= actual <= window_end:
                                    v_status = VisitStatus.COMPLETED
                                else:
                                    v_status = VisitStatus.OUT_OF_WINDOW
                                sdv = rng.random() < 0.7
                            else:
                                # Last visit may be scheduled or in-window
                                actual = None
                                v_status = VisitStatus.SCHEDULED
                                sdv = False

                            visit = CTMSVisit(
                                id=vid,
                                patient_id=pid,
                                trial_id=trial_id,
                                visit_number=v_idx,
                                visit_name=v_name,
                                scheduled_date=sched_date,
                                actual_date=actual,
                                window_start=window_start,
                                window_end=window_end,
                                status=v_status,
                                source_data_verified=sdv,
                            )
                            self._visits[vid] = visit
                    elif is_screen_failure:
                        # Screen failure gets a screening visit
                        visit_counter += 1
                        vid = f"CTMS-VIS-{visit_counter:04d}"
                        visit = CTMSVisit(
                            id=vid,
                            patient_id=pid,
                            trial_id=trial_id,
                            visit_number=0,
                            visit_name="Screening",
                            scheduled_date=screening_dt,
                            actual_date=screening_dt,
                            window_start=screening_dt - timedelta(days=3),
                            window_end=screening_dt + timedelta(days=5),
                            status=VisitStatus.COMPLETED,
                            source_data_verified=rng.random() < 0.5,
                        )
                        self._visits[vid] = visit

        logger.info(
            "CTMS seeded: %d trials, %d sites, %d patients, %d visits",
            len(self._trials), len(self._sites), len(self._patients), len(self._visits),
        )

    # ------------------------------------------------------------------
    # Trial Management
    # ------------------------------------------------------------------

    def list_trials(
        self,
        *,
        phase: TrialPhase | None = None,
        status: TrialStatus | None = None,
        therapeutic_area: TherapeuticArea | None = None,
    ) -> list[CTMSTrial]:
        """List trials with optional filters."""
        with self._lock:
            result = list(self._trials.values())

        if phase is not None:
            result = [t for t in result if t.phase == phase]
        if status is not None:
            result = [t for t in result if t.status == status]
        if therapeutic_area is not None:
            result = [t for t in result if t.therapeutic_area == therapeutic_area]

        return sorted(result, key=lambda t: t.protocol_number)

    def get_trial(self, trial_id: str) -> CTMSTrial | None:
        """Get a single trial by ID."""
        with self._lock:
            return self._trials.get(trial_id)

    def create_trial(self, payload: TrialCreate) -> CTMSTrial:
        """Create a new clinical trial."""
        trial_id = f"CTMS-TRIAL-{uuid4().hex[:8].upper()}"
        trial = CTMSTrial(
            id=trial_id,
            status=TrialStatus.PLANNING,
            current_enrollment=0,
            sites_active=0,
            **payload.model_dump(),
        )
        with self._lock:
            self._trials[trial_id] = trial
        logger.info("Created trial %s: %s", trial_id, payload.protocol_number)
        return trial

    def update_trial(self, trial_id: str, payload: TrialUpdate) -> CTMSTrial | None:
        """Update an existing trial."""
        with self._lock:
            existing = self._trials.get(trial_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CTMSTrial(**data)
            self._trials[trial_id] = updated
        return updated

    def delete_trial(self, trial_id: str) -> bool:
        """Delete a trial. Returns True if deleted, False if not found."""
        with self._lock:
            if trial_id in self._trials:
                del self._trials[trial_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Management
    # ------------------------------------------------------------------

    def list_sites(
        self,
        *,
        trial_id: str | None = None,
        status: SiteStatus | None = None,
        country: str | None = None,
    ) -> list[CTMSSite]:
        """List sites with optional filters."""
        with self._lock:
            result = list(self._sites.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if country is not None:
            result = [s for s in result if s.country == country]

        return sorted(result, key=lambda s: s.site_number)

    def get_site(self, site_id: str) -> CTMSSite | None:
        """Get a single site by ID."""
        with self._lock:
            return self._sites.get(site_id)

    def create_site(self, payload: SiteCreate) -> CTMSSite:
        """Create a new site."""
        site_id = f"CTMS-SITE-{uuid4().hex[:8].upper()}"
        site = CTMSSite(
            id=site_id,
            status=SiteStatus.SELECTED,
            **payload.model_dump(),
        )
        with self._lock:
            self._sites[site_id] = site
        logger.info("Created site %s for trial %s", site_id, payload.trial_id)
        return site

    def update_site(self, site_id: str, payload: SiteUpdate) -> CTMSSite | None:
        """Update an existing site."""
        with self._lock:
            existing = self._sites.get(site_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CTMSSite(**data)
            self._sites[site_id] = updated
        return updated

    def delete_site(self, site_id: str) -> bool:
        """Delete a site. Returns True if deleted."""
        with self._lock:
            if site_id in self._sites:
                del self._sites[site_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Patient Management
    # ------------------------------------------------------------------

    def list_patients(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: PatientStatus | None = None,
    ) -> list[CTMSPatient]:
        """List patients with optional filters."""
        with self._lock:
            result = list(self._patients.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if site_id is not None:
            result = [p for p in result if p.site_id == site_id]
        if status is not None:
            result = [p for p in result if p.status == status]

        return sorted(result, key=lambda p: p.subject_number)

    def get_patient(self, patient_id: str) -> CTMSPatient | None:
        """Get a single patient by ID."""
        with self._lock:
            return self._patients.get(patient_id)

    def create_patient(self, payload: PatientCreate) -> CTMSPatient:
        """Screen a new patient."""
        patient_id = f"CTMS-PAT-{uuid4().hex[:8].upper()}"
        patient = CTMSPatient(
            id=patient_id,
            status=PatientStatus.SCREENING,
            **payload.model_dump(),
        )
        with self._lock:
            self._patients[patient_id] = patient
        logger.info("Screened patient %s at site %s", patient_id, payload.site_id)
        return patient

    def update_patient(self, patient_id: str, payload: PatientUpdate) -> CTMSPatient | None:
        """Update a patient record."""
        with self._lock:
            existing = self._patients.get(patient_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # When enrolling, update current visit
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = PatientStatus(new_status)
                if new_status == PatientStatus.ENROLLED and existing.status == PatientStatus.SCREENING:
                    if "current_visit" not in updates:
                        updates["current_visit"] = "Baseline"

                # Track screen failures on the site
                if new_status == PatientStatus.SCREEN_FAILED and existing.status != PatientStatus.SCREEN_FAILED:
                    site = self._sites.get(existing.site_id)
                    if site is not None:
                        site_data = site.model_dump()
                        site_data["screen_failure_count"] = site.screen_failure_count + 1
                        self._sites[existing.site_id] = CTMSSite(**site_data)

            data.update(updates)
            updated = CTMSPatient(**data)
            self._patients[patient_id] = updated
        return updated

    def delete_patient(self, patient_id: str) -> bool:
        """Delete a patient record. Returns True if deleted."""
        with self._lock:
            if patient_id in self._patients:
                del self._patients[patient_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Visit Management
    # ------------------------------------------------------------------

    def list_visits(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
        status: VisitStatus | None = None,
    ) -> list[CTMSVisit]:
        """List visits with optional filters."""
        with self._lock:
            result = list(self._visits.values())

        if patient_id is not None:
            result = [v for v in result if v.patient_id == patient_id]
        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if status is not None:
            result = [v for v in result if v.status == status]

        return sorted(result, key=lambda v: (v.patient_id, v.visit_number))

    def get_visit(self, visit_id: str) -> CTMSVisit | None:
        """Get a single visit by ID."""
        with self._lock:
            return self._visits.get(visit_id)

    def create_visit(self, payload: VisitCreate) -> CTMSVisit:
        """Schedule a new visit."""
        visit_id = f"CTMS-VIS-{uuid4().hex[:8].upper()}"
        visit = CTMSVisit(
            id=visit_id,
            status=VisitStatus.SCHEDULED,
            **payload.model_dump(),
        )
        with self._lock:
            self._visits[visit_id] = visit
        logger.info("Scheduled visit %s for patient %s", visit_id, payload.patient_id)
        return visit

    def update_visit(self, visit_id: str, payload: VisitUpdate) -> CTMSVisit | None:
        """Update a visit (e.g., record actual date, mark SDV)."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-determine window compliance when actual_date is set
            if "actual_date" in updates and updates["actual_date"] is not None:
                actual = updates["actual_date"]
                if isinstance(actual, str):
                    actual = date.fromisoformat(actual)
                if existing.window_start <= actual <= existing.window_end:
                    if "status" not in updates:
                        updates["status"] = VisitStatus.COMPLETED
                else:
                    if "status" not in updates:
                        updates["status"] = VisitStatus.OUT_OF_WINDOW

            data.update(updates)
            updated = CTMSVisit(**data)
            self._visits[visit_id] = updated
        return updated

    def delete_visit(self, visit_id: str) -> bool:
        """Delete a visit. Returns True if deleted."""
        with self._lock:
            if visit_id in self._visits:
                del self._visits[visit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Enrollment Summary (for a trial)
    # ------------------------------------------------------------------

    def get_enrollment_summary(self, trial_id: str) -> dict | None:
        """Get enrollment summary for a trial."""
        with self._lock:
            trial = self._trials.get(trial_id)
            if trial is None:
                return None
            sites = [s for s in self._sites.values() if s.trial_id == trial_id]
            patients = [p for p in self._patients.values() if p.trial_id == trial_id]

        total_enrolled = sum(1 for p in patients if p.status not in (PatientStatus.SCREENING, PatientStatus.SCREEN_FAILED))
        screen_failures = sum(1 for p in patients if p.status == PatientStatus.SCREEN_FAILED)
        total_screened = len(patients)
        active_patients = sum(1 for p in patients if p.status == PatientStatus.ACTIVE)
        completed_patients = sum(1 for p in patients if p.status == PatientStatus.COMPLETED)
        withdrawn_patients = sum(1 for p in patients if p.status == PatientStatus.WITHDRAWN)

        sf_rate = round((screen_failures / total_screened * 100) if total_screened > 0 else 0.0, 1)
        enrollment_rate = round((total_enrolled / trial.target_enrollment * 100) if trial.target_enrollment > 0 else 0.0, 1)

        return {
            "trial_id": trial_id,
            "protocol_number": trial.protocol_number,
            "target_enrollment": trial.target_enrollment,
            "total_screened": total_screened,
            "total_enrolled": total_enrolled,
            "screen_failures": screen_failures,
            "screen_failure_rate": sf_rate,
            "enrollment_rate": enrollment_rate,
            "active_patients": active_patients,
            "completed_patients": completed_patients,
            "withdrawn_patients": withdrawn_patients,
            "sites_active": len([s for s in sites if s.status in (SiteStatus.ACTIVE, SiteStatus.ENROLLING)]),
            "sites_total": len(sites),
        }

    # ------------------------------------------------------------------
    # Site Enrollment (for a site)
    # ------------------------------------------------------------------

    def get_site_enrollment(self, site_id: str) -> dict | None:
        """Get enrollment details for a specific site."""
        with self._lock:
            site = self._sites.get(site_id)
            if site is None:
                return None
            patients = [p for p in self._patients.values() if p.site_id == site_id]

        enrolled = sum(1 for p in patients if p.status not in (PatientStatus.SCREENING, PatientStatus.SCREEN_FAILED))
        screen_failures = sum(1 for p in patients if p.status == PatientStatus.SCREEN_FAILED)
        total_screened = len(patients)
        sf_rate = round((screen_failures / total_screened * 100) if total_screened > 0 else 0.0, 1)

        return {
            "site_id": site_id,
            "site_name": site.name,
            "pi_name": site.pi_name,
            "enrollment_target": site.enrollment_target,
            "enrolled": enrolled,
            "screen_failures": screen_failures,
            "total_screened": total_screened,
            "screen_failure_rate": sf_rate,
            "patients_by_status": {
                status.value: sum(1 for p in patients if p.status == status)
                for status in PatientStatus
                if any(p.status == status for p in patients)
            },
        }

    # ------------------------------------------------------------------
    # Visit Compliance
    # ------------------------------------------------------------------

    def get_visit_compliance(self, trial_id: str) -> dict | None:
        """Get visit compliance metrics for a trial."""
        with self._lock:
            trial = self._trials.get(trial_id)
            if trial is None:
                return None
            visits = [v for v in self._visits.values() if v.trial_id == trial_id]

        total = len(visits)
        completed = sum(1 for v in visits if v.status == VisitStatus.COMPLETED)
        out_of_window = sum(1 for v in visits if v.status == VisitStatus.OUT_OF_WINDOW)
        missed = sum(1 for v in visits if v.status == VisitStatus.MISSED)
        scheduled = sum(1 for v in visits if v.status == VisitStatus.SCHEDULED)
        sdv_done = sum(1 for v in visits if v.source_data_verified)
        sdv_eligible = sum(1 for v in visits if v.status in (VisitStatus.COMPLETED, VisitStatus.OUT_OF_WINDOW))

        compliance_rate = round((completed / (completed + out_of_window + missed) * 100) if (completed + out_of_window + missed) > 0 else 0.0, 1)
        sdv_rate = round((sdv_done / sdv_eligible * 100) if sdv_eligible > 0 else 0.0, 1)

        return {
            "trial_id": trial_id,
            "total_visits": total,
            "completed": completed,
            "out_of_window": out_of_window,
            "missed": missed,
            "scheduled": scheduled,
            "compliance_rate": compliance_rate,
            "sdv_completed": sdv_done,
            "sdv_eligible": sdv_eligible,
            "sdv_rate": sdv_rate,
        }

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> CTMSMetrics:
        """Compute aggregated CTMS operational metrics."""
        with self._lock:
            trials = list(self._trials.values())
            sites = list(self._sites.values())
            patients = list(self._patients.values())

        # Trials by phase
        by_phase: dict[str, int] = {}
        for t in trials:
            key = t.phase.value
            by_phase[key] = by_phase.get(key, 0) + 1

        # Trials by status
        by_status: dict[str, int] = {}
        for t in trials:
            key = t.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Enrollment rate
        total_target = sum(t.target_enrollment for t in trials)
        total_enrolled = sum(t.current_enrollment for t in trials)
        avg_enrollment_rate = round(
            (total_enrolled / total_target * 100) if total_target > 0 else 0.0, 1
        )

        # Screen failure rate
        screen_failures = sum(1 for p in patients if p.status == PatientStatus.SCREEN_FAILED)
        total_patients = len(patients)
        sf_rate = round(
            (screen_failures / total_patients * 100) if total_patients > 0 else 0.0, 1
        )

        return CTMSMetrics(
            total_trials=len(trials),
            trials_by_phase=by_phase,
            trials_by_status=by_status,
            total_patients=total_patients,
            total_sites=len(sites),
            avg_enrollment_rate=avg_enrollment_rate,
            screen_failure_rate_overall=sf_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CTMSService | None = None
_instance_lock = threading.Lock()


def get_ctms_service() -> CTMSService:
    """Return the singleton CTMSService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CTMSService()
    return _instance


def reset_ctms_service() -> CTMSService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CTMSService()
    return _instance
