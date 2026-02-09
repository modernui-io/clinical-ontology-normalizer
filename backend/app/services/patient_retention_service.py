"""Patient Retention Analytics Service (CMO-12).

Pharma-grade patient retention analytics engine that tracks patient dropout
risk, generates Kaplan-Meier retention curves, manages retention interventions,
provides site-level retention comparisons, and delivers comprehensive retention
dashboards for clinical trials.

Usage:
    from app.services.patient_retention_service import (
        get_patient_retention_service,
    )

    svc = get_patient_retention_service()
    profiles = svc.list_profiles()
    prediction = svc.predict_dropout("patient-001")
"""

from __future__ import annotations

import logging
import math
import random
import threading
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.schemas.patient_retention import (
    CohortAnalysis,
    DropoutPrediction,
    DropoutReason,
    InterventionCreateRequest,
    InterventionEffectiveness,
    InterventionType,
    InterventionUpdateRequest,
    PatientPhase,
    PatientRetentionProfile,
    ProfileCreateRequest,
    ProfileUpdateRequest,
    RetentionCurve,
    RetentionCurvePoint,
    RetentionDashboard,
    RetentionIntervention,
    RetentionMetrics,
    RetentionMetricType,
    RetentionRiskFactor,
    RetentionRiskLevel,
    SiteRetentionComparison,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trial ID constants (matching adverse_event_service)
# ---------------------------------------------------------------------------

EYLEA_TRIAL_ID = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL_ID = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL_ID = "00000000-de00-0003-0000-000000000003"

# ---------------------------------------------------------------------------
# Site constants
# ---------------------------------------------------------------------------

SITES = {
    "SITE-101": "Bascom Palmer Eye Institute",
    "SITE-102": "Wills Eye Hospital",
    "SITE-103": "Mass General Dermatology",
    "SITE-104": "Johns Hopkins Oncology",
    "SITE-105": "Mayo Clinic Ophthalmology",
    "SITE-106": "Cleveland Clinic Dermatology",
    "SITE-107": "MD Anderson Cancer Center",
    "SITE-108": "Stanford Dermatology",
}


class PatientRetentionService:
    """In-memory patient retention analytics engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, PatientRetentionProfile] = {}
        self._interventions: dict[str, RetentionIntervention] = {}
        self._lock = threading.Lock()
        self._profile_counter = 0
        self._intervention_counter = 0
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------

    def _next_profile_id(self) -> str:
        self._profile_counter += 1
        return f"ret-{self._profile_counter:04d}"

    def _next_intervention_id(self) -> str:
        self._intervention_counter += 1
        return f"intv-{self._intervention_counter:04d}"

    def _seed_demo_data(self) -> None:
        """Pre-populate 40 patient profiles across 3 Regeneron trials, 25 interventions."""
        today = date.today()
        rng = random.Random(42)

        # Patient data: (patient_id_suffix, trial_id, site_id, phase, enrolled_days_ago,
        #                visits_completed, visits_scheduled, missed_visits, dropped_out,
        #                dropout_reason, dropout_days_ago)
        patient_specs = [
            # EYLEA patients (15) - SITE-101, SITE-102, SITE-105
            ("P001", EYLEA_TRIAL_ID, "SITE-101", PatientPhase.ACTIVE_TREATMENT, 180, 8, 12, 0, False, None, None),
            ("P002", EYLEA_TRIAL_ID, "SITE-101", PatientPhase.ACTIVE_TREATMENT, 160, 7, 12, 1, False, None, None),
            ("P003", EYLEA_TRIAL_ID, "SITE-101", PatientPhase.FOLLOW_UP, 200, 10, 12, 0, False, None, None),
            ("P004", EYLEA_TRIAL_ID, "SITE-102", PatientPhase.ACTIVE_TREATMENT, 150, 6, 12, 2, False, None, None),
            ("P005", EYLEA_TRIAL_ID, "SITE-102", PatientPhase.ACTIVE_TREATMENT, 140, 5, 12, 0, False, None, None),
            ("P006", EYLEA_TRIAL_ID, "SITE-102", PatientPhase.ENROLLED, 30, 1, 12, 0, False, None, None),
            ("P007", EYLEA_TRIAL_ID, "SITE-105", PatientPhase.ACTIVE_TREATMENT, 170, 7, 12, 1, False, None, None),
            ("P008", EYLEA_TRIAL_ID, "SITE-105", PatientPhase.ACTIVE_TREATMENT, 165, 7, 12, 0, False, None, None),
            ("P009", EYLEA_TRIAL_ID, "SITE-105", PatientPhase.COMPLETED, 220, 12, 12, 0, False, None, None),
            ("P010", EYLEA_TRIAL_ID, "SITE-101", PatientPhase.ACTIVE_TREATMENT, 130, 5, 12, 3, False, None, None),
            ("P011", EYLEA_TRIAL_ID, "SITE-102", PatientPhase.DROPPED_OUT, 120, 4, 12, 3, True, DropoutReason.ADVERSE_EVENT, 30),
            ("P012", EYLEA_TRIAL_ID, "SITE-105", PatientPhase.ACTIVE_TREATMENT, 90, 3, 12, 0, False, None, None),
            ("P013", EYLEA_TRIAL_ID, "SITE-101", PatientPhase.SCREENING, 10, 0, 12, 0, False, None, None),
            ("P014", EYLEA_TRIAL_ID, "SITE-102", PatientPhase.ACTIVE_TREATMENT, 110, 4, 12, 1, False, None, None),
            ("P015", EYLEA_TRIAL_ID, "SITE-105", PatientPhase.DROPPED_OUT, 100, 3, 12, 4, True, DropoutReason.TRAVEL_DISTANCE, 20),
            # Dupixent patients (15) - SITE-103, SITE-106, SITE-108
            ("P016", DUPIXENT_TRIAL_ID, "SITE-103", PatientPhase.ACTIVE_TREATMENT, 200, 9, 14, 0, False, None, None),
            ("P017", DUPIXENT_TRIAL_ID, "SITE-103", PatientPhase.ACTIVE_TREATMENT, 190, 8, 14, 1, False, None, None),
            ("P018", DUPIXENT_TRIAL_ID, "SITE-103", PatientPhase.FOLLOW_UP, 210, 12, 14, 0, False, None, None),
            ("P019", DUPIXENT_TRIAL_ID, "SITE-106", PatientPhase.ACTIVE_TREATMENT, 175, 7, 14, 2, False, None, None),
            ("P020", DUPIXENT_TRIAL_ID, "SITE-106", PatientPhase.ACTIVE_TREATMENT, 160, 6, 14, 0, False, None, None),
            ("P021", DUPIXENT_TRIAL_ID, "SITE-106", PatientPhase.ENROLLED, 20, 0, 14, 0, False, None, None),
            ("P022", DUPIXENT_TRIAL_ID, "SITE-108", PatientPhase.ACTIVE_TREATMENT, 185, 8, 14, 1, False, None, None),
            ("P023", DUPIXENT_TRIAL_ID, "SITE-108", PatientPhase.COMPLETED, 250, 14, 14, 0, False, None, None),
            ("P024", DUPIXENT_TRIAL_ID, "SITE-103", PatientPhase.ACTIVE_TREATMENT, 145, 5, 14, 3, False, None, None),
            ("P025", DUPIXENT_TRIAL_ID, "SITE-106", PatientPhase.DROPPED_OUT, 130, 4, 14, 5, True, DropoutReason.PROTOCOL_BURDEN, 25),
            ("P026", DUPIXENT_TRIAL_ID, "SITE-108", PatientPhase.ACTIVE_TREATMENT, 100, 4, 14, 0, False, None, None),
            ("P027", DUPIXENT_TRIAL_ID, "SITE-103", PatientPhase.SCREENING, 5, 0, 14, 0, False, None, None),
            ("P028", DUPIXENT_TRIAL_ID, "SITE-108", PatientPhase.ACTIVE_TREATMENT, 80, 3, 14, 1, False, None, None),
            # Libtayo patients (12) - SITE-104, SITE-107
            ("P029", LIBTAYO_TRIAL_ID, "SITE-104", PatientPhase.ACTIVE_TREATMENT, 170, 6, 10, 0, False, None, None),
            ("P030", LIBTAYO_TRIAL_ID, "SITE-104", PatientPhase.ACTIVE_TREATMENT, 155, 5, 10, 1, False, None, None),
            ("P031", LIBTAYO_TRIAL_ID, "SITE-104", PatientPhase.FOLLOW_UP, 220, 8, 10, 0, False, None, None),
            ("P032", LIBTAYO_TRIAL_ID, "SITE-107", PatientPhase.ACTIVE_TREATMENT, 140, 5, 10, 2, False, None, None),
            ("P033", LIBTAYO_TRIAL_ID, "SITE-107", PatientPhase.ACTIVE_TREATMENT, 130, 4, 10, 0, False, None, None),
            ("P034", LIBTAYO_TRIAL_ID, "SITE-107", PatientPhase.ENROLLED, 15, 0, 10, 0, False, None, None),
            ("P035", LIBTAYO_TRIAL_ID, "SITE-104", PatientPhase.ACTIVE_TREATMENT, 120, 4, 10, 1, False, None, None),
            ("P036", LIBTAYO_TRIAL_ID, "SITE-107", PatientPhase.COMPLETED, 260, 10, 10, 0, False, None, None),
            ("P037", LIBTAYO_TRIAL_ID, "SITE-104", PatientPhase.DROPPED_OUT, 110, 3, 10, 4, True, DropoutReason.LACK_OF_EFFICACY, 40),
            ("P038", LIBTAYO_TRIAL_ID, "SITE-107", PatientPhase.ACTIVE_TREATMENT, 75, 2, 10, 0, False, None, None),
            ("P039", LIBTAYO_TRIAL_ID, "SITE-104", PatientPhase.DROPPED_OUT, 95, 3, 10, 3, True, DropoutReason.WITHDRAWAL_CONSENT, 15),
            ("P040", LIBTAYO_TRIAL_ID, "SITE-107", PatientPhase.ACTIVE_TREATMENT, 60, 2, 10, 1, False, None, None),
        ]

        for spec in patient_specs:
            (pid_suffix, trial_id, site_id, phase, enrolled_ago,
             visits_done, visits_sched, missed, dropped, reason, dropout_ago) = spec

            enrolled = today - timedelta(days=enrolled_ago)
            last_visit = today - timedelta(days=rng.randint(1, 30)) if visits_done > 0 else None
            next_visit = today + timedelta(days=rng.randint(1, 30)) if not dropped and phase not in (PatientPhase.COMPLETED, PatientPhase.SCREENING) else None
            dropout_dt = today - timedelta(days=dropout_ago) if dropout_ago else None

            profile_id = self._next_profile_id()
            profile = PatientRetentionProfile(
                id=profile_id,
                patient_id=pid_suffix,
                trial_id=trial_id,
                site_id=site_id,
                phase=phase,
                enrolled_date=enrolled,
                last_visit_date=last_visit,
                next_visit_date=next_visit,
                visits_completed=visits_done,
                visits_scheduled=visits_sched,
                missed_visits=missed,
                risk_level=RetentionRiskLevel.MINIMAL,
                risk_score=0.0,
                risk_factors=[],
                interventions_applied=[],
                dropped_out=dropped,
                dropout_date=dropout_dt,
                dropout_reason=reason,
            )
            self._profiles[profile_id] = profile

        # Calculate risk scores for all profiles
        for profile_id in list(self._profiles.keys()):
            self._calculate_risk_score(profile_id)

        # Seed 25 interventions across at-risk patients
        intervention_specs = [
            ("P002", InterventionType.PHONE_CALL, 14, "Dr. Smith", "Patient rescheduled", 25.0),
            ("P004", InterventionType.TRANSPORTATION_ASSISTANCE, 20, "Coordinator", "Arranged ride service", 150.0),
            ("P004", InterventionType.PHONE_CALL, 10, "Nurse Jones", "Confirmed next visit", 25.0),
            ("P007", InterventionType.REMINDER_SYSTEM, 30, "System", "Automated reminders enabled", 5.0),
            ("P010", InterventionType.HOME_VISIT, 15, "Dr. Garcia", "Patient visited at home", 350.0),
            ("P010", InterventionType.SCHEDULE_FLEXIBILITY, 10, "Coordinator", "Moved to evening slots", 0.0),
            ("P010", InterventionType.PHONE_CALL, 5, "Nurse Adams", "Follow-up call", 25.0),
            ("P014", InterventionType.TELEHEALTH_OPTION, 25, "Dr. Lee", "Switched to telehealth visits", 0.0),
            ("P017", InterventionType.PATIENT_EDUCATION, 30, "Educator", "Provided trial education materials", 50.0),
            ("P019", InterventionType.TRANSPORTATION_ASSISTANCE, 18, "Coordinator", "Uber Health arranged", 120.0),
            ("P019", InterventionType.PHONE_CALL, 8, "Nurse Chen", "Check-in call", 25.0),
            ("P022", InterventionType.REMINDER_SYSTEM, 35, "System", "SMS reminders activated", 5.0),
            ("P024", InterventionType.HOME_VISIT, 12, "Dr. Patel", "Home visit completed", 350.0),
            ("P024", InterventionType.FINANCIAL_SUPPORT, 8, "Admin", "Copay assistance approved", 500.0),
            ("P024", InterventionType.CAREGIVER_SUPPORT, 5, "Social Worker", "Caregiver training provided", 200.0),
            ("P028", InterventionType.SCHEDULE_FLEXIBILITY, 20, "Coordinator", "Weekend appointments", 0.0),
            ("P030", InterventionType.PHONE_CALL, 22, "Nurse Taylor", "Reassurance call", 25.0),
            ("P032", InterventionType.TRANSPORTATION_ASSISTANCE, 16, "Coordinator", "Shuttle arranged", 100.0),
            ("P032", InterventionType.GIFT_CARD, 10, "Admin", "$50 gas card provided", 50.0),
            ("P035", InterventionType.TELEHEALTH_OPTION, 30, "Dr. Kim", "Partial telehealth visits", 0.0),
            ("P040", InterventionType.PATIENT_EDUCATION, 20, "Educator", "One-on-one education session", 75.0),
            ("P040", InterventionType.REMINDER_SYSTEM, 15, "System", "Calendar integration set up", 5.0),
            ("P011", InterventionType.PHONE_CALL, 45, "Nurse Brown", "Pre-dropout outreach", 25.0),
            ("P025", InterventionType.HOME_VISIT, 35, "Dr. Wilson", "Attempted retention visit", 350.0),
            ("P037", InterventionType.PHONE_CALL, 50, "Dr. Martinez", "Pre-dropout counseling", 25.0),
        ]

        for spec in intervention_specs:
            pid, itype, days_ago, applied_by, outcome, cost = spec
            intv_id = self._next_intervention_id()
            intv = RetentionIntervention(
                id=intv_id,
                patient_id=pid,
                intervention_type=itype,
                applied_date=today - timedelta(days=days_ago),
                applied_by=applied_by,
                outcome=outcome,
                notes=f"Intervention for patient {pid}",
                cost=cost,
            )
            self._interventions[intv_id] = intv

            # Link intervention to profile
            for profile in self._profiles.values():
                if profile.patient_id == pid:
                    profile.interventions_applied.append(intv_id)
                    break

    # ------------------------------------------------------------------
    # Risk scoring
    # ------------------------------------------------------------------

    def _calculate_risk_score(self, profile_id: str) -> None:
        """Calculate weighted risk score for a patient profile.

        Weights:
            missed_visits:      25%
            days_since_visit:   20%
            protocol_burden:    15%
            distance:           15%
            adverse_events:     15%
            demographics:       10%
        """
        profile = self._profiles.get(profile_id)
        if profile is None:
            return

        today = date.today()
        risk_factors: list[RetentionRiskFactor] = []

        # 1. Missed visits factor (25%)
        if profile.visits_scheduled > 0:
            miss_ratio = profile.missed_visits / profile.visits_scheduled
            miss_score = min(miss_ratio * 200, 100.0)  # 50% missed = 100 score
        else:
            miss_score = 0.0
        risk_factors.append(RetentionRiskFactor(
            factor_name="missed_visits",
            weight=0.25,
            score=miss_score,
            description=f"{profile.missed_visits} missed out of {profile.visits_scheduled} scheduled visits",
        ))

        # 2. Days since last visit factor (20%)
        if profile.last_visit_date:
            days_since = (today - profile.last_visit_date).days
            visit_score = min(days_since / 60 * 100, 100.0)  # 60+ days = max risk
        else:
            visit_score = 50.0 if profile.visits_completed == 0 else 80.0
        risk_factors.append(RetentionRiskFactor(
            factor_name="days_since_last_visit",
            weight=0.20,
            score=visit_score,
            description=f"Days since last visit: {(today - profile.last_visit_date).days if profile.last_visit_date else 'N/A'}",
        ))

        # 3. Protocol burden factor (15%)
        burden_score = min(profile.visits_scheduled / 14 * 60, 100.0)  # High schedule = high burden
        if profile.missed_visits >= 2:
            burden_score = min(burden_score + 20, 100.0)
        risk_factors.append(RetentionRiskFactor(
            factor_name="protocol_burden",
            weight=0.15,
            score=burden_score,
            description=f"Protocol requires {profile.visits_scheduled} visits with {profile.missed_visits} missed",
        ))

        # 4. Distance/travel factor (15%) - simulated based on site
        distance_scores = {
            "SITE-101": 20.0, "SITE-102": 35.0, "SITE-103": 25.0, "SITE-104": 40.0,
            "SITE-105": 15.0, "SITE-106": 30.0, "SITE-107": 45.0, "SITE-108": 20.0,
        }
        dist_score = distance_scores.get(profile.site_id, 30.0)
        risk_factors.append(RetentionRiskFactor(
            factor_name="travel_distance",
            weight=0.15,
            score=dist_score,
            description=f"Travel burden score for site {profile.site_id}",
        ))

        # 5. Adverse event proxy factor (15%)
        ae_score = 0.0
        if profile.dropped_out and profile.dropout_reason == DropoutReason.ADVERSE_EVENT:
            ae_score = 100.0
        elif profile.missed_visits >= 3:
            ae_score = 40.0
        elif profile.missed_visits >= 1:
            ae_score = 15.0
        risk_factors.append(RetentionRiskFactor(
            factor_name="adverse_events",
            weight=0.15,
            score=ae_score,
            description="Adverse event risk proxy based on visit patterns",
        ))

        # 6. Demographics factor (10%) - simulated
        demo_score = 20.0  # Base demographic risk
        enrolled_days = (today - profile.enrolled_date).days
        if enrolled_days > 180:
            demo_score += 10.0  # Longer enrollment = fatigue risk
        risk_factors.append(RetentionRiskFactor(
            factor_name="demographics",
            weight=0.10,
            score=min(demo_score, 100.0),
            description="Demographic and enrollment duration risk factors",
        ))

        # Calculate composite score
        composite = sum(f.weight * f.score for f in risk_factors)

        # Dropped-out patients always have max risk
        if profile.dropped_out:
            composite = 95.0

        # Completed patients always have minimal risk
        if profile.phase == PatientPhase.COMPLETED:
            composite = 5.0

        # Determine risk level
        if composite >= 75:
            level = RetentionRiskLevel.VERY_HIGH
        elif composite >= 55:
            level = RetentionRiskLevel.HIGH
        elif composite >= 35:
            level = RetentionRiskLevel.MODERATE
        elif composite >= 15:
            level = RetentionRiskLevel.LOW
        else:
            level = RetentionRiskLevel.MINIMAL

        profile.risk_score = round(composite, 2)
        profile.risk_level = level
        profile.risk_factors = risk_factors

    # ------------------------------------------------------------------
    # Profile CRUD
    # ------------------------------------------------------------------

    def list_profiles(
        self,
        trial_id: Optional[str] = None,
        site_id: Optional[str] = None,
        phase: Optional[PatientPhase] = None,
        risk_level: Optional[RetentionRiskLevel] = None,
    ) -> list[PatientRetentionProfile]:
        """List all patient retention profiles with optional filters."""
        with self._lock:
            profiles = list(self._profiles.values())

        if trial_id:
            profiles = [p for p in profiles if p.trial_id == trial_id]
        if site_id:
            profiles = [p for p in profiles if p.site_id == site_id]
        if phase:
            profiles = [p for p in profiles if p.phase == phase]
        if risk_level:
            profiles = [p for p in profiles if p.risk_level == risk_level]

        return profiles

    def get_profile(self, profile_id: str) -> Optional[PatientRetentionProfile]:
        """Get a single patient retention profile by ID."""
        with self._lock:
            return self._profiles.get(profile_id)

    def get_profile_by_patient(self, patient_id: str, trial_id: Optional[str] = None) -> Optional[PatientRetentionProfile]:
        """Get a patient retention profile by patient ID and optional trial ID."""
        with self._lock:
            for profile in self._profiles.values():
                if profile.patient_id == patient_id:
                    if trial_id is None or profile.trial_id == trial_id:
                        return profile
        return None

    def create_profile(self, request: ProfileCreateRequest) -> PatientRetentionProfile:
        """Create a new patient retention profile."""
        with self._lock:
            profile_id = self._next_profile_id()
            profile = PatientRetentionProfile(
                id=profile_id,
                patient_id=request.patient_id,
                trial_id=request.trial_id,
                site_id=request.site_id,
                phase=request.phase,
                enrolled_date=request.enrolled_date,
                visits_scheduled=request.visits_scheduled,
            )
            self._profiles[profile_id] = profile
            self._calculate_risk_score(profile_id)
            return self._profiles[profile_id]

    def update_profile(self, profile_id: str, request: ProfileUpdateRequest) -> Optional[PatientRetentionProfile]:
        """Update an existing patient retention profile."""
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return None

            if request.phase is not None:
                profile.phase = request.phase
            if request.last_visit_date is not None:
                profile.last_visit_date = request.last_visit_date
            if request.next_visit_date is not None:
                profile.next_visit_date = request.next_visit_date
            if request.visits_completed is not None:
                profile.visits_completed = request.visits_completed
            if request.missed_visits is not None:
                profile.missed_visits = request.missed_visits
            if request.dropped_out is not None:
                profile.dropped_out = request.dropped_out
            if request.dropout_date is not None:
                profile.dropout_date = request.dropout_date
            if request.dropout_reason is not None:
                profile.dropout_reason = request.dropout_reason

            self._calculate_risk_score(profile_id)
            return self._profiles[profile_id]

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a patient retention profile."""
        with self._lock:
            if profile_id in self._profiles:
                del self._profiles[profile_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Dropout prediction
    # ------------------------------------------------------------------

    def predict_dropout(self, patient_id: str) -> Optional[DropoutPrediction]:
        """Generate a dropout prediction for a patient using the weighted risk model."""
        profile = self.get_profile_by_patient(patient_id)
        if profile is None:
            return None

        # Use existing risk factors sorted by weighted contribution
        sorted_factors = sorted(
            profile.risk_factors,
            key=lambda f: f.weight * f.score,
            reverse=True,
        )
        top_factors = sorted_factors[:3]

        # Recommend interventions based on top risk factors
        recommendations: list[InterventionType] = []
        for factor in top_factors:
            if factor.factor_name == "missed_visits" and factor.score > 30:
                recommendations.append(InterventionType.REMINDER_SYSTEM)
                recommendations.append(InterventionType.PHONE_CALL)
            elif factor.factor_name == "days_since_last_visit" and factor.score > 30:
                recommendations.append(InterventionType.PHONE_CALL)
                recommendations.append(InterventionType.HOME_VISIT)
            elif factor.factor_name == "protocol_burden" and factor.score > 30:
                recommendations.append(InterventionType.SCHEDULE_FLEXIBILITY)
                recommendations.append(InterventionType.TELEHEALTH_OPTION)
            elif factor.factor_name == "travel_distance" and factor.score > 30:
                recommendations.append(InterventionType.TRANSPORTATION_ASSISTANCE)
                recommendations.append(InterventionType.TELEHEALTH_OPTION)
            elif factor.factor_name == "adverse_events" and factor.score > 30:
                recommendations.append(InterventionType.PATIENT_EDUCATION)
                recommendations.append(InterventionType.CAREGIVER_SUPPORT)
            elif factor.factor_name == "demographics" and factor.score > 30:
                recommendations.append(InterventionType.FINANCIAL_SUPPORT)
                recommendations.append(InterventionType.GIFT_CARD)

        # Deduplicate while preserving order
        seen = set()
        unique_recs = []
        for r in recommendations:
            if r not in seen:
                seen.add(r)
                unique_recs.append(r)

        # Confidence based on data completeness
        data_points = sum(1 for f in profile.risk_factors if f.score > 0)
        confidence = min(0.5 + data_points * 0.08, 0.95)

        return DropoutPrediction(
            patient_id=patient_id,
            risk_score=profile.risk_score,
            risk_level=profile.risk_level,
            top_risk_factors=top_factors,
            recommended_interventions=unique_recs,
            prediction_confidence=round(confidence, 2),
            prediction_date=date.today(),
        )

    # ------------------------------------------------------------------
    # Kaplan-Meier survival curve
    # ------------------------------------------------------------------

    def generate_retention_curve(self, trial_id: str) -> Optional[RetentionCurve]:
        """Generate a Kaplan-Meier retention survival curve for a trial."""
        profiles = self.list_profiles(trial_id=trial_id)
        if not profiles:
            return None

        today = date.today()

        # Build time-to-event data
        events: list[tuple[int, bool]] = []  # (days, is_event)
        for p in profiles:
            if p.dropped_out and p.dropout_date:
                days = (p.dropout_date - p.enrolled_date).days
                events.append((days, True))
            else:
                days = (today - p.enrolled_date).days
                events.append((days, False))  # censored

        events.sort(key=lambda x: x[0])

        # Generate KM curve points
        n_at_risk = len(events)
        survival = 1.0
        curve_points: list[RetentionCurvePoint] = []

        # Add day 0
        curve_points.append(RetentionCurvePoint(
            day=0, patients_at_risk=n_at_risk,
            events=0, censored=0, survival_probability=1.0,
        ))

        # Group events by day
        day_events: dict[int, tuple[int, int]] = {}  # day -> (events, censored)
        for day_val, is_event in events:
            if day_val not in day_events:
                day_events[day_val] = (0, 0)
            ev, cen = day_events[day_val]
            if is_event:
                day_events[day_val] = (ev + 1, cen)
            else:
                day_events[day_val] = (ev, cen + 1)

        for day_val in sorted(day_events.keys()):
            ev_count, cen_count = day_events[day_val]
            if n_at_risk > 0 and ev_count > 0:
                survival *= (1 - ev_count / n_at_risk)
            n_at_risk -= (ev_count + cen_count)
            curve_points.append(RetentionCurvePoint(
                day=day_val, patients_at_risk=max(n_at_risk, 0),
                events=ev_count, censored=cen_count,
                survival_probability=round(max(survival, 0), 4),
            ))

        # Extract landmark retention rates
        def _get_retention_at(day_target: int) -> Optional[float]:
            last_prob = 1.0
            for pt in curve_points:
                if pt.day <= day_target:
                    last_prob = pt.survival_probability
                else:
                    break
            return round(last_prob, 4) if day_target <= max(p.day for p in curve_points) else None

        # Median retention: first day survival drops below 0.5
        median_days = None
        for pt in curve_points:
            if pt.survival_probability < 0.5:
                median_days = pt.day
                break

        return RetentionCurve(
            trial_id=trial_id,
            data_points=curve_points,
            kaplan_meier_estimate=round(survival, 4),
            median_retention_days=median_days,
            retention_at_30d=_get_retention_at(30),
            retention_at_90d=_get_retention_at(90),
            retention_at_180d=_get_retention_at(180),
            retention_at_365d=_get_retention_at(365),
        )

    # ------------------------------------------------------------------
    # Intervention management
    # ------------------------------------------------------------------

    def list_interventions(
        self,
        patient_id: Optional[str] = None,
        intervention_type: Optional[InterventionType] = None,
    ) -> list[RetentionIntervention]:
        """List all interventions with optional filters."""
        with self._lock:
            interventions = list(self._interventions.values())

        if patient_id:
            interventions = [i for i in interventions if i.patient_id == patient_id]
        if intervention_type:
            interventions = [i for i in interventions if i.intervention_type == intervention_type]

        return interventions

    def get_intervention(self, intervention_id: str) -> Optional[RetentionIntervention]:
        """Get a single intervention by ID."""
        with self._lock:
            return self._interventions.get(intervention_id)

    def create_intervention(self, request: InterventionCreateRequest) -> RetentionIntervention:
        """Create a new retention intervention."""
        with self._lock:
            intv_id = self._next_intervention_id()
            intv = RetentionIntervention(
                id=intv_id,
                patient_id=request.patient_id,
                intervention_type=request.intervention_type,
                applied_date=date.today(),
                applied_by=request.applied_by,
                notes=request.notes,
                cost=request.cost,
            )
            self._interventions[intv_id] = intv

            # Link to patient profile
            for profile in self._profiles.values():
                if profile.patient_id == request.patient_id:
                    profile.interventions_applied.append(intv_id)
                    break

            return intv

    def update_intervention(self, intervention_id: str, request: InterventionUpdateRequest) -> Optional[RetentionIntervention]:
        """Update an intervention outcome."""
        with self._lock:
            intv = self._interventions.get(intervention_id)
            if intv is None:
                return None

            if request.outcome is not None:
                intv.outcome = request.outcome
            if request.notes is not None:
                intv.notes = request.notes

            return intv

    # ------------------------------------------------------------------
    # Site retention comparison
    # ------------------------------------------------------------------

    def get_site_comparisons(self, trial_id: Optional[str] = None) -> list[SiteRetentionComparison]:
        """Compare retention rates across sites."""
        profiles = self.list_profiles(trial_id=trial_id)
        if not profiles:
            return []

        today = date.today()
        site_data: dict[str, dict] = defaultdict(lambda: {
            "total": 0, "dropped": 0, "days": [], "interventions": 0, "cost": 0.0,
        })

        for p in profiles:
            sd = site_data[p.site_id]
            sd["total"] += 1
            if p.dropped_out:
                sd["dropped"] += 1
            days_retained = (today - p.enrolled_date).days
            if p.dropped_out and p.dropout_date:
                days_retained = (p.dropout_date - p.enrolled_date).days
            sd["days"].append(days_retained)

        # Count interventions by site
        with self._lock:
            for intv in self._interventions.values():
                for p in profiles:
                    if p.patient_id == intv.patient_id:
                        site_data[p.site_id]["interventions"] += 1
                        site_data[p.site_id]["cost"] += intv.cost
                        break

        comparisons = []
        for sid, data in site_data.items():
            total = data["total"]
            dropped = data["dropped"]
            retained = total - dropped
            avg_days = sum(data["days"]) / len(data["days"]) if data["days"] else 0
            cost_per = data["cost"] / retained if retained > 0 else 0.0

            comparisons.append(SiteRetentionComparison(
                site_id=sid,
                site_name=SITES.get(sid, sid),
                retention_rate=round((total - dropped) / total, 4) if total > 0 else 0.0,
                dropout_rate=round(dropped / total, 4) if total > 0 else 0.0,
                avg_days_retained=round(avg_days, 1),
                intervention_count=data["interventions"],
                cost_per_retained=round(cost_per, 2),
            ))

        return sorted(comparisons, key=lambda c: c.retention_rate, reverse=True)

    # ------------------------------------------------------------------
    # Retention dashboard
    # ------------------------------------------------------------------

    def get_retention_metrics(self, trial_id: Optional[str] = None) -> RetentionMetrics:
        """Compute aggregate retention metrics."""
        profiles = self.list_profiles(trial_id=trial_id)
        today = date.today()

        total = len(profiles)
        dropped = sum(1 for p in profiles if p.dropped_out)
        completed = sum(1 for p in profiles if p.phase == PatientPhase.COMPLETED)
        active = total - dropped - completed
        screening = sum(1 for p in profiles if p.phase == PatientPhase.SCREENING)
        active = active - screening  # Don't count screening patients as active

        avg_risk = sum(p.risk_score for p in profiles) / total if total > 0 else 0.0
        high_risk = sum(1 for p in profiles if p.risk_level in (RetentionRiskLevel.HIGH, RetentionRiskLevel.VERY_HIGH))

        # Calculate days retained
        days_list = []
        for p in profiles:
            if p.dropped_out and p.dropout_date:
                days_list.append((p.dropout_date - p.enrolled_date).days)
            else:
                days_list.append((today - p.enrolled_date).days)
        avg_days = sum(days_list) / len(days_list) if days_list else 0

        # Intervention costs
        with self._lock:
            all_interventions = list(self._interventions.values())

        if trial_id:
            patient_ids = {p.patient_id for p in profiles}
            relevant_interventions = [i for i in all_interventions if i.patient_id in patient_ids]
        else:
            relevant_interventions = all_interventions

        total_cost = sum(i.cost for i in relevant_interventions)
        retained_count = total - dropped
        cost_per_retained = total_cost / retained_count if retained_count > 0 else 0.0

        retention_rate = (total - dropped) / total if total > 0 else 0.0
        dropout_rate = dropped / total if total > 0 else 0.0

        return RetentionMetrics(
            total_patients=total,
            active_patients=active,
            dropped_out_patients=dropped,
            completed_patients=completed,
            overall_retention_rate=round(retention_rate, 4),
            overall_dropout_rate=round(dropout_rate, 4),
            avg_risk_score=round(avg_risk, 2),
            high_risk_count=high_risk,
            total_interventions=len(relevant_interventions),
            total_intervention_cost=round(total_cost, 2),
            cost_per_retained_patient=round(cost_per_retained, 2),
            avg_days_retained=round(avg_days, 1),
        )

    def get_dashboard(self, trial_id: Optional[str] = None) -> RetentionDashboard:
        """Generate a comprehensive retention dashboard."""
        profiles = self.list_profiles(trial_id=trial_id)

        # Risk distribution
        risk_dist: dict[str, int] = defaultdict(int)
        for p in profiles:
            risk_dist[p.risk_level.value] += 1

        # Phase distribution
        phase_dist: dict[str, int] = defaultdict(int)
        for p in profiles:
            phase_dist[p.phase.value] += 1

        # Dropout reasons
        dropout_reasons: dict[str, int] = defaultdict(int)
        for p in profiles:
            if p.dropped_out and p.dropout_reason:
                dropout_reasons[p.dropout_reason.value] += 1

        # Top risk patients (non-dropped-out, sorted by risk score desc)
        at_risk = sorted(
            [p for p in profiles if not p.dropped_out and p.phase != PatientPhase.COMPLETED],
            key=lambda p: p.risk_score,
            reverse=True,
        )[:10]

        # Site comparisons
        site_comps = self.get_site_comparisons(trial_id=trial_id)

        # Intervention effectiveness
        effectiveness = self.get_intervention_effectiveness(trial_id=trial_id)

        # Retention curves
        trial_ids = list({p.trial_id for p in profiles})
        curves = []
        for tid in trial_ids:
            curve = self.generate_retention_curve(tid)
            if curve:
                curves.append(curve)

        return RetentionDashboard(
            metrics=self.get_retention_metrics(trial_id=trial_id),
            risk_distribution=dict(risk_dist),
            phase_distribution=dict(phase_dist),
            dropout_reasons=dict(dropout_reasons),
            site_comparisons=site_comps,
            top_risk_patients=at_risk,
            intervention_effectiveness=effectiveness,
            retention_curves=curves,
        )

    # ------------------------------------------------------------------
    # Cohort analysis
    # ------------------------------------------------------------------

    def get_cohort_analysis(
        self,
        group_by: RetentionMetricType = RetentionMetricType.BY_TRIAL,
        trial_id: Optional[str] = None,
    ) -> list[CohortAnalysis]:
        """Analyze retention by cohort grouping."""
        profiles = self.list_profiles(trial_id=trial_id)
        if not profiles:
            return []

        today = date.today()
        cohorts: dict[str, list[PatientRetentionProfile]] = defaultdict(list)

        if group_by == RetentionMetricType.BY_TRIAL:
            trial_names = {
                EYLEA_TRIAL_ID: "EYLEA HD",
                DUPIXENT_TRIAL_ID: "Dupixent",
                LIBTAYO_TRIAL_ID: "Libtayo",
            }
            for p in profiles:
                cohorts[trial_names.get(p.trial_id, p.trial_id)].append(p)

        elif group_by == RetentionMetricType.BY_SITE:
            for p in profiles:
                name = SITES.get(p.site_id, p.site_id)
                cohorts[name].append(p)

        elif group_by == RetentionMetricType.BY_PHASE:
            for p in profiles:
                cohorts[p.phase.value].append(p)

        elif group_by == RetentionMetricType.BY_DEMOGRAPHICS:
            # Simulate demographic cohorts based on enrollment duration
            for p in profiles:
                days = (today - p.enrolled_date).days
                if days < 60:
                    cohorts["Recently Enrolled (<60d)"].append(p)
                elif days < 120:
                    cohorts["Mid-term (60-120d)"].append(p)
                elif days < 200:
                    cohorts["Long-term (120-200d)"].append(p)
                else:
                    cohorts["Extended (200d+)"].append(p)

        else:  # OVERALL
            cohorts["All Patients"] = profiles

        results = []
        for name, members in cohorts.items():
            total = len(members)
            dropped = sum(1 for p in members if p.dropped_out)
            retained = total - dropped
            avg_risk = sum(p.risk_score for p in members) / total if total > 0 else 0.0

            days_list = []
            for p in members:
                if p.dropped_out and p.dropout_date:
                    days_list.append((p.dropout_date - p.enrolled_date).days)
                else:
                    days_list.append((today - p.enrolled_date).days)
            avg_days = sum(days_list) / len(days_list) if days_list else 0

            # Count interventions for this cohort
            patient_ids = {p.patient_id for p in members}
            with self._lock:
                intv_count = sum(1 for i in self._interventions.values() if i.patient_id in patient_ids)

            results.append(CohortAnalysis(
                cohort_name=name,
                cohort_size=total,
                retention_rate=round(retained / total, 4) if total > 0 else 0.0,
                dropout_rate=round(dropped / total, 4) if total > 0 else 0.0,
                avg_risk_score=round(avg_risk, 2),
                avg_days_retained=round(avg_days, 1),
                intervention_count=intv_count,
            ))

        return sorted(results, key=lambda c: c.retention_rate, reverse=True)

    # ------------------------------------------------------------------
    # Intervention effectiveness
    # ------------------------------------------------------------------

    def get_intervention_effectiveness(self, trial_id: Optional[str] = None) -> list[InterventionEffectiveness]:
        """Analyze the effectiveness of each intervention type."""
        profiles = self.list_profiles(trial_id=trial_id)
        patient_ids = {p.patient_id for p in profiles} if trial_id else None

        with self._lock:
            if patient_ids is not None:
                interventions = [i for i in self._interventions.values() if i.patient_id in patient_ids]
            else:
                interventions = list(self._interventions.values())

        # Group by type
        type_data: dict[InterventionType, dict] = {}
        for itype in InterventionType:
            type_intv = [i for i in interventions if i.intervention_type == itype]
            if not type_intv:
                continue

            total = len(type_intv)
            successful = sum(1 for i in type_intv if i.outcome and "fail" not in i.outcome.lower())
            total_cost = sum(i.cost for i in type_intv)
            avg_cost = total_cost / total if total > 0 else 0.0

            # Check patient retention after intervention
            retained = 0
            dropped = 0
            for intv in type_intv:
                for p in profiles:
                    if p.patient_id == intv.patient_id:
                        if p.dropped_out:
                            dropped += 1
                        else:
                            retained += 1
                        break

            type_data[itype] = InterventionEffectiveness(
                intervention_type=itype,
                total_applied=total,
                successful_outcomes=successful,
                success_rate=round(successful / total, 4) if total > 0 else 0.0,
                avg_cost=round(avg_cost, 2),
                total_cost=round(total_cost, 2),
                retained_after=retained,
                dropped_after=dropped,
            )

        return sorted(type_data.values(), key=lambda e: e.success_rate, reverse=True)

    # ------------------------------------------------------------------
    # Cost per retained patient
    # ------------------------------------------------------------------

    def get_cost_per_retained(self, trial_id: Optional[str] = None) -> dict:
        """Calculate cost-per-retained-patient metrics."""
        profiles = self.list_profiles(trial_id=trial_id)
        total = len(profiles)
        dropped = sum(1 for p in profiles if p.dropped_out)
        retained = total - dropped

        patient_ids = {p.patient_id for p in profiles}
        with self._lock:
            relevant_interventions = [
                i for i in self._interventions.values() if i.patient_id in patient_ids
            ]

        total_cost = sum(i.cost for i in relevant_interventions)
        cost_per = total_cost / retained if retained > 0 else 0.0

        # Cost by intervention type
        cost_by_type: dict[str, float] = defaultdict(float)
        for i in relevant_interventions:
            cost_by_type[i.intervention_type.value] += i.cost

        return {
            "total_patients": total,
            "retained_patients": retained,
            "dropped_patients": dropped,
            "total_intervention_cost": round(total_cost, 2),
            "cost_per_retained_patient": round(cost_per, 2),
            "cost_by_intervention_type": dict(cost_by_type),
            "interventions_per_patient": round(len(relevant_interventions) / total, 2) if total > 0 else 0.0,
        }

    # ------------------------------------------------------------------
    # Batch risk recalculation
    # ------------------------------------------------------------------

    def recalculate_all_risks(self) -> dict:
        """Recalculate risk scores for all profiles."""
        with self._lock:
            profile_ids = list(self._profiles.keys())

        for pid in profile_ids:
            self._calculate_risk_score(pid)

        profiles = self.list_profiles()
        risk_dist = defaultdict(int)
        for p in profiles:
            risk_dist[p.risk_level.value] += 1

        return {
            "profiles_updated": len(profile_ids),
            "risk_distribution": dict(risk_dist),
        }


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_instance: PatientRetentionService | None = None
_instance_lock = threading.Lock()


def get_patient_retention_service() -> PatientRetentionService:
    """Return the module-level singleton, creating it on first call."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientRetentionService()
    return _instance


def reset_patient_retention_service() -> PatientRetentionService:
    """Reset the singleton with fresh seed data (useful for tests)."""
    global _instance
    with _instance_lock:
        _instance = PatientRetentionService()
    return _instance
