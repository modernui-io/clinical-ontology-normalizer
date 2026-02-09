"""Patient Screening Dashboard Service (VP-Product-8).

In-memory service for managing saved searches, executing screening runs,
and producing dashboard analytics for clinical trial patient recruitment.

Usage:
    from app.services.screening_dashboard_service import (
        get_screening_dashboard_service,
    )

    svc = get_screening_dashboard_service()
    summary = svc.get_dashboard_summary()
"""

from __future__ import annotations

import logging
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.schemas.screening_dashboard import (
    DailyVolume,
    DashboardSummary,
    ExclusionReason,
    ExportResultsResponse,
    FilterOperator,
    RunScreeningRequest,
    SavedSearch,
    SavedSearchCreate,
    SavedSearchFilters,
    SavedSearchUpdate,
    ScreeningFilter,
    ScreeningHistoryItem,
    ScreeningMetrics,
    ScreeningResult,
    ScreeningSession,
    ScreeningStatus,
    TopMatchingTrial,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory patient data for screening
# ---------------------------------------------------------------------------

_DEMO_PATIENTS: list[dict[str, Any]] = [
    {
        "patient_id": "PAT-001",
        "patient_name": "Maria Garcia",
        "age": 62,
        "gender": "Female",
        "conditions": ["Diabetic Macular Edema", "Type 2 Diabetes", "Hypertension"],
        "labs": {"HbA1c": 7.8, "BCVA_ETDRS": 58, "CRT": 350, "eGFR": 72},
        "medications": ["Metformin", "Lisinopril"],
        "last_visit_date": "2025-12-15",
    },
    {
        "patient_id": "PAT-002",
        "patient_name": "James Wilson",
        "age": 55,
        "gender": "Male",
        "conditions": ["Diabetic Macular Edema", "Type 2 Diabetes", "Hyperlipidemia"],
        "labs": {"HbA1c": 8.2, "BCVA_ETDRS": 62, "CRT": 320, "eGFR": 85},
        "medications": ["Metformin", "Atorvastatin", "Insulin Glargine"],
        "last_visit_date": "2025-12-20",
    },
    {
        "patient_id": "PAT-003",
        "patient_name": "Sarah Chen",
        "age": 34,
        "gender": "Female",
        "conditions": ["Atopic Dermatitis", "Asthma", "Allergic Rhinitis"],
        "labs": {"IgE": 450, "Eosinophils": 620, "EASI": 28},
        "medications": ["Fluticasone", "Cetirizine"],
        "last_visit_date": "2025-12-18",
    },
    {
        "patient_id": "PAT-004",
        "patient_name": "Robert Thompson",
        "age": 71,
        "gender": "Male",
        "conditions": ["Cutaneous Squamous Cell Carcinoma", "Hypertension", "COPD"],
        "labs": {"LDH": 210, "Albumin": 3.8, "WBC": 7200},
        "medications": ["Amlodipine", "Tiotropium"],
        "last_visit_date": "2025-12-22",
    },
    {
        "patient_id": "PAT-005",
        "patient_name": "Emily Rodriguez",
        "age": 28,
        "gender": "Female",
        "conditions": ["Atopic Dermatitis", "Food Allergy"],
        "labs": {"IgE": 380, "Eosinophils": 510, "EASI": 22},
        "medications": ["Hydroxyzine", "Emollients"],
        "last_visit_date": "2025-12-19",
    },
    {
        "patient_id": "PAT-006",
        "patient_name": "Michael Brown",
        "age": 68,
        "gender": "Male",
        "conditions": ["Type 2 Diabetes", "Diabetic Retinopathy", "Chronic Kidney Disease"],
        "labs": {"HbA1c": 9.1, "BCVA_ETDRS": 45, "CRT": 410, "eGFR": 38},
        "medications": ["Insulin Lispro", "Losartan", "Amlodipine"],
        "last_visit_date": "2025-12-10",
    },
    {
        "patient_id": "PAT-007",
        "patient_name": "Jennifer Lee",
        "age": 45,
        "gender": "Female",
        "conditions": ["Atopic Dermatitis", "Depression", "Insomnia"],
        "labs": {"IgE": 290, "Eosinophils": 400, "EASI": 16},
        "medications": ["Sertraline", "Tacrolimus Ointment"],
        "last_visit_date": "2025-12-21",
    },
    {
        "patient_id": "PAT-008",
        "patient_name": "William Davis",
        "age": 58,
        "gender": "Male",
        "conditions": ["Type 2 Diabetes", "Hypertension", "Obesity"],
        "labs": {"HbA1c": 7.2, "eGFR": 90, "BMI": 34.5},
        "medications": ["Metformin", "Empagliflozin", "Lisinopril"],
        "last_visit_date": "2025-12-17",
    },
    {
        "patient_id": "PAT-009",
        "patient_name": "Ashley Martinez",
        "age": 23,
        "gender": "Female",
        "conditions": ["Eczema", "Allergic Rhinitis"],
        "labs": {"IgE": 180, "Eosinophils": 320, "EASI": 12},
        "medications": ["Cetirizine", "Hydrocortisone Cream"],
        "last_visit_date": "2025-12-14",
    },
    {
        "patient_id": "PAT-010",
        "patient_name": "David Kim",
        "age": 66,
        "gender": "Male",
        "conditions": ["Cutaneous Squamous Cell Carcinoma", "Type 2 Diabetes"],
        "labs": {"LDH": 195, "Albumin": 4.0, "WBC": 6800, "HbA1c": 7.0},
        "medications": ["Metformin", "Aspirin"],
        "last_visit_date": "2025-12-23",
    },
    {
        "patient_id": "PAT-011",
        "patient_name": "Linda White",
        "age": 59,
        "gender": "Female",
        "conditions": ["Diabetic Macular Edema", "Type 2 Diabetes", "Osteoarthritis"],
        "labs": {"HbA1c": 8.5, "BCVA_ETDRS": 55, "CRT": 380, "eGFR": 65},
        "medications": ["Insulin Glargine", "Metformin", "Naproxen"],
        "last_visit_date": "2025-12-16",
    },
    {
        "patient_id": "PAT-012",
        "patient_name": "Thomas Anderson",
        "age": 42,
        "gender": "Male",
        "conditions": ["Psoriasis", "Hypertension"],
        "labs": {"PASI": 18, "CRP": 3.2},
        "medications": ["Methotrexate", "Lisinopril"],
        "last_visit_date": "2025-12-11",
    },
]

# ---------------------------------------------------------------------------
# Trial criteria definitions for screening
# ---------------------------------------------------------------------------

_TRIAL_CRITERIA: dict[str, dict[str, Any]] = {
    "TRIAL-EYLEA-DME": {
        "name": "EYLEA HD DME Pivotal Study",
        "conditions_required": ["Diabetic Macular Edema"],
        "age_range": {"min": 18, "max": 85},
        "lab_criteria": {
            "BCVA_ETDRS": {"min": 24, "max": 73},
            "CRT": {"min": 300},
        },
        "exclusions": ["Active Cancer", "Uncontrolled Glaucoma"],
    },
    "TRIAL-DUPIXENT-AD": {
        "name": "Dupixent Atopic Dermatitis Phase III",
        "conditions_required": ["Atopic Dermatitis"],
        "age_range": {"min": 12, "max": 75},
        "lab_criteria": {
            "EASI": {"min": 16},
        },
        "exclusions": ["Active Cancer", "Active Infection", "Immunosuppressive Therapy"],
    },
    "TRIAL-LIBTAYO-CSCC": {
        "name": "Libtayo Advanced CSCC Study",
        "conditions_required": ["Cutaneous Squamous Cell Carcinoma"],
        "age_range": {"min": 18},
        "lab_criteria": {
            "LDH": {"max": 300},
        },
        "exclusions": ["Autoimmune Disease", "Organ Transplant"],
    },
}


class ScreeningDashboardService:
    """In-memory screening dashboard with saved searches and analytics.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._saved_searches: dict[str, SavedSearch] = {}
        self._sessions: dict[str, ScreeningSession] = {}
        self._lock = threading.Lock()
        self._prepopulate()

    # ------------------------------------------------------------------
    # Pre-population
    # ------------------------------------------------------------------

    def _prepopulate(self) -> None:
        """Seed default saved searches and demo screening sessions."""
        now = datetime.now(timezone.utc)

        # --- Saved searches ---
        searches = [
            SavedSearchCreate(
                name="EYLEA DME Candidates",
                description="Patients with DME eligible for EYLEA HD trial",
                created_by="system",
                filters=SavedSearchFilters(
                    trial_id="TRIAL-EYLEA-DME",
                    conditions=["Diabetic Macular Edema"],
                    age_range={"min": 18, "max": 85},
                    lab_ranges={"BCVA_ETDRS": {"min": 24, "max": 73}, "CRT": {"min": 300}},
                    exclusions=["Active Cancer", "Uncontrolled Glaucoma"],
                ),
            ),
            SavedSearchCreate(
                name="Dupixent AD Candidates",
                description="Moderate-to-severe atopic dermatitis patients for Dupixent trial",
                created_by="system",
                filters=SavedSearchFilters(
                    trial_id="TRIAL-DUPIXENT-AD",
                    conditions=["Atopic Dermatitis"],
                    age_range={"min": 12, "max": 75},
                    lab_ranges={"EASI": {"min": 16}},
                    exclusions=["Active Cancer", "Active Infection"],
                ),
            ),
            SavedSearchCreate(
                name="Libtayo CSCC Candidates",
                description="Advanced CSCC patients for Libtayo immunotherapy study",
                created_by="system",
                filters=SavedSearchFilters(
                    trial_id="TRIAL-LIBTAYO-CSCC",
                    conditions=["Cutaneous Squamous Cell Carcinoma"],
                    age_range={"min": 18},
                    lab_ranges={"LDH": {"max": 300}},
                    exclusions=["Autoimmune Disease", "Organ Transplant"],
                ),
            ),
            SavedSearchCreate(
                name="High-Risk Diabetics",
                description="Diabetic patients with poor glycemic control for multiple trial matching",
                created_by="dr.smith",
                filters=SavedSearchFilters(
                    conditions=["Type 2 Diabetes"],
                    lab_ranges={"HbA1c": {"min": 7.5}},
                    exclusions=["Chronic Kidney Disease Stage 5"],
                ),
            ),
            SavedSearchCreate(
                name="Young Adults with Skin Conditions",
                description="Young adults (18-35) with dermatological conditions",
                created_by="dr.jones",
                filters=SavedSearchFilters(
                    conditions=["Atopic Dermatitis", "Eczema"],
                    age_range={"min": 18, "max": 35},
                    exclusions=[],
                ),
            ),
        ]

        for sc in searches:
            self.create_saved_search(sc)

        # --- Demo screening sessions ---
        session1_results = self._screen_patients_against_trial("TRIAL-EYLEA-DME")
        session1 = ScreeningSession(
            id=str(uuid4()),
            trial_id="TRIAL-EYLEA-DME",
            filters_applied=[],
            total_screened=len(session1_results),
            total_eligible=sum(1 for r in session1_results if r.status == ScreeningStatus.ELIGIBLE),
            total_ineligible=sum(1 for r in session1_results if r.status == ScreeningStatus.INELIGIBLE),
            total_indeterminate=sum(1 for r in session1_results if r.status == ScreeningStatus.INDETERMINATE),
            results=session1_results,
            started_at=now - timedelta(hours=4),
            completed_at=now - timedelta(hours=3, minutes=55),
            created_by="system",
        )

        session2_results = self._screen_patients_against_trial("TRIAL-DUPIXENT-AD")
        session2 = ScreeningSession(
            id=str(uuid4()),
            trial_id="TRIAL-DUPIXENT-AD",
            filters_applied=[],
            total_screened=len(session2_results),
            total_eligible=sum(1 for r in session2_results if r.status == ScreeningStatus.ELIGIBLE),
            total_ineligible=sum(1 for r in session2_results if r.status == ScreeningStatus.INELIGIBLE),
            total_indeterminate=sum(1 for r in session2_results if r.status == ScreeningStatus.INDETERMINATE),
            results=session2_results,
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=1, minutes=55),
            created_by="dr.smith",
        )

        session3_results = self._screen_patients_against_trial("TRIAL-LIBTAYO-CSCC")
        session3 = ScreeningSession(
            id=str(uuid4()),
            trial_id="TRIAL-LIBTAYO-CSCC",
            filters_applied=[],
            total_screened=len(session3_results),
            total_eligible=sum(1 for r in session3_results if r.status == ScreeningStatus.ELIGIBLE),
            total_ineligible=sum(1 for r in session3_results if r.status == ScreeningStatus.INELIGIBLE),
            total_indeterminate=sum(1 for r in session3_results if r.status == ScreeningStatus.INDETERMINATE),
            results=session3_results,
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=55),
            created_by="system",
        )

        with self._lock:
            self._sessions[session1.id] = session1
            self._sessions[session2.id] = session2
            self._sessions[session3.id] = session3

    # ------------------------------------------------------------------
    # Internal screening logic
    # ------------------------------------------------------------------

    def _screen_patient_against_criteria(
        self, patient: dict[str, Any], criteria: dict[str, Any]
    ) -> ScreeningResult:
        """Screen a single patient against trial criteria."""
        matched: list[str] = []
        unmatched: list[str] = []
        missing: list[str] = []

        # Check conditions
        required_conditions = criteria.get("conditions_required", [])
        patient_conditions = [c.lower() for c in patient.get("conditions", [])]
        for cond in required_conditions:
            if cond.lower() in patient_conditions:
                matched.append(f"Condition: {cond}")
            else:
                unmatched.append(f"Condition: {cond}")

        # Check age
        age_range = criteria.get("age_range", {})
        patient_age = patient.get("age", 0)
        if age_range:
            age_ok = True
            if "min" in age_range and patient_age < age_range["min"]:
                age_ok = False
            if "max" in age_range and patient_age > age_range["max"]:
                age_ok = False
            if age_ok:
                matched.append("Age within range")
            else:
                unmatched.append(f"Age: {patient_age} outside [{age_range.get('min', 0)}-{age_range.get('max', 'N/A')}]")

        # Check lab criteria
        lab_criteria = criteria.get("lab_criteria", {})
        patient_labs = patient.get("labs", {})
        for lab_name, lab_range in lab_criteria.items():
            if lab_name not in patient_labs:
                missing.append(f"Lab: {lab_name}")
                continue
            value = patient_labs[lab_name]
            lab_ok = True
            if "min" in lab_range and value < lab_range["min"]:
                lab_ok = False
            if "max" in lab_range and value > lab_range["max"]:
                lab_ok = False
            if lab_ok:
                matched.append(f"Lab {lab_name}: {value} in range")
            else:
                unmatched.append(f"Lab {lab_name}: {value} out of range")

        # Check exclusions
        exclusions = criteria.get("exclusions", [])
        for excl in exclusions:
            if excl.lower() in patient_conditions:
                unmatched.append(f"Exclusion: {excl}")

        # Calculate score and status
        total_criteria = len(matched) + len(unmatched) + len(missing)
        match_score = len(matched) / total_criteria if total_criteria > 0 else 0.0

        if len(unmatched) == 0 and len(missing) == 0:
            status = ScreeningStatus.ELIGIBLE
        elif len(missing) > 0 and len(unmatched) == 0:
            status = ScreeningStatus.INDETERMINATE
        else:
            status = ScreeningStatus.INELIGIBLE

        return ScreeningResult(
            patient_id=patient["patient_id"],
            patient_name=patient["patient_name"],
            age=patient["age"],
            gender=patient["gender"],
            match_score=round(match_score, 3),
            matched_criteria=matched,
            unmatched_criteria=unmatched,
            missing_data=missing,
            last_visit_date=patient.get("last_visit_date"),
            primary_conditions=patient.get("conditions", []),
            status=status,
        )

    def _screen_patients_against_trial(
        self,
        trial_id: str,
        patients: list[dict[str, Any]] | None = None,
        extra_filters: list[ScreeningFilter] | None = None,
    ) -> list[ScreeningResult]:
        """Screen all patients against a trial's criteria."""
        criteria = _TRIAL_CRITERIA.get(trial_id)
        if not criteria:
            return []

        pool = patients if patients is not None else _DEMO_PATIENTS
        results: list[ScreeningResult] = []

        for patient in pool:
            # Apply extra filters first
            if extra_filters and not self._patient_matches_filters(patient, extra_filters):
                continue
            result = self._screen_patient_against_criteria(patient, criteria)
            results.append(result)

        return results

    def _patient_matches_filters(
        self, patient: dict[str, Any], filters: list[ScreeningFilter]
    ) -> bool:
        """Check if a patient matches all additional filters."""
        for f in filters:
            field = f.field.lower()
            op = f.operator

            # Get patient value
            if field == "age":
                pval: Any = patient.get("age")
            elif field == "gender":
                pval = patient.get("gender", "").lower()
            elif field.startswith("lab."):
                lab_name = f.field.split(".", 1)[1]
                pval = patient.get("labs", {}).get(lab_name)
            elif field == "condition":
                pval = [c.lower() for c in patient.get("conditions", [])]
            else:
                pval = patient.get(field)

            if pval is None and op != FilterOperator.NE:
                return False

            # Evaluate
            if op == FilterOperator.EQ:
                if isinstance(pval, str):
                    if pval.lower() != str(f.value).lower():
                        return False
                elif pval != f.value:
                    return False
            elif op == FilterOperator.NE:
                if pval is not None and pval == f.value:
                    return False
            elif op == FilterOperator.GT:
                if not (isinstance(pval, (int, float)) and pval > float(f.value)):  # type: ignore[arg-type]
                    return False
            elif op == FilterOperator.LT:
                if not (isinstance(pval, (int, float)) and pval < float(f.value)):  # type: ignore[arg-type]
                    return False
            elif op == FilterOperator.GTE:
                if not (isinstance(pval, (int, float)) and pval >= float(f.value)):  # type: ignore[arg-type]
                    return False
            elif op == FilterOperator.LTE:
                if not (isinstance(pval, (int, float)) and pval <= float(f.value)):  # type: ignore[arg-type]
                    return False
            elif op == FilterOperator.CONTAINS:
                if isinstance(pval, list):
                    if not any(str(f.value).lower() in item.lower() for item in pval):
                        return False
                elif isinstance(pval, str):
                    if str(f.value).lower() not in pval.lower():
                        return False
                else:
                    return False
            elif op == FilterOperator.IN:
                if f.values is None:
                    return False
                str_values = [str(v).lower() for v in f.values]
                if isinstance(pval, list):
                    if not any(item.lower() in str_values for item in pval):
                        return False
                else:
                    if str(pval).lower() not in str_values:
                        return False
            elif op == FilterOperator.BETWEEN:
                if f.values is None or len(f.values) < 2:
                    return False
                lo, hi = float(f.values[0]), float(f.values[1])
                if not (isinstance(pval, (int, float)) and lo <= pval <= hi):
                    return False

        return True

    # ------------------------------------------------------------------
    # Saved Search CRUD
    # ------------------------------------------------------------------

    def create_saved_search(self, create: SavedSearchCreate) -> SavedSearch:
        """Create and store a new saved search."""
        now = datetime.now(timezone.utc)
        search = SavedSearch(
            id=str(uuid4()),
            name=create.name,
            description=create.description,
            created_by=create.created_by,
            filters=create.filters,
            patient_count=0,
            last_run=None,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._saved_searches[search.id] = search
        return search

    def list_saved_searches(self) -> list[SavedSearch]:
        """Return all saved searches."""
        with self._lock:
            return list(self._saved_searches.values())

    def get_saved_search(self, search_id: str) -> SavedSearch | None:
        """Return a single saved search by ID."""
        with self._lock:
            return self._saved_searches.get(search_id)

    def update_saved_search(self, search_id: str, update: SavedSearchUpdate) -> SavedSearch | None:
        """Update an existing saved search."""
        with self._lock:
            search = self._saved_searches.get(search_id)
            if not search:
                return None
            if update.name is not None:
                search.name = update.name
            if update.description is not None:
                search.description = update.description
            if update.filters is not None:
                search.filters = update.filters
            search.updated_at = datetime.now(timezone.utc)
            self._saved_searches[search_id] = search
            return search

    def delete_saved_search(self, search_id: str) -> bool:
        """Delete a saved search. Returns True if it existed."""
        with self._lock:
            return self._saved_searches.pop(search_id, None) is not None

    def execute_saved_search(self, search_id: str) -> ScreeningSession | None:
        """Execute a saved search and return results as a screening session."""
        search = self.get_saved_search(search_id)
        if not search:
            return None

        trial_id = search.filters.trial_id or "CUSTOM"

        # Build filters from saved search
        extra_filters: list[ScreeningFilter] = []
        if search.filters.age_range:
            if "min" in search.filters.age_range:
                extra_filters.append(
                    ScreeningFilter(field="age", operator=FilterOperator.GTE, value=search.filters.age_range["min"])
                )
            if "max" in search.filters.age_range:
                extra_filters.append(
                    ScreeningFilter(field="age", operator=FilterOperator.LTE, value=search.filters.age_range["max"])
                )

        # Screen patients
        if trial_id != "CUSTOM" and trial_id in _TRIAL_CRITERIA:
            results = self._screen_patients_against_trial(trial_id)
        else:
            # Custom search: match by conditions
            matching_patients = []
            for patient in _DEMO_PATIENTS:
                patient_conds = [c.lower() for c in patient.get("conditions", [])]
                required = search.filters.conditions
                if required and any(r.lower() in patient_conds for r in required):
                    matching_patients.append(patient)
                elif not required:
                    matching_patients.append(patient)

            # Apply age filter
            if search.filters.age_range:
                filtered = []
                for p in matching_patients:
                    age = p.get("age", 0)
                    min_age = search.filters.age_range.get("min", 0)
                    max_age = search.filters.age_range.get("max", 999)
                    if min_age <= age <= max_age:
                        filtered.append(p)
                matching_patients = filtered

            # Build simple results for non-trial searches
            results = []
            for p in matching_patients:
                matched = [f"Condition: {c}" for c in p.get("conditions", [])
                           if c.lower() in [r.lower() for r in search.filters.conditions]]
                results.append(ScreeningResult(
                    patient_id=p["patient_id"],
                    patient_name=p["patient_name"],
                    age=p["age"],
                    gender=p["gender"],
                    match_score=1.0 if matched else 0.5,
                    matched_criteria=matched,
                    unmatched_criteria=[],
                    missing_data=[],
                    last_visit_date=p.get("last_visit_date"),
                    primary_conditions=p.get("conditions", []),
                    status=ScreeningStatus.ELIGIBLE if matched else ScreeningStatus.INDETERMINATE,
                ))

        now = datetime.now(timezone.utc)
        session = ScreeningSession(
            id=str(uuid4()),
            trial_id=trial_id,
            filters_applied=extra_filters,
            total_screened=len(results),
            total_eligible=sum(1 for r in results if r.status == ScreeningStatus.ELIGIBLE),
            total_ineligible=sum(1 for r in results if r.status == ScreeningStatus.INELIGIBLE),
            total_indeterminate=sum(1 for r in results if r.status == ScreeningStatus.INDETERMINATE),
            results=results,
            started_at=now,
            completed_at=now,
            created_by="system",
        )

        with self._lock:
            self._sessions[session.id] = session
            search.last_run = now
            search.patient_count = session.total_eligible
            self._saved_searches[search_id] = search

        return session

    # ------------------------------------------------------------------
    # Run Screening
    # ------------------------------------------------------------------

    def run_screening(self, request: RunScreeningRequest) -> ScreeningSession:
        """Execute a screening run for a trial with optional filters."""
        now = datetime.now(timezone.utc)
        results = self._screen_patients_against_trial(
            request.trial_id,
            extra_filters=request.filters if request.filters else None,
        )

        session = ScreeningSession(
            id=str(uuid4()),
            trial_id=request.trial_id,
            filters_applied=request.filters,
            total_screened=len(results),
            total_eligible=sum(1 for r in results if r.status == ScreeningStatus.ELIGIBLE),
            total_ineligible=sum(1 for r in results if r.status == ScreeningStatus.INELIGIBLE),
            total_indeterminate=sum(1 for r in results if r.status == ScreeningStatus.INDETERMINATE),
            results=results,
            started_at=now,
            completed_at=datetime.now(timezone.utc),
            created_by=request.created_by,
        )

        with self._lock:
            self._sessions[session.id] = session

        return session

    # ------------------------------------------------------------------
    # Dashboard Summary
    # ------------------------------------------------------------------

    def get_dashboard_summary(self) -> DashboardSummary:
        """Return high-level dashboard stats."""
        with self._lock:
            sessions = list(self._sessions.values())

        today = datetime.now(timezone.utc).date()

        # Count today's screening
        today_sessions = [
            s for s in sessions
            if s.started_at.date() == today
        ]
        total_screened_today = sum(s.total_screened for s in today_sessions)
        total_eligible_today = sum(s.total_eligible for s in today_sessions)

        # Screening rate trend (last 7 days)
        trend: list[dict[str, int | str]] = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_sessions = [s for s in sessions if s.started_at.date() == day]
            count = sum(s.total_screened for s in day_sessions)
            trend.append({"date": day.isoformat(), "count": count})

        # Top matching trials
        trial_eligible: dict[str, int] = defaultdict(int)
        for s in sessions:
            trial_eligible[s.trial_id] += s.total_eligible

        top_trials = [
            TopMatchingTrial(
                trial_id=tid,
                trial_name=_TRIAL_CRITERIA.get(tid, {}).get("name", tid),
                eligible_count=cnt,
            )
            for tid, cnt in sorted(trial_eligible.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return DashboardSummary(
            active_trials=len(_TRIAL_CRITERIA),
            total_patients=len(_DEMO_PATIENTS),
            total_screened_today=total_screened_today,
            total_eligible_today=total_eligible_today,
            screening_rate_trend=trend,
            top_matching_trials=top_trials,
        )

    # ------------------------------------------------------------------
    # Screening Metrics
    # ------------------------------------------------------------------

    def get_screening_metrics(self) -> ScreeningMetrics:
        """Return analytics metrics across all sessions."""
        with self._lock:
            sessions = list(self._sessions.values())

        if not sessions:
            return ScreeningMetrics()

        total_sessions = len(sessions)
        total_patients = sum(s.total_screened for s in sessions)
        avg_patients = total_patients / total_sessions if total_sessions else 0.0

        # Average match score
        all_scores: list[float] = []
        exclusion_counter: Counter[str] = Counter()
        for s in sessions:
            for r in s.results:
                all_scores.append(r.match_score)
                for crit in r.unmatched_criteria:
                    exclusion_counter[crit] += 1

        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        top_exclusions = [
            ExclusionReason(reason=reason, count=cnt)
            for reason, cnt in exclusion_counter.most_common(10)
        ]

        # Volume by day
        day_map: dict[str, dict[str, int]] = defaultdict(lambda: {"sessions": 0, "patients": 0})
        for s in sessions:
            day_key = s.started_at.date().isoformat()
            day_map[day_key]["sessions"] += 1
            day_map[day_key]["patients"] += s.total_screened

        volume_by_day = [
            DailyVolume(date=day, sessions=data["sessions"], patients_screened=data["patients"])
            for day, data in sorted(day_map.items())
        ]

        return ScreeningMetrics(
            total_sessions=total_sessions,
            avg_patients_per_session=round(avg_patients, 1),
            avg_match_score=round(avg_score, 3),
            most_common_exclusion_reasons=top_exclusions,
            screening_volume_by_day=volume_by_day,
        )

    # ------------------------------------------------------------------
    # Screening History
    # ------------------------------------------------------------------

    def get_screening_history(self, limit: int = 20) -> list[ScreeningHistoryItem]:
        """Return recent screening sessions (without results)."""
        with self._lock:
            sessions = sorted(
                self._sessions.values(),
                key=lambda s: s.started_at,
                reverse=True,
            )[:limit]

        return [
            ScreeningHistoryItem(
                id=s.id,
                trial_id=s.trial_id,
                total_screened=s.total_screened,
                total_eligible=s.total_eligible,
                total_ineligible=s.total_ineligible,
                total_indeterminate=s.total_indeterminate,
                started_at=s.started_at,
                completed_at=s.completed_at,
                created_by=s.created_by,
            )
            for s in sessions
        ]

    # ------------------------------------------------------------------
    # Session Details
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> ScreeningSession | None:
        """Return a single screening session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_results(self, session_id: str, fmt: str = "json") -> ExportResultsResponse | None:
        """Export session results in CSV-like or JSON format."""
        session = self.get_session(session_id)
        if not session:
            return None

        columns = [
            "patient_id", "patient_name", "age", "gender",
            "match_score", "status", "matched_criteria",
            "unmatched_criteria", "missing_data",
            "primary_conditions", "last_visit_date",
        ]

        data: list[dict] = []
        for r in session.results:
            row = {
                "patient_id": r.patient_id,
                "patient_name": r.patient_name,
                "age": r.age,
                "gender": r.gender,
                "match_score": r.match_score,
                "status": r.status.value,
                "matched_criteria": "; ".join(r.matched_criteria) if fmt == "csv" else r.matched_criteria,
                "unmatched_criteria": "; ".join(r.unmatched_criteria) if fmt == "csv" else r.unmatched_criteria,
                "missing_data": "; ".join(r.missing_data) if fmt == "csv" else r.missing_data,
                "primary_conditions": "; ".join(r.primary_conditions) if fmt == "csv" else r.primary_conditions,
                "last_visit_date": r.last_visit_date or "",
            }
            data.append(row)

        return ExportResultsResponse(
            session_id=session_id,
            format=fmt,
            row_count=len(data),
            columns=columns,
            data=data,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service stats."""
        with self._lock:
            return {
                "saved_searches": len(self._saved_searches),
                "sessions": len(self._sessions),
                "demo_patients": len(_DEMO_PATIENTS),
                "trial_criteria": len(_TRIAL_CRITERIA),
            }

    def clear(self) -> None:
        """Clear all data and re-populate with defaults."""
        with self._lock:
            self._saved_searches.clear()
            self._sessions.clear()
        self._prepopulate()

    def clear_all(self) -> None:
        """Clear all data without re-populating."""
        with self._lock:
            self._saved_searches.clear()
            self._sessions.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ScreeningDashboardService | None = None
_instance_lock = threading.Lock()


def get_screening_dashboard_service() -> ScreeningDashboardService:
    """Return the singleton ScreeningDashboardService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ScreeningDashboardService()
    return _instance
