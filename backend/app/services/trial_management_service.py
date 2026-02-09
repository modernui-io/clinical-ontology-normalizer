"""Trial Management Office (TMO) & Multi-Site Coordination Service (CLINICAL-10).

Manages TMO operations: site activation tracking, country regulatory status,
trial milestones with critical path analysis, site communications with
acknowledgment tracking, blocker management with auto-escalation, cross-trial
resource allocation, enrollment forecasting, and TMO dashboard aggregation.

Usage:
    from app.services.trial_management_service import get_tmo_service

    svc = get_tmo_service()
    dashboard = svc.get_dashboard("trial-id")
    critical_path = svc.get_critical_path("trial-id")
"""

from __future__ import annotations

import logging
import math
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.trial_management import (
    CommunicationType,
    CountryRegulatory,
    CountryStatus,
    CountryStatusUpdate,
    CriticalPathResult,
    CrossTrialResource,
    CrossTrialResourceCreate,
    EnrollmentProjection,
    GanttChartData,
    GanttItem,
    MilestoneCategory,
    MilestoneStatus,
    ResourceUtilization,
    SiteActivation,
    SiteActivationStatus,
    SiteActivationUpdate,
    SiteBlocker,
    SiteBlockerCreate,
    SiteCommunication,
    SiteCommunicationCreate,
    TMODashboard,
    TrialMilestone,
    TrialMilestoneCreate,
    TrialMilestoneUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Blocker escalation threshold
BLOCKER_ESCALATION_DAYS = 14

# Delay threshold for site activations (days)
SITE_ACTIVATION_DELAY_THRESHOLD_DAYS = 14

# Enrollment targets by trial
ENROLLMENT_TARGETS = {
    EYLEA_TRIAL: 600,
    DUPIXENT_TRIAL: 400,
    LIBTAYO_TRIAL: 300,
}

# Current enrollment counts (simulated)
CURRENT_ENROLLMENT = {
    EYLEA_TRIAL: 342,
    DUPIXENT_TRIAL: 218,
    LIBTAYO_TRIAL: 145,
}

# Valid site activation status transitions
VALID_SITE_TRANSITIONS: dict[SiteActivationStatus, set[SiteActivationStatus]] = {
    SiteActivationStatus.PLANNED: {SiteActivationStatus.REGULATORY_SUBMITTED},
    SiteActivationStatus.REGULATORY_SUBMITTED: {SiteActivationStatus.IRB_APPROVED},
    SiteActivationStatus.IRB_APPROVED: {SiteActivationStatus.CONTRACTS_EXECUTED},
    SiteActivationStatus.CONTRACTS_EXECUTED: {SiteActivationStatus.SITE_INITIATED},
    SiteActivationStatus.SITE_INITIATED: {SiteActivationStatus.ENROLLING},
    SiteActivationStatus.ENROLLING: {SiteActivationStatus.ENROLLMENT_COMPLETE, SiteActivationStatus.CLOSED},
    SiteActivationStatus.ENROLLMENT_COMPLETE: {SiteActivationStatus.CLOSED},
    SiteActivationStatus.CLOSED: set(),
}


class TrialManagementService:
    """In-memory TMO management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._site_activations: dict[str, SiteActivation] = {}
        self._country_regulatory: dict[str, CountryRegulatory] = {}
        self._milestones: dict[str, TrialMilestone] = {}
        self._communications: dict[str, SiteCommunication] = {}
        self._blockers: dict[str, SiteBlocker] = {}
        self._resources: dict[str, CrossTrialResource] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic TMO data across 3 Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 30 Site Activations across 3 trials ---
        sites_data = self._generate_site_activations(now)
        for s in sites_data:
            self._site_activations[s["id"]] = SiteActivation(**s)

        # --- 8 Country Regulatory submissions ---
        countries_data = self._generate_country_regulatory(now)
        for c in countries_data:
            self._country_regulatory[c["id"]] = CountryRegulatory(**c)

        # --- 40 Milestones with dependencies ---
        milestones_data = self._generate_milestones(now)
        for m in milestones_data:
            self._milestones[m["id"]] = TrialMilestone(**m)

        # --- 15 Site Communications ---
        comms_data = self._generate_communications(now)
        for c in comms_data:
            self._communications[c["id"]] = SiteCommunication(**c)

        # --- 8 Blockers (3 resolved, 5 open) ---
        blockers_data = self._generate_blockers(now)
        for b in blockers_data:
            self._blockers[b["id"]] = SiteBlocker(**b)

        # --- 10 Cross-trial Resources ---
        resources_data = self._generate_resources(now)
        for r in resources_data:
            self._resources[r["id"]] = CrossTrialResource(**r)

        logger.info(
            "TMO service seeded: %d sites, %d countries, %d milestones, "
            "%d comms, %d blockers, %d resources",
            len(self._site_activations),
            len(self._country_regulatory),
            len(self._milestones),
            len(self._communications),
            len(self._blockers),
            len(self._resources),
        )

    def _generate_site_activations(self, now: datetime) -> list[dict]:
        """Generate 30 site activations across 3 trials."""
        sites = []

        # EYLEA HD: 12 sites - US(6), EU(4), Japan(2)
        eylea_sites = [
            ("SITE-EYL-001", "Massachusetts Eye and Ear", "US", SiteActivationStatus.ENROLLING),
            ("SITE-EYL-002", "Bascom Palmer Eye Institute", "US", SiteActivationStatus.ENROLLING),
            ("SITE-EYL-003", "Wills Eye Hospital", "US", SiteActivationStatus.ENROLLING),
            ("SITE-EYL-004", "Jules Stein Eye Institute", "US", SiteActivationStatus.SITE_INITIATED),
            ("SITE-EYL-005", "Duke Eye Center", "US", SiteActivationStatus.CONTRACTS_EXECUTED),
            ("SITE-EYL-006", "Cleveland Clinic Cole Eye Institute", "US", SiteActivationStatus.IRB_APPROVED),
            ("SITE-EYL-007", "Moorfields Eye Hospital", "UK", SiteActivationStatus.ENROLLING),
            ("SITE-EYL-008", "Charite Berlin Ophthalmology", "DE", SiteActivationStatus.SITE_INITIATED),
            ("SITE-EYL-009", "Hopital des Quinze-Vingts", "FR", SiteActivationStatus.CONTRACTS_EXECUTED),
            ("SITE-EYL-010", "San Raffaele Hospital", "IT", SiteActivationStatus.REGULATORY_SUBMITTED),
            ("SITE-EYL-011", "University of Tokyo Hospital", "JP", SiteActivationStatus.ENROLLING),
            ("SITE-EYL-012", "Kyoto University Hospital", "JP", SiteActivationStatus.SITE_INITIATED),
        ]
        for sid, name, country, status in eylea_sites:
            site = self._make_site_dict(sid, name, EYLEA_TRIAL, country, status, now)
            sites.append(site)

        # Dupixent AD: 10 sites - US(5), EU(3), Australia(2)
        dupixent_sites = [
            ("SITE-DUP-001", "Mount Sinai Dermatology", "US", SiteActivationStatus.ENROLLING),
            ("SITE-DUP-002", "Northwestern Dermatology", "US", SiteActivationStatus.ENROLLING),
            ("SITE-DUP-003", "UCSF Dermatology", "US", SiteActivationStatus.ENROLLING),
            ("SITE-DUP-004", "Penn Dermatology", "US", SiteActivationStatus.SITE_INITIATED),
            ("SITE-DUP-005", "Johns Hopkins Dermatology", "US", SiteActivationStatus.CONTRACTS_EXECUTED),
            ("SITE-DUP-006", "St Thomas Hospital London", "UK", SiteActivationStatus.ENROLLING),
            ("SITE-DUP-007", "University Hospital Zurich", "CH", SiteActivationStatus.SITE_INITIATED),
            ("SITE-DUP-008", "Academic Medical Center Amsterdam", "NL", SiteActivationStatus.IRB_APPROVED),
            ("SITE-DUP-009", "Royal Melbourne Hospital", "AU", SiteActivationStatus.ENROLLING),
            ("SITE-DUP-010", "Sydney Dermatology Institute", "AU", SiteActivationStatus.CONTRACTS_EXECUTED),
        ]
        for sid, name, country, status in dupixent_sites:
            site = self._make_site_dict(sid, name, DUPIXENT_TRIAL, country, status, now)
            sites.append(site)

        # Libtayo CSCC: 8 sites - US(4), EU(3), Canada(1)
        libtayo_sites = [
            ("SITE-LIB-001", "Memorial Sloan Kettering", "US", SiteActivationStatus.ENROLLING),
            ("SITE-LIB-002", "MD Anderson Cancer Center", "US", SiteActivationStatus.ENROLLING),
            ("SITE-LIB-003", "Dana-Farber Cancer Institute", "US", SiteActivationStatus.SITE_INITIATED),
            ("SITE-LIB-004", "Mayo Clinic Oncology", "US", SiteActivationStatus.ENROLLING),
            ("SITE-LIB-005", "Gustave Roussy", "FR", SiteActivationStatus.ENROLLING),
            ("SITE-LIB-006", "University Hospital Munich", "DE", SiteActivationStatus.SITE_INITIATED),
            ("SITE-LIB-007", "Istituto Nazionale Tumori", "IT", SiteActivationStatus.CONTRACTS_EXECUTED),
            ("SITE-LIB-008", "Princess Margaret Cancer Centre", "CA", SiteActivationStatus.ENROLLING),
        ]
        for sid, name, country, status in libtayo_sites:
            site = self._make_site_dict(sid, name, LIBTAYO_TRIAL, country, status, now)
            sites.append(site)

        return sites

    def _make_site_dict(
        self, sid: str, name: str, trial_id: str, country: str,
        status: SiteActivationStatus, now: datetime,
    ) -> dict:
        """Create a site activation dictionary based on status."""
        base_offset = hash(sid) % 180  # Deterministic offset based on site ID

        planned = now - timedelta(days=180 + base_offset % 60)
        irb = None
        contract = None
        actual = None
        first_patient = None
        milestones_list: list[str] = []

        if status.value in ("irb_approved", "contracts_executed", "site_initiated", "enrolling", "enrollment_complete", "closed"):
            irb = planned + timedelta(days=30 + base_offset % 20)
            milestones_list.append("IRB Approved")

        if status.value in ("contracts_executed", "site_initiated", "enrolling", "enrollment_complete", "closed"):
            contract = irb + timedelta(days=15 + base_offset % 10) if irb else None
            milestones_list.append("Contract Executed")

        if status.value in ("site_initiated", "enrolling", "enrollment_complete", "closed"):
            actual = contract + timedelta(days=10 + base_offset % 7) if contract else None
            milestones_list.append("Site Initiated")

        if status.value in ("enrolling", "enrollment_complete", "closed"):
            first_patient = actual + timedelta(days=7 + base_offset % 14) if actual else None
            milestones_list.append("First Patient Enrolled")

        return {
            "id": sid,
            "site_id": sid,
            "site_name": name,
            "trial_id": trial_id,
            "country": country,
            "status": status,
            "planned_activation_date": planned,
            "actual_activation_date": actual,
            "irb_approval_date": irb,
            "contract_execution_date": contract,
            "first_patient_date": first_patient,
            "milestones": milestones_list,
            "blockers": [],
        }

    def _generate_country_regulatory(self, now: datetime) -> list[dict]:
        """Generate 8 country regulatory submissions."""
        return [
            {
                "id": "CR-001",
                "country_code": "US",
                "country_name": "United States",
                "trial_id": EYLEA_TRIAL,
                "status": CountryStatus.ACTIVE,
                "regulatory_body": "FDA",
                "submission_date": now - timedelta(days=300),
                "approval_date": now - timedelta(days=240),
                "import_license_date": None,
                "data_privacy_approval": True,
                "local_requirements": ["FDA IND submission", "21 CFR Part 11 compliance"],
            },
            {
                "id": "CR-002",
                "country_code": "UK",
                "country_name": "United Kingdom",
                "trial_id": EYLEA_TRIAL,
                "status": CountryStatus.ACTIVE,
                "regulatory_body": "MHRA",
                "submission_date": now - timedelta(days=280),
                "approval_date": now - timedelta(days=210),
                "import_license_date": now - timedelta(days=200),
                "data_privacy_approval": True,
                "local_requirements": ["UK GDPR compliance", "MHRA CTA approval"],
            },
            {
                "id": "CR-003",
                "country_code": "DE",
                "country_name": "Germany",
                "trial_id": EYLEA_TRIAL,
                "status": CountryStatus.APPROVED,
                "regulatory_body": "BfArM",
                "submission_date": now - timedelta(days=260),
                "approval_date": now - timedelta(days=180),
                "import_license_date": now - timedelta(days=170),
                "data_privacy_approval": True,
                "local_requirements": ["EU-CTR compliance", "Ethics Committee approval", "GDPR DPA"],
            },
            {
                "id": "CR-004",
                "country_code": "JP",
                "country_name": "Japan",
                "trial_id": EYLEA_TRIAL,
                "status": CountryStatus.ACTIVE,
                "regulatory_body": "PMDA",
                "submission_date": now - timedelta(days=250),
                "approval_date": now - timedelta(days=160),
                "import_license_date": now - timedelta(days=150),
                "data_privacy_approval": True,
                "local_requirements": ["PMDA CTN submission", "J-GCP compliance", "Import license"],
            },
            {
                "id": "CR-005",
                "country_code": "US",
                "country_name": "United States",
                "trial_id": DUPIXENT_TRIAL,
                "status": CountryStatus.ACTIVE,
                "regulatory_body": "FDA",
                "submission_date": now - timedelta(days=270),
                "approval_date": now - timedelta(days=210),
                "import_license_date": None,
                "data_privacy_approval": True,
                "local_requirements": ["FDA IND submission", "21 CFR Part 11 compliance"],
            },
            {
                "id": "CR-006",
                "country_code": "AU",
                "country_name": "Australia",
                "trial_id": DUPIXENT_TRIAL,
                "status": CountryStatus.APPROVED,
                "regulatory_body": "TGA",
                "submission_date": now - timedelta(days=240),
                "approval_date": now - timedelta(days=170),
                "import_license_date": now - timedelta(days=160),
                "data_privacy_approval": True,
                "local_requirements": ["TGA CTN scheme", "HREC approval"],
            },
            {
                "id": "CR-007",
                "country_code": "US",
                "country_name": "United States",
                "trial_id": LIBTAYO_TRIAL,
                "status": CountryStatus.ACTIVE,
                "regulatory_body": "FDA",
                "submission_date": now - timedelta(days=290),
                "approval_date": now - timedelta(days=220),
                "import_license_date": None,
                "data_privacy_approval": True,
                "local_requirements": ["FDA IND submission", "21 CFR Part 11 compliance"],
            },
            {
                "id": "CR-008",
                "country_code": "CA",
                "country_name": "Canada",
                "trial_id": LIBTAYO_TRIAL,
                "status": CountryStatus.ACTIVE,
                "regulatory_body": "Health Canada",
                "submission_date": now - timedelta(days=260),
                "approval_date": now - timedelta(days=190),
                "import_license_date": now - timedelta(days=180),
                "data_privacy_approval": True,
                "local_requirements": ["CTA filing", "REB approval", "PIPEDA compliance"],
            },
        ]

    def _generate_milestones(self, now: datetime) -> list[dict]:
        """Generate 40 milestones with dependencies across 3 trials."""
        milestones = []

        # --- EYLEA HD milestones (15) ---
        eylea_ms = [
            ("MS-EYL-001", "Regulatory submission (US)", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=300), now - timedelta(days=295), "Regulatory Affairs", [], 100.0),
            ("MS-EYL-002", "FDA IND approval", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=250), now - timedelta(days=240), "Regulatory Affairs", ["MS-EYL-001"], 100.0),
            ("MS-EYL-003", "First site activated (US)", MilestoneCategory.SITE_ACTIVATION, MilestoneStatus.COMPLETED, now - timedelta(days=200), now - timedelta(days=195), "Site Management", ["MS-EYL-002"], 100.0),
            ("MS-EYL-004", "EU regulatory submission", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=280), now - timedelta(days=275), "Regulatory Affairs", ["MS-EYL-001"], 100.0),
            ("MS-EYL-005", "EU CTA approval", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=220), now - timedelta(days=210), "Regulatory Affairs", ["MS-EYL-004"], 100.0),
            ("MS-EYL-006", "Japan PMDA submission", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=260), now - timedelta(days=255), "Regulatory Affairs", [], 100.0),
            ("MS-EYL-007", "Japan PMDA approval", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=170), now - timedelta(days=160), "Regulatory Affairs", ["MS-EYL-006"], 100.0),
            ("MS-EYL-008", "First patient enrolled", MilestoneCategory.ENROLLMENT, MilestoneStatus.COMPLETED, now - timedelta(days=150), now - timedelta(days=148), "Clinical Operations", ["MS-EYL-003"], 100.0),
            ("MS-EYL-009", "25% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.COMPLETED, now - timedelta(days=90), now - timedelta(days=85), "Clinical Operations", ["MS-EYL-008"], 100.0),
            ("MS-EYL-010", "50% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.IN_PROGRESS, now - timedelta(days=20), None, "Clinical Operations", ["MS-EYL-009"], 75.0),
            ("MS-EYL-011", "75% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.NOT_STARTED, now + timedelta(days=60), None, "Clinical Operations", ["MS-EYL-010"], 0.0),
            ("MS-EYL-012", "100% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.NOT_STARTED, now + timedelta(days=120), None, "Clinical Operations", ["MS-EYL-011"], 0.0),
            ("MS-EYL-013", "Interim safety analysis", MilestoneCategory.SAFETY, MilestoneStatus.DELAYED, now - timedelta(days=30), None, "Biostatistics", ["MS-EYL-010"], 40.0),
            ("MS-EYL-014", "Database lock", MilestoneCategory.DATA, MilestoneStatus.NOT_STARTED, now + timedelta(days=180), None, "Data Management", ["MS-EYL-012"], 0.0),
            ("MS-EYL-015", "Final study report", MilestoneCategory.REPORTING, MilestoneStatus.NOT_STARTED, now + timedelta(days=240), None, "Medical Writing", ["MS-EYL-014"], 0.0),
        ]

        for mid, name, cat, status, planned, actual, party, deps, pct in eylea_ms:
            milestones.append({
                "id": mid, "trial_id": EYLEA_TRIAL, "name": name,
                "category": cat, "status": status, "planned_date": planned,
                "actual_date": actual, "responsible_party": party,
                "dependencies": deps, "percent_complete": pct,
            })

        # --- Dupixent AD milestones (13) ---
        dup_ms = [
            ("MS-DUP-001", "Regulatory submission (US)", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=280), now - timedelta(days=275), "Regulatory Affairs", [], 100.0),
            ("MS-DUP-002", "FDA IND approval", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=220), now - timedelta(days=210), "Regulatory Affairs", ["MS-DUP-001"], 100.0),
            ("MS-DUP-003", "First site activated (US)", MilestoneCategory.SITE_ACTIVATION, MilestoneStatus.COMPLETED, now - timedelta(days=180), now - timedelta(days=175), "Site Management", ["MS-DUP-002"], 100.0),
            ("MS-DUP-004", "Australia TGA submission", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=250), now - timedelta(days=245), "Regulatory Affairs", [], 100.0),
            ("MS-DUP-005", "TGA approval", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=180), now - timedelta(days=170), "Regulatory Affairs", ["MS-DUP-004"], 100.0),
            ("MS-DUP-006", "First patient enrolled", MilestoneCategory.ENROLLMENT, MilestoneStatus.COMPLETED, now - timedelta(days=140), now - timedelta(days=138), "Clinical Operations", ["MS-DUP-003"], 100.0),
            ("MS-DUP-007", "25% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.COMPLETED, now - timedelta(days=70), now - timedelta(days=65), "Clinical Operations", ["MS-DUP-006"], 100.0),
            ("MS-DUP-008", "50% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.IN_PROGRESS, now - timedelta(days=10), None, "Clinical Operations", ["MS-DUP-007"], 80.0),
            ("MS-DUP-009", "75% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.NOT_STARTED, now + timedelta(days=50), None, "Clinical Operations", ["MS-DUP-008"], 0.0),
            ("MS-DUP-010", "100% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.NOT_STARTED, now + timedelta(days=110), None, "Clinical Operations", ["MS-DUP-009"], 0.0),
            ("MS-DUP-011", "Interim analysis", MilestoneCategory.SAFETY, MilestoneStatus.AT_RISK, now + timedelta(days=20), None, "Biostatistics", ["MS-DUP-008"], 30.0),
            ("MS-DUP-012", "Database lock", MilestoneCategory.DATA, MilestoneStatus.NOT_STARTED, now + timedelta(days=170), None, "Data Management", ["MS-DUP-010"], 0.0),
            ("MS-DUP-013", "Final study report", MilestoneCategory.REPORTING, MilestoneStatus.NOT_STARTED, now + timedelta(days=230), None, "Medical Writing", ["MS-DUP-012"], 0.0),
        ]

        for mid, name, cat, status, planned, actual, party, deps, pct in dup_ms:
            milestones.append({
                "id": mid, "trial_id": DUPIXENT_TRIAL, "name": name,
                "category": cat, "status": status, "planned_date": planned,
                "actual_date": actual, "responsible_party": party,
                "dependencies": deps, "percent_complete": pct,
            })

        # --- Libtayo CSCC milestones (12) ---
        lib_ms = [
            ("MS-LIB-001", "Regulatory submission (US)", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=300), now - timedelta(days=295), "Regulatory Affairs", [], 100.0),
            ("MS-LIB-002", "FDA IND approval", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=230), now - timedelta(days=220), "Regulatory Affairs", ["MS-LIB-001"], 100.0),
            ("MS-LIB-003", "Canada CTA submission", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=270), now - timedelta(days=265), "Regulatory Affairs", [], 100.0),
            ("MS-LIB-004", "Canada CTA approval", MilestoneCategory.REGULATORY, MilestoneStatus.COMPLETED, now - timedelta(days=200), now - timedelta(days=190), "Regulatory Affairs", ["MS-LIB-003"], 100.0),
            ("MS-LIB-005", "First site activated", MilestoneCategory.SITE_ACTIVATION, MilestoneStatus.COMPLETED, now - timedelta(days=180), now - timedelta(days=175), "Site Management", ["MS-LIB-002"], 100.0),
            ("MS-LIB-006", "First patient enrolled", MilestoneCategory.ENROLLMENT, MilestoneStatus.COMPLETED, now - timedelta(days=140), now - timedelta(days=135), "Clinical Operations", ["MS-LIB-005"], 100.0),
            ("MS-LIB-007", "25% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.COMPLETED, now - timedelta(days=60), now - timedelta(days=55), "Clinical Operations", ["MS-LIB-006"], 100.0),
            ("MS-LIB-008", "50% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.IN_PROGRESS, now + timedelta(days=10), None, "Clinical Operations", ["MS-LIB-007"], 65.0),
            ("MS-LIB-009", "75% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.NOT_STARTED, now + timedelta(days=70), None, "Clinical Operations", ["MS-LIB-008"], 0.0),
            ("MS-LIB-010", "100% enrollment target", MilestoneCategory.ENROLLMENT, MilestoneStatus.NOT_STARTED, now + timedelta(days=130), None, "Clinical Operations", ["MS-LIB-009"], 0.0),
            ("MS-LIB-011", "Database lock", MilestoneCategory.DATA, MilestoneStatus.NOT_STARTED, now + timedelta(days=190), None, "Data Management", ["MS-LIB-010"], 0.0),
            ("MS-LIB-012", "Final study report", MilestoneCategory.REPORTING, MilestoneStatus.NOT_STARTED, now + timedelta(days=250), None, "Medical Writing", ["MS-LIB-011"], 0.0),
        ]

        for mid, name, cat, status, planned, actual, party, deps, pct in lib_ms:
            milestones.append({
                "id": mid, "trial_id": LIBTAYO_TRIAL, "name": name,
                "category": cat, "status": status, "planned_date": planned,
                "actual_date": actual, "responsible_party": party,
                "dependencies": deps, "percent_complete": pct,
            })

        return milestones

    def _generate_communications(self, now: datetime) -> list[dict]:
        """Generate 15 site communications."""
        eylea_sites = [f"SITE-EYL-{i:03d}" for i in range(1, 13)]
        dup_sites = [f"SITE-DUP-{i:03d}" for i in range(1, 11)]
        lib_sites = [f"SITE-LIB-{i:03d}" for i in range(1, 9)]

        comms = [
            {
                "id": "COMM-001", "trial_id": EYLEA_TRIAL,
                "type": CommunicationType.NEWSLETTER,
                "subject": "EYLEA HD Trial Monthly Newsletter - January 2026",
                "body": "Enrollment update: 342 of 600 target enrolled. Site activation on track in all regions.",
                "sent_date": now - timedelta(days=10),
                "recipients": eylea_sites,
                "acknowledgments": eylea_sites[:8],
                "requires_acknowledgment": False,
            },
            {
                "id": "COMM-002", "trial_id": EYLEA_TRIAL,
                "type": CommunicationType.PROTOCOL_AMENDMENT,
                "subject": "Protocol Amendment 3 - Updated Inclusion Criteria",
                "body": "Amendment 3 expands age range to 18-85 and adds new secondary endpoint.",
                "sent_date": now - timedelta(days=30),
                "recipients": eylea_sites,
                "acknowledgments": eylea_sites[:10],
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-003", "trial_id": EYLEA_TRIAL,
                "type": CommunicationType.SAFETY_LETTER,
                "subject": "Safety Update - Updated Adverse Event Reporting Requirements",
                "body": "New AE reporting requirements effective immediately per DSMB recommendation.",
                "sent_date": now - timedelta(days=45),
                "recipients": eylea_sites,
                "acknowledgments": eylea_sites,
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-004", "trial_id": EYLEA_TRIAL,
                "type": CommunicationType.TRAINING_BULLETIN,
                "subject": "Updated EDC Training Materials Available",
                "body": "New EDC system training modules are available in the site portal.",
                "sent_date": now - timedelta(days=60),
                "recipients": eylea_sites,
                "acknowledgments": eylea_sites[:6],
                "requires_acknowledgment": False,
            },
            {
                "id": "COMM-005", "trial_id": EYLEA_TRIAL,
                "type": CommunicationType.ALERT,
                "subject": "Supply Chain Alert - IMP Shipment Delay to EU Sites",
                "body": "IMP shipments to EU sites delayed by 5 business days due to customs processing.",
                "sent_date": now - timedelta(days=15),
                "recipients": [s for s in eylea_sites if "EYL-007" <= s <= "EYL-010"],
                "acknowledgments": ["SITE-EYL-007"],
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-006", "trial_id": DUPIXENT_TRIAL,
                "type": CommunicationType.NEWSLETTER,
                "subject": "Dupixent AD Trial Quarterly Update",
                "body": "Enrollment at 218 of 400 target. Two new sites activated in Australia.",
                "sent_date": now - timedelta(days=7),
                "recipients": dup_sites,
                "acknowledgments": dup_sites[:5],
                "requires_acknowledgment": False,
            },
            {
                "id": "COMM-007", "trial_id": DUPIXENT_TRIAL,
                "type": CommunicationType.MEMO,
                "subject": "Site Monitoring Visit Schedule Q1 2026",
                "body": "Monitoring visits scheduled for all active sites. See attached schedule.",
                "sent_date": now - timedelta(days=20),
                "recipients": dup_sites,
                "acknowledgments": dup_sites[:7],
                "requires_acknowledgment": False,
            },
            {
                "id": "COMM-008", "trial_id": DUPIXENT_TRIAL,
                "type": CommunicationType.PROTOCOL_AMENDMENT,
                "subject": "Protocol Amendment 2 - Dosing Schedule Clarification",
                "body": "Clarification on dosing intervals for patients with renal impairment.",
                "sent_date": now - timedelta(days=50),
                "recipients": dup_sites,
                "acknowledgments": dup_sites,
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-009", "trial_id": DUPIXENT_TRIAL,
                "type": CommunicationType.SAFETY_LETTER,
                "subject": "Updated Investigator Brochure - Section 5 Revision",
                "body": "IB updated with new safety data from ongoing studies.",
                "sent_date": now - timedelta(days=35),
                "recipients": dup_sites,
                "acknowledgments": dup_sites[:8],
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-010", "trial_id": DUPIXENT_TRIAL,
                "type": CommunicationType.TRAINING_BULLETIN,
                "subject": "New IWRS System Training Required",
                "body": "All site staff must complete IWRS training by end of month.",
                "sent_date": now - timedelta(days=25),
                "recipients": dup_sites,
                "acknowledgments": dup_sites[:4],
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-011", "trial_id": LIBTAYO_TRIAL,
                "type": CommunicationType.NEWSLETTER,
                "subject": "Libtayo CSCC Trial Monthly Update",
                "body": "Enrollment at 145 of 300 target. Strong enrollment in US and Canada sites.",
                "sent_date": now - timedelta(days=5),
                "recipients": lib_sites,
                "acknowledgments": lib_sites[:4],
                "requires_acknowledgment": False,
            },
            {
                "id": "COMM-012", "trial_id": LIBTAYO_TRIAL,
                "type": CommunicationType.ALERT,
                "subject": "Urgent: Protocol Deviation Reporting Reminder",
                "body": "All protocol deviations must be reported within 24 hours per ICH-GCP.",
                "sent_date": now - timedelta(days=18),
                "recipients": lib_sites,
                "acknowledgments": lib_sites[:6],
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-013", "trial_id": LIBTAYO_TRIAL,
                "type": CommunicationType.MEMO,
                "subject": "Updated Informed Consent Form Available",
                "body": "ICF version 4.0 is available for download. All sites must implement within 30 days.",
                "sent_date": now - timedelta(days=40),
                "recipients": lib_sites,
                "acknowledgments": lib_sites,
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-014", "trial_id": LIBTAYO_TRIAL,
                "type": CommunicationType.SAFETY_LETTER,
                "subject": "SUSAR Report - Immune-Related Adverse Event",
                "body": "SUSAR notification per regulatory requirements. See attached case narrative.",
                "sent_date": now - timedelta(days=12),
                "recipients": lib_sites,
                "acknowledgments": lib_sites[:5],
                "requires_acknowledgment": True,
            },
            {
                "id": "COMM-015", "trial_id": LIBTAYO_TRIAL,
                "type": CommunicationType.TRAINING_BULLETIN,
                "subject": "Biomarker Sample Collection Training Update",
                "body": "Updated procedures for biomarker sample collection and shipment.",
                "sent_date": now - timedelta(days=55),
                "recipients": lib_sites,
                "acknowledgments": lib_sites[:3],
                "requires_acknowledgment": False,
            },
        ]

        return comms

    def _generate_blockers(self, now: datetime) -> list[dict]:
        """Generate 8 blockers (3 resolved, 5 open)."""
        return [
            # Resolved blockers
            {
                "id": "BLK-001", "site_id": "SITE-EYL-005", "trial_id": EYLEA_TRIAL,
                "description": "IRB approval delayed due to incomplete submission package",
                "category": "regulatory",
                "raised_date": now - timedelta(days=60),
                "resolved_date": now - timedelta(days=30),
                "impact_description": "Site activation delayed by 4 weeks",
                "escalated": True,
            },
            {
                "id": "BLK-002", "site_id": "SITE-DUP-005", "trial_id": DUPIXENT_TRIAL,
                "description": "Contract negotiation stalled over indemnification clause",
                "category": "contract",
                "raised_date": now - timedelta(days=45),
                "resolved_date": now - timedelta(days=20),
                "impact_description": "Contract execution delayed by 3 weeks",
                "escalated": True,
            },
            {
                "id": "BLK-003", "site_id": "SITE-LIB-007", "trial_id": LIBTAYO_TRIAL,
                "description": "Import license processing delay in Italy",
                "category": "regulatory",
                "raised_date": now - timedelta(days=40),
                "resolved_date": now - timedelta(days=10),
                "impact_description": "IMP delivery delayed by 2 weeks",
                "escalated": False,
            },
            # Open blockers
            {
                "id": "BLK-004", "site_id": "SITE-EYL-006", "trial_id": EYLEA_TRIAL,
                "description": "Site principal investigator on extended leave; replacement needed",
                "category": "staffing",
                "raised_date": now - timedelta(days=20),
                "resolved_date": None,
                "impact_description": "Cannot proceed to contract execution without PI signature",
                "escalated": True,
            },
            {
                "id": "BLK-005", "site_id": "SITE-EYL-010", "trial_id": EYLEA_TRIAL,
                "description": "Italian regulatory submission requires additional local documentation",
                "category": "regulatory",
                "raised_date": now - timedelta(days=15),
                "resolved_date": None,
                "impact_description": "Site activation delayed pending regulatory clarification",
                "escalated": True,
            },
            {
                "id": "BLK-006", "site_id": "SITE-DUP-008", "trial_id": DUPIXENT_TRIAL,
                "description": "Ethics committee requested protocol clarification",
                "category": "regulatory",
                "raised_date": now - timedelta(days=12),
                "resolved_date": None,
                "impact_description": "IRB approval pending committee re-review",
                "escalated": False,
            },
            {
                "id": "BLK-007", "site_id": "SITE-DUP-010", "trial_id": DUPIXENT_TRIAL,
                "description": "IMP storage temperature excursion during shipment",
                "category": "supply",
                "raised_date": now - timedelta(days=8),
                "resolved_date": None,
                "impact_description": "Replacement IMP shipment required; site start delayed by 2 weeks",
                "escalated": False,
            },
            {
                "id": "BLK-008", "site_id": "SITE-LIB-006", "trial_id": LIBTAYO_TRIAL,
                "description": "Local laboratory not yet qualified for central lab analysis",
                "category": "other",
                "raised_date": now - timedelta(days=18),
                "resolved_date": None,
                "impact_description": "Cannot begin enrollment until lab is qualified",
                "escalated": True,
            },
        ]

    def _generate_resources(self, now: datetime) -> list[dict]:
        """Generate 10 cross-trial resources."""
        return [
            {
                "id": "RES-001", "resource_name": "Dr. Sarah Mitchell",
                "role": "Clinical Research Associate",
                "assigned_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL],
                "utilization_pct": 85.0,
                "availability_start": now - timedelta(days=365),
                "skills": ["GCP", "Site Monitoring", "Protocol Training", "Ophthalmology"],
            },
            {
                "id": "RES-002", "resource_name": "James Rodriguez",
                "role": "Clinical Data Manager",
                "assigned_trials": [EYLEA_TRIAL, LIBTAYO_TRIAL],
                "utilization_pct": 92.0,
                "availability_start": now - timedelta(days=300),
                "skills": ["EDC Systems", "Data Review", "CDISC Standards", "Medical Coding"],
            },
            {
                "id": "RES-003", "resource_name": "Dr. Emily Nakamura",
                "role": "Medical Monitor",
                "assigned_trials": [EYLEA_TRIAL],
                "utilization_pct": 70.0,
                "availability_start": now - timedelta(days=400),
                "skills": ["Medical Review", "SAE Assessment", "Ophthalmology", "Clinical Oversight"],
            },
            {
                "id": "RES-004", "resource_name": "Michael Chen",
                "role": "Regulatory Affairs Specialist",
                "assigned_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "utilization_pct": 95.0,
                "availability_start": now - timedelta(days=500),
                "skills": ["FDA Submissions", "EU-CTR", "PMDA", "Health Canada"],
            },
            {
                "id": "RES-005", "resource_name": "Lisa Park",
                "role": "Clinical Research Associate",
                "assigned_trials": [DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "utilization_pct": 78.0,
                "availability_start": now - timedelta(days=250),
                "skills": ["GCP", "Site Monitoring", "Dermatology", "Oncology"],
            },
            {
                "id": "RES-006", "resource_name": "Dr. Thomas Weber",
                "role": "Biostatistician",
                "assigned_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL],
                "utilization_pct": 88.0,
                "availability_start": now - timedelta(days=350),
                "skills": ["Interim Analysis", "Group Sequential Design", "SAS", "R"],
            },
            {
                "id": "RES-007", "resource_name": "Anna Kowalski",
                "role": "Site Activation Lead",
                "assigned_trials": [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
                "utilization_pct": 97.0,
                "availability_start": now - timedelta(days=400),
                "skills": ["Site Selection", "Feasibility", "Contract Negotiation", "Regulatory Submissions"],
            },
            {
                "id": "RES-008", "resource_name": "Robert Williams",
                "role": "Supply Chain Coordinator",
                "assigned_trials": [EYLEA_TRIAL, LIBTAYO_TRIAL],
                "utilization_pct": 65.0,
                "availability_start": now - timedelta(days=200),
                "skills": ["IMP Management", "Cold Chain Logistics", "Import/Export", "IVRS"],
            },
            {
                "id": "RES-009", "resource_name": "Dr. Priya Sharma",
                "role": "Medical Monitor",
                "assigned_trials": [DUPIXENT_TRIAL],
                "utilization_pct": 55.0,
                "availability_start": now - timedelta(days=300),
                "skills": ["Medical Review", "SAE Assessment", "Dermatology", "Immunology"],
            },
            {
                "id": "RES-010", "resource_name": "David Kim",
                "role": "Clinical Trial Manager",
                "assigned_trials": [LIBTAYO_TRIAL],
                "utilization_pct": 25.0,
                "availability_start": now + timedelta(days=30),
                "skills": ["Trial Oversight", "Vendor Management", "Budget Management", "Oncology"],
            },
        ]

    # ------------------------------------------------------------------
    # Site Activations
    # ------------------------------------------------------------------

    def list_site_activations(
        self,
        trial_id: str | None = None,
        country: str | None = None,
        status: SiteActivationStatus | None = None,
    ) -> list[SiteActivation]:
        """List site activations with optional filtering."""
        with self._lock:
            items = list(self._site_activations.values())

        if trial_id:
            items = [s for s in items if s.trial_id == trial_id]
        if country:
            items = [s for s in items if s.country.lower() == country.lower()]
        if status:
            items = [s for s in items if s.status == status]

        return items

    def get_site_activation(self, site_id: str) -> SiteActivation | None:
        """Get a single site activation by ID."""
        with self._lock:
            return self._site_activations.get(site_id)

    def update_site_status(self, site_id: str, update: SiteActivationUpdate) -> SiteActivation:
        """Update a site activation status with transition validation."""
        with self._lock:
            site = self._site_activations.get(site_id)
            if site is None:
                raise ValueError(f"Site activation not found: {site_id}")

            current = site.status
            new_status = update.status

            valid_next = VALID_SITE_TRANSITIONS.get(current, set())
            if new_status not in valid_next:
                raise ValueError(
                    f"Invalid status transition from {current.value} to {new_status.value}. "
                    f"Valid transitions: {[s.value for s in valid_next]}"
                )

            now = datetime.now(timezone.utc)
            updated = site.model_copy(update={"status": new_status})

            # Set dates based on transition
            if new_status == SiteActivationStatus.IRB_APPROVED and updated.irb_approval_date is None:
                updated = updated.model_copy(update={"irb_approval_date": now})
            elif new_status == SiteActivationStatus.CONTRACTS_EXECUTED and updated.contract_execution_date is None:
                updated = updated.model_copy(update={"contract_execution_date": now})
            elif new_status == SiteActivationStatus.SITE_INITIATED and updated.actual_activation_date is None:
                updated = updated.model_copy(update={"actual_activation_date": now})
            elif new_status == SiteActivationStatus.ENROLLING and updated.first_patient_date is None:
                updated = updated.model_copy(update={"first_patient_date": now})

            self._site_activations[site_id] = updated
            return updated

    def get_delayed_sites(self) -> list[dict]:
        """Find sites where actual activation is delayed > 2 weeks from planned."""
        with self._lock:
            items = list(self._site_activations.values())

        delayed = []
        now = datetime.now(timezone.utc)
        for site in items:
            if site.planned_activation_date is None:
                continue
            if site.actual_activation_date:
                delay = (site.actual_activation_date - site.planned_activation_date).days
            elif site.status != SiteActivationStatus.CLOSED:
                delay = (now - site.planned_activation_date).days
            else:
                continue
            if delay > SITE_ACTIVATION_DELAY_THRESHOLD_DAYS:
                delayed.append({
                    "site_id": site.site_id,
                    "site_name": site.site_name,
                    "trial_id": site.trial_id,
                    "status": site.status.value,
                    "delay_days": delay,
                    "planned_date": site.planned_activation_date.isoformat(),
                    "actual_date": site.actual_activation_date.isoformat() if site.actual_activation_date else None,
                })
        return delayed

    # ------------------------------------------------------------------
    # Blockers
    # ------------------------------------------------------------------

    def list_blockers(
        self,
        trial_id: str | None = None,
        open_only: bool = False,
    ) -> list[SiteBlocker]:
        """List blockers with optional filtering."""
        with self._lock:
            items = list(self._blockers.values())

        if trial_id:
            items = [b for b in items if b.trial_id == trial_id]
        if open_only:
            items = [b for b in items if b.resolved_date is None]

        return items

    def get_blocker(self, blocker_id: str) -> SiteBlocker | None:
        """Get a single blocker by ID."""
        with self._lock:
            return self._blockers.get(blocker_id)

    def raise_blocker(self, site_id: str, trial_id: str, create: SiteBlockerCreate) -> SiteBlocker:
        """Raise a new blocker for a site."""
        now = datetime.now(timezone.utc)
        blocker_id = f"BLK-{uuid4().hex[:8].upper()}"

        blocker = SiteBlocker(
            id=blocker_id,
            site_id=site_id,
            trial_id=trial_id,
            description=create.description,
            category=create.category,
            raised_date=now,
            resolved_date=None,
            impact_description=create.impact_description,
            escalated=False,
        )

        with self._lock:
            self._blockers[blocker_id] = blocker
            # Add blocker reference to site
            site = self._site_activations.get(site_id)
            if site:
                updated_blockers = list(site.blockers) + [blocker_id]
                self._site_activations[site_id] = site.model_copy(
                    update={"blockers": updated_blockers}
                )

        return blocker

    def resolve_blocker(self, blocker_id: str) -> SiteBlocker:
        """Resolve a blocker."""
        with self._lock:
            blocker = self._blockers.get(blocker_id)
            if blocker is None:
                raise ValueError(f"Blocker not found: {blocker_id}")
            if blocker.resolved_date is not None:
                raise ValueError(f"Blocker already resolved: {blocker_id}")

            now = datetime.now(timezone.utc)
            updated = blocker.model_copy(update={"resolved_date": now})
            self._blockers[blocker_id] = updated
            return updated

    def auto_escalate_blockers(self) -> list[SiteBlocker]:
        """Auto-escalate blockers open > 14 days that are not already escalated."""
        now = datetime.now(timezone.utc)
        escalated = []

        with self._lock:
            for bid, blocker in self._blockers.items():
                if blocker.resolved_date is not None:
                    continue
                if blocker.escalated:
                    continue
                days_open = (now - blocker.raised_date).days
                if days_open > BLOCKER_ESCALATION_DAYS:
                    updated = blocker.model_copy(update={"escalated": True})
                    self._blockers[bid] = updated
                    escalated.append(updated)

        return escalated

    # ------------------------------------------------------------------
    # Country Regulatory
    # ------------------------------------------------------------------

    def list_country_regulatory(
        self,
        trial_id: str | None = None,
        status: CountryStatus | None = None,
    ) -> list[CountryRegulatory]:
        """List country regulatory records."""
        with self._lock:
            items = list(self._country_regulatory.values())

        if trial_id:
            items = [c for c in items if c.trial_id == trial_id]
        if status:
            items = [c for c in items if c.status == status]

        return items

    def get_country_regulatory(self, country_id: str) -> CountryRegulatory | None:
        """Get a single country regulatory record."""
        with self._lock:
            return self._country_regulatory.get(country_id)

    def update_country_status(self, country_id: str, update: CountryStatusUpdate) -> CountryRegulatory:
        """Update a country regulatory status."""
        with self._lock:
            record = self._country_regulatory.get(country_id)
            if record is None:
                raise ValueError(f"Country regulatory record not found: {country_id}")

            now = datetime.now(timezone.utc)
            updates: dict = {"status": update.status}

            if update.status == CountryStatus.APPROVED and record.approval_date is None:
                updates["approval_date"] = now

            updated = record.model_copy(update=updates)
            self._country_regulatory[country_id] = updated
            return updated

    # ------------------------------------------------------------------
    # Milestones
    # ------------------------------------------------------------------

    def list_milestones(
        self,
        trial_id: str | None = None,
        category: MilestoneCategory | None = None,
        status: MilestoneStatus | None = None,
    ) -> list[TrialMilestone]:
        """List milestones with optional filtering."""
        with self._lock:
            items = list(self._milestones.values())

        if trial_id:
            items = [m for m in items if m.trial_id == trial_id]
        if category:
            items = [m for m in items if m.category == category]
        if status:
            items = [m for m in items if m.status == status]

        return items

    def get_milestone(self, milestone_id: str) -> TrialMilestone | None:
        """Get a single milestone by ID."""
        with self._lock:
            return self._milestones.get(milestone_id)

    def create_milestone(self, create: TrialMilestoneCreate) -> TrialMilestone:
        """Create a new milestone."""
        mid = f"MS-NEW-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        milestone = TrialMilestone(
            id=mid,
            trial_id=create.trial_id,
            name=create.name,
            category=create.category,
            status=MilestoneStatus.NOT_STARTED,
            planned_date=create.planned_date,
            actual_date=None,
            responsible_party=create.responsible_party,
            dependencies=create.dependencies,
            percent_complete=0.0,
        )

        with self._lock:
            # Validate dependencies exist
            for dep_id in create.dependencies:
                if dep_id not in self._milestones:
                    raise ValueError(f"Dependency milestone not found: {dep_id}")
            self._milestones[mid] = milestone

        return milestone

    def update_milestone(self, milestone_id: str, update: TrialMilestoneUpdate) -> TrialMilestone:
        """Update a milestone."""
        with self._lock:
            milestone = self._milestones.get(milestone_id)
            if milestone is None:
                raise ValueError(f"Milestone not found: {milestone_id}")

            updates = {}
            if update.name is not None:
                updates["name"] = update.name
            if update.category is not None:
                updates["category"] = update.category
            if update.status is not None:
                updates["status"] = update.status
            if update.planned_date is not None:
                updates["planned_date"] = update.planned_date
            if update.actual_date is not None:
                updates["actual_date"] = update.actual_date
            if update.responsible_party is not None:
                updates["responsible_party"] = update.responsible_party
            if update.dependencies is not None:
                for dep_id in update.dependencies:
                    if dep_id not in self._milestones and dep_id != milestone_id:
                        raise ValueError(f"Dependency milestone not found: {dep_id}")
                updates["dependencies"] = update.dependencies
            if update.percent_complete is not None:
                updates["percent_complete"] = update.percent_complete

            updated = milestone.model_copy(update=updates)
            self._milestones[milestone_id] = updated
            return updated

    def get_critical_path(self, trial_id: str) -> CriticalPathResult:
        """Find the critical path (longest chain of dependent milestones) for a trial."""
        with self._lock:
            trial_milestones = {
                mid: m for mid, m in self._milestones.items()
                if m.trial_id == trial_id
            }

        if not trial_milestones:
            return CriticalPathResult(
                trial_id=trial_id,
                critical_path=[],
                total_duration_days=0,
                earliest_completion=None,
            )

        # Build adjacency list (dependency -> dependent)
        # and compute longest path using topological sort
        in_degree: dict[str, int] = {mid: 0 for mid in trial_milestones}
        children: dict[str, list[str]] = {mid: [] for mid in trial_milestones}

        for mid, ms in trial_milestones.items():
            for dep_id in ms.dependencies:
                if dep_id in trial_milestones:
                    children[dep_id].append(mid)
                    in_degree[mid] += 1

        # Topological sort + longest path computation
        dist: dict[str, int] = {mid: 0 for mid in trial_milestones}
        predecessor: dict[str, str | None] = {mid: None for mid in trial_milestones}

        # Start from milestones with no dependencies
        queue = [mid for mid, deg in in_degree.items() if deg == 0]

        # Calculate durations based on planned dates
        earliest_date = min(m.planned_date for m in trial_milestones.values())
        durations: dict[str, int] = {}
        for mid, ms in trial_milestones.items():
            durations[mid] = (ms.planned_date - earliest_date).days

        processed = []
        while queue:
            current = queue.pop(0)
            processed.append(current)
            for child in children[current]:
                new_dist = durations[current] + max(1, (trial_milestones[child].planned_date - trial_milestones[current].planned_date).days)
                if new_dist > dist[child]:
                    dist[child] = new_dist
                    predecessor[child] = current
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        # Find the end of the critical path
        if not dist:
            return CriticalPathResult(
                trial_id=trial_id,
                critical_path=[],
                total_duration_days=0,
                earliest_completion=None,
            )

        end_node = max(dist, key=lambda k: dist[k])
        total_duration = dist[end_node]

        # Trace back the critical path
        path_ids = []
        current_node: str | None = end_node
        while current_node is not None:
            path_ids.append(current_node)
            current_node = predecessor[current_node]
        path_ids.reverse()

        critical_milestones = [trial_milestones[mid] for mid in path_ids]

        # Earliest completion = latest planned date on the critical path
        latest_planned = max(m.planned_date for m in critical_milestones)

        return CriticalPathResult(
            trial_id=trial_id,
            critical_path=critical_milestones,
            total_duration_days=total_duration,
            earliest_completion=latest_planned,
        )

    def get_gantt_data(self, trial_id: str) -> GanttChartData:
        """Generate Gantt chart data for a trial."""
        critical_path = self.get_critical_path(trial_id)
        critical_ids = [m.id for m in critical_path.critical_path]

        with self._lock:
            trial_milestones = [
                m for m in self._milestones.values()
                if m.trial_id == trial_id
            ]

        items = []
        for ms in trial_milestones:
            # Estimate start based on dependencies or as standalone
            if ms.dependencies:
                dep_dates = []
                for dep_id in ms.dependencies:
                    dep = self._milestones.get(dep_id)
                    if dep:
                        dep_dates.append(dep.actual_date or dep.planned_date)
                start = max(dep_dates) if dep_dates else ms.planned_date - timedelta(days=30)
            else:
                start = ms.planned_date - timedelta(days=30)

            items.append(GanttItem(
                milestone_id=ms.id,
                name=ms.name,
                category=ms.category,
                status=ms.status,
                planned_start=start,
                planned_end=ms.planned_date,
                actual_end=ms.actual_date,
                percent_complete=ms.percent_complete,
                dependencies=ms.dependencies,
                is_critical_path=ms.id in critical_ids,
            ))

        return GanttChartData(
            trial_id=trial_id,
            items=items,
            critical_path_ids=critical_ids,
        )

    # ------------------------------------------------------------------
    # Communications
    # ------------------------------------------------------------------

    def list_communications(
        self,
        trial_id: str | None = None,
        comm_type: CommunicationType | None = None,
    ) -> list[SiteCommunication]:
        """List communications with optional filtering."""
        with self._lock:
            items = list(self._communications.values())

        if trial_id:
            items = [c for c in items if c.trial_id == trial_id]
        if comm_type:
            items = [c for c in items if c.type == comm_type]

        return items

    def get_communication(self, comm_id: str) -> SiteCommunication | None:
        """Get a single communication by ID."""
        with self._lock:
            return self._communications.get(comm_id)

    def send_communication(self, create: SiteCommunicationCreate) -> SiteCommunication:
        """Send a new communication to sites."""
        now = datetime.now(timezone.utc)
        comm_id = f"COMM-{uuid4().hex[:8].upper()}"

        comm = SiteCommunication(
            id=comm_id,
            trial_id=create.trial_id,
            type=create.type,
            subject=create.subject,
            body=create.body,
            sent_date=now,
            recipients=create.recipients,
            acknowledgments=[],
            requires_acknowledgment=create.requires_acknowledgment,
        )

        with self._lock:
            self._communications[comm_id] = comm

        return comm

    def acknowledge_communication(self, comm_id: str, site_id: str) -> SiteCommunication:
        """Acknowledge a communication from a site."""
        with self._lock:
            comm = self._communications.get(comm_id)
            if comm is None:
                raise ValueError(f"Communication not found: {comm_id}")
            if site_id not in comm.recipients:
                raise ValueError(f"Site {site_id} is not a recipient of communication {comm_id}")
            if site_id in comm.acknowledgments:
                raise ValueError(f"Site {site_id} has already acknowledged communication {comm_id}")

            updated_acks = list(comm.acknowledgments) + [site_id]
            updated = comm.model_copy(update={"acknowledgments": updated_acks})
            self._communications[comm_id] = updated
            return updated

    def get_acknowledgment_rate(self, comm_id: str) -> float:
        """Get acknowledgment percentage for a communication."""
        with self._lock:
            comm = self._communications.get(comm_id)
            if comm is None:
                raise ValueError(f"Communication not found: {comm_id}")
            if not comm.recipients:
                return 0.0
            return (len(comm.acknowledgments) / len(comm.recipients)) * 100.0

    # ------------------------------------------------------------------
    # Cross-trial Resources
    # ------------------------------------------------------------------

    def list_resources(self) -> list[CrossTrialResource]:
        """List all cross-trial resources."""
        with self._lock:
            return list(self._resources.values())

    def get_resource(self, resource_id: str) -> CrossTrialResource | None:
        """Get a single resource by ID."""
        with self._lock:
            return self._resources.get(resource_id)

    def add_resource(self, create: CrossTrialResourceCreate) -> CrossTrialResource:
        """Add a new cross-trial resource."""
        rid = f"RES-{uuid4().hex[:8].upper()}"

        resource = CrossTrialResource(
            id=rid,
            resource_name=create.resource_name,
            role=create.role,
            assigned_trials=create.assigned_trials,
            utilization_pct=create.utilization_pct,
            availability_start=create.availability_start,
            skills=create.skills,
        )

        with self._lock:
            self._resources[rid] = resource

        return resource

    def get_utilization_report(self) -> ResourceUtilization:
        """Generate resource utilization report."""
        with self._lock:
            resources = list(self._resources.values())

        if not resources:
            return ResourceUtilization(
                total_resources=0,
                avg_utilization_pct=0.0,
                over_utilized=[],
                under_utilized=[],
                by_role={},
            )

        avg_util = sum(r.utilization_pct for r in resources) / len(resources)
        over = [r for r in resources if r.utilization_pct > 90.0]
        under = [r for r in resources if r.utilization_pct < 30.0]

        # Average utilization by role
        role_totals: dict[str, list[float]] = defaultdict(list)
        for r in resources:
            role_totals[r.role].append(r.utilization_pct)
        by_role = {role: sum(vals) / len(vals) for role, vals in role_totals.items()}

        return ResourceUtilization(
            total_resources=len(resources),
            avg_utilization_pct=round(avg_util, 1),
            over_utilized=over,
            under_utilized=under,
            by_role={k: round(v, 1) for k, v in by_role.items()},
        )

    # ------------------------------------------------------------------
    # Enrollment Forecasting
    # ------------------------------------------------------------------

    def get_enrollment_projection(self, trial_id: str | None = None) -> list[EnrollmentProjection]:
        """Get enrollment projections, optionally filtered by trial."""
        now = datetime.now(timezone.utc)
        projections = []

        trial_ids = [trial_id] if trial_id else [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]

        for tid in trial_ids:
            target = ENROLLMENT_TARGETS.get(tid, 0)
            current = CURRENT_ENROLLMENT.get(tid, 0)

            # Count enrolling sites
            enrolling_sites = len([
                s for s in self._site_activations.values()
                if s.trial_id == tid and s.status == SiteActivationStatus.ENROLLING
            ])

            # Estimate monthly enrollment rate based on enrolling sites
            # Assume ~5 patients/site/month
            rate = enrolling_sites * 5.0 if enrolling_sites > 0 else 0.0

            remaining = max(0, target - current)
            months_remaining = remaining / rate if rate > 0 else None
            projected_completion = (
                now + timedelta(days=int(months_remaining * 30.44))
                if months_remaining is not None else None
            )

            on_track = True
            if months_remaining is not None and months_remaining > 12:
                on_track = False

            projections.append(EnrollmentProjection(
                trial_id=tid,
                enrollment_target=target,
                current_enrollment=current,
                enrollment_rate_per_month=round(rate, 1),
                projected_completion_date=projected_completion,
                months_remaining=round(months_remaining, 1) if months_remaining is not None else None,
                on_track=on_track,
                sites_enrolling=enrolling_sites,
            ))

        return projections

    # ------------------------------------------------------------------
    # TMO Dashboard
    # ------------------------------------------------------------------

    def get_dashboard(self, trial_id: str) -> TMODashboard:
        """Generate TMO dashboard for a trial."""
        now = datetime.now(timezone.utc)

        # Site metrics
        sites = [s for s in self._site_activations.values() if s.trial_id == trial_id]
        status_counts: dict[str, int] = Counter()
        for s in sites:
            status_counts[s.status.value] += 1

        # Country metrics
        countries = [c for c in self._country_regulatory.values()
                     if c.trial_id == trial_id and c.status in (CountryStatus.ACTIVE, CountryStatus.APPROVED)]

        # Enrollment metrics
        target = ENROLLMENT_TARGETS.get(trial_id, 0)
        current = CURRENT_ENROLLMENT.get(trial_id, 0)
        enrolling_sites = len([s for s in sites if s.status == SiteActivationStatus.ENROLLING])
        rate = enrolling_sites * 5.0

        # Milestone metrics
        milestones = [m for m in self._milestones.values() if m.trial_id == trial_id]
        on_track = len([m for m in milestones if m.status in (
            MilestoneStatus.COMPLETED, MilestoneStatus.IN_PROGRESS, MilestoneStatus.NOT_STARTED
        )])
        delayed = len([m for m in milestones if m.status in (
            MilestoneStatus.DELAYED, MilestoneStatus.AT_RISK
        )])

        # Open blockers
        open_blockers = len([
            b for b in self._blockers.values()
            if b.trial_id == trial_id and b.resolved_date is None
        ])

        # Upcoming milestones in 30 days
        upcoming_30d = [
            m for m in milestones
            if m.status != MilestoneStatus.COMPLETED
            and m.status != MilestoneStatus.CANCELLED
            and m.planned_date <= now + timedelta(days=30)
            and m.planned_date >= now - timedelta(days=7)
        ]

        return TMODashboard(
            trial_id=trial_id,
            total_sites=len(sites),
            sites_by_status=dict(status_counts),
            countries_active=len(countries),
            enrollment_target=target,
            current_enrollment=current,
            enrollment_rate_per_month=round(rate, 1),
            milestones_on_track=on_track,
            milestones_delayed=delayed,
            open_blockers=open_blockers,
            upcoming_milestones_30d=upcoming_30d,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics."""
        with self._lock:
            return {
                "site_activations": len(self._site_activations),
                "country_regulatory": len(self._country_regulatory),
                "milestones": len(self._milestones),
                "communications": len(self._communications),
                "blockers": len(self._blockers),
                "resources": len(self._resources),
                "open_blockers": len([b for b in self._blockers.values() if b.resolved_date is None]),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TrialManagementService | None = None
_instance_lock = threading.Lock()


def get_tmo_service() -> TrialManagementService:
    """Return the singleton TrialManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TrialManagementService()
    return _instance


def reset_tmo_service() -> TrialManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = TrialManagementService()
    return _instance
