"""Tests for Patient Retention Analytics (CMO-12).

Covers:
- Seed data verification (40 profiles, 25 interventions, 3 trials, 8 sites)
- Profile CRUD (create, read, update, delete, filters)
- Risk scoring (weighted model, factor contributions, level classification)
- Dropout prediction (risk factors, recommendations, confidence)
- Kaplan-Meier retention curves (survival probabilities, landmarks)
- Intervention management (CRUD, linking to profiles)
- Site retention comparisons
- Retention metrics (aggregate calculations)
- Retention dashboard (comprehensive analytics)
- Cohort analysis (by trial, site, phase, demographics)
- Intervention effectiveness analysis
- Cost-per-retained-patient calculation
- Batch risk recalculation
- API integration (all 19 endpoints)
- Error handling (404s, invalid inputs)
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
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
    RetentionMetricType,
    RetentionMetrics,
    RetentionRiskFactor,
    RetentionRiskLevel,
    SiteRetentionComparison,
)
from app.services.patient_retention_service import (
    DUPIXENT_TRIAL_ID,
    EYLEA_TRIAL_ID,
    LIBTAYO_TRIAL_ID,
    PatientRetentionService,
    get_patient_retention_service,
    reset_patient_retention_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/patient-retention"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_retention_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientRetentionService:
    """Shorthand for the fresh service."""
    return fresh_service


# ===========================================================================
# Section 1: Seed data verification (15 tests)
# ===========================================================================


class TestSeedData:
    """Verify the seed data is loaded correctly on service init."""

    def test_seed_forty_profiles(self, svc: PatientRetentionService):
        """Seed should contain exactly 40 patient profiles."""
        profiles = svc.list_profiles()
        assert len(profiles) == 40

    def test_seed_eylea_profiles(self, svc: PatientRetentionService):
        """EYLEA trial should have 15 patients."""
        profiles = svc.list_profiles(trial_id=EYLEA_TRIAL_ID)
        assert len(profiles) == 15

    def test_seed_dupixent_profiles(self, svc: PatientRetentionService):
        """Dupixent trial should have 13 patients."""
        profiles = svc.list_profiles(trial_id=DUPIXENT_TRIAL_ID)
        assert len(profiles) == 13

    def test_seed_libtayo_profiles(self, svc: PatientRetentionService):
        """Libtayo trial should have 12 patients."""
        profiles = svc.list_profiles(trial_id=LIBTAYO_TRIAL_ID)
        assert len(profiles) == 12

    def test_seed_25_interventions(self, svc: PatientRetentionService):
        """Seed should contain exactly 25 interventions."""
        interventions = svc.list_interventions()
        assert len(interventions) == 25

    def test_seed_five_dropouts(self, svc: PatientRetentionService):
        """Seed should contain exactly 5 dropped-out patients."""
        profiles = svc.list_profiles()
        dropped = [p for p in profiles if p.dropped_out]
        assert len(dropped) == 5

    def test_seed_dropout_reasons_documented(self, svc: PatientRetentionService):
        """All dropped-out patients should have documented dropout reasons."""
        profiles = svc.list_profiles()
        dropped = [p for p in profiles if p.dropped_out]
        for p in dropped:
            assert p.dropout_reason is not None
            assert p.dropout_date is not None

    def test_seed_profiles_have_risk_scores(self, svc: PatientRetentionService):
        """All profiles should have calculated risk scores."""
        profiles = svc.list_profiles()
        for p in profiles:
            assert p.risk_score >= 0
            assert p.risk_level is not None

    def test_seed_profiles_have_risk_factors(self, svc: PatientRetentionService):
        """All profiles should have at least one risk factor."""
        profiles = svc.list_profiles()
        for p in profiles:
            assert len(p.risk_factors) > 0

    def test_seed_eylea_sites(self, svc: PatientRetentionService):
        """EYLEA patients should be at SITE-101, SITE-102, SITE-105."""
        profiles = svc.list_profiles(trial_id=EYLEA_TRIAL_ID)
        sites = {p.site_id for p in profiles}
        assert sites == {"SITE-101", "SITE-102", "SITE-105"}

    def test_seed_dupixent_sites(self, svc: PatientRetentionService):
        """Dupixent patients should be at SITE-103, SITE-106, SITE-108."""
        profiles = svc.list_profiles(trial_id=DUPIXENT_TRIAL_ID)
        sites = {p.site_id for p in profiles}
        assert sites == {"SITE-103", "SITE-106", "SITE-108"}

    def test_seed_libtayo_sites(self, svc: PatientRetentionService):
        """Libtayo patients should be at SITE-104, SITE-107."""
        profiles = svc.list_profiles(trial_id=LIBTAYO_TRIAL_ID)
        sites = {p.site_id for p in profiles}
        assert sites == {"SITE-104", "SITE-107"}

    def test_seed_mixed_phases(self, svc: PatientRetentionService):
        """Seed data should include multiple patient phases."""
        profiles = svc.list_profiles()
        phases = {p.phase for p in profiles}
        assert PatientPhase.ACTIVE_TREATMENT in phases
        assert PatientPhase.FOLLOW_UP in phases
        assert PatientPhase.COMPLETED in phases
        assert PatientPhase.DROPPED_OUT in phases
        assert PatientPhase.ENROLLED in phases

    def test_seed_completed_patients(self, svc: PatientRetentionService):
        """Seed should have patients who completed the trial."""
        profiles = svc.list_profiles(phase=PatientPhase.COMPLETED)
        assert len(profiles) >= 3

    def test_seed_screening_patients(self, svc: PatientRetentionService):
        """Seed should have patients in screening phase."""
        profiles = svc.list_profiles(phase=PatientPhase.SCREENING)
        assert len(profiles) >= 2


# ===========================================================================
# Section 2: Profile CRUD (15 tests)
# ===========================================================================


class TestProfileCRUD:
    """Test profile create, read, update, delete operations."""

    def test_create_profile(self, svc: PatientRetentionService):
        """Should create a new profile with auto-generated ID."""
        req = ProfileCreateRequest(
            patient_id="NEW-001",
            trial_id=EYLEA_TRIAL_ID,
            site_id="SITE-101",
            enrolled_date=date.today(),
            visits_scheduled=10,
        )
        profile = svc.create_profile(req)
        assert profile.id is not None
        assert profile.patient_id == "NEW-001"
        assert profile.trial_id == EYLEA_TRIAL_ID
        assert profile.risk_score >= 0

    def test_create_profile_increments_count(self, svc: PatientRetentionService):
        """Creating a profile should increase total count."""
        initial = len(svc.list_profiles())
        req = ProfileCreateRequest(
            patient_id="NEW-002",
            trial_id=EYLEA_TRIAL_ID,
            site_id="SITE-101",
            enrolled_date=date.today(),
            visits_scheduled=8,
        )
        svc.create_profile(req)
        assert len(svc.list_profiles()) == initial + 1

    def test_get_profile_by_id(self, svc: PatientRetentionService):
        """Should retrieve a profile by its ID."""
        profiles = svc.list_profiles()
        profile = svc.get_profile(profiles[0].id)
        assert profile is not None
        assert profile.id == profiles[0].id

    def test_get_profile_nonexistent(self, svc: PatientRetentionService):
        """Should return None for nonexistent profile."""
        assert svc.get_profile("nonexistent") is None

    def test_get_profile_by_patient_id(self, svc: PatientRetentionService):
        """Should retrieve a profile by patient ID."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        assert profile.patient_id == "P001"

    def test_get_profile_by_patient_with_trial(self, svc: PatientRetentionService):
        """Should retrieve a profile by patient ID and trial ID."""
        profile = svc.get_profile_by_patient("P001", trial_id=EYLEA_TRIAL_ID)
        assert profile is not None
        assert profile.trial_id == EYLEA_TRIAL_ID

    def test_get_profile_by_patient_wrong_trial(self, svc: PatientRetentionService):
        """Should return None for patient in wrong trial."""
        profile = svc.get_profile_by_patient("P001", trial_id=DUPIXENT_TRIAL_ID)
        assert profile is None

    def test_update_profile_phase(self, svc: PatientRetentionService):
        """Should update patient phase."""
        profiles = svc.list_profiles()
        pid = profiles[0].id
        req = ProfileUpdateRequest(phase=PatientPhase.FOLLOW_UP)
        updated = svc.update_profile(pid, req)
        assert updated is not None
        assert updated.phase == PatientPhase.FOLLOW_UP

    def test_update_profile_missed_visits(self, svc: PatientRetentionService):
        """Should update missed visits and recalculate risk."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        old_score = profile.risk_score
        req = ProfileUpdateRequest(missed_visits=5)
        updated = svc.update_profile(profile.id, req)
        assert updated is not None
        assert updated.missed_visits == 5
        assert updated.risk_score != old_score

    def test_update_profile_dropout(self, svc: PatientRetentionService):
        """Should mark a patient as dropped out."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        req = ProfileUpdateRequest(
            dropped_out=True,
            dropout_date=date.today(),
            dropout_reason=DropoutReason.ADVERSE_EVENT,
            phase=PatientPhase.DROPPED_OUT,
        )
        updated = svc.update_profile(profile.id, req)
        assert updated is not None
        assert updated.dropped_out is True
        assert updated.dropout_reason == DropoutReason.ADVERSE_EVENT

    def test_update_nonexistent_profile(self, svc: PatientRetentionService):
        """Should return None when updating nonexistent profile."""
        req = ProfileUpdateRequest(phase=PatientPhase.COMPLETED)
        assert svc.update_profile("nonexistent", req) is None

    def test_delete_profile(self, svc: PatientRetentionService):
        """Should delete a profile."""
        profiles = svc.list_profiles()
        pid = profiles[0].id
        assert svc.delete_profile(pid) is True
        assert svc.get_profile(pid) is None

    def test_delete_nonexistent_profile(self, svc: PatientRetentionService):
        """Should return False when deleting nonexistent profile."""
        assert svc.delete_profile("nonexistent") is False

    def test_filter_by_trial(self, svc: PatientRetentionService):
        """Should filter profiles by trial ID."""
        profiles = svc.list_profiles(trial_id=EYLEA_TRIAL_ID)
        for p in profiles:
            assert p.trial_id == EYLEA_TRIAL_ID

    def test_filter_by_risk_level(self, svc: PatientRetentionService):
        """Should filter profiles by risk level."""
        profiles = svc.list_profiles(risk_level=RetentionRiskLevel.VERY_HIGH)
        for p in profiles:
            assert p.risk_level == RetentionRiskLevel.VERY_HIGH


# ===========================================================================
# Section 3: Risk scoring (15 tests)
# ===========================================================================


class TestRiskScoring:
    """Test the weighted risk scoring model."""

    def test_risk_factors_have_six_components(self, svc: PatientRetentionService):
        """Each profile should have 6 risk factor components."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        assert len(profile.risk_factors) == 6

    def test_risk_factor_names(self, svc: PatientRetentionService):
        """Risk factors should include all expected names."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        names = {f.factor_name for f in profile.risk_factors}
        expected = {"missed_visits", "days_since_last_visit", "protocol_burden",
                    "travel_distance", "adverse_events", "demographics"}
        assert names == expected

    def test_risk_weights_sum_to_one(self, svc: PatientRetentionService):
        """Risk factor weights should sum to 1.0."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        total = sum(f.weight for f in profile.risk_factors)
        assert abs(total - 1.0) < 0.01

    def test_missed_visits_weight_25_pct(self, svc: PatientRetentionService):
        """Missed visits factor should have 25% weight."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        factor = next(f for f in profile.risk_factors if f.factor_name == "missed_visits")
        assert factor.weight == 0.25

    def test_days_since_visit_weight_20_pct(self, svc: PatientRetentionService):
        """Days since last visit factor should have 20% weight."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        factor = next(f for f in profile.risk_factors if f.factor_name == "days_since_last_visit")
        assert factor.weight == 0.20

    def test_protocol_burden_weight_15_pct(self, svc: PatientRetentionService):
        """Protocol burden factor should have 15% weight."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        factor = next(f for f in profile.risk_factors if f.factor_name == "protocol_burden")
        assert factor.weight == 0.15

    def test_distance_weight_15_pct(self, svc: PatientRetentionService):
        """Travel distance factor should have 15% weight."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        factor = next(f for f in profile.risk_factors if f.factor_name == "travel_distance")
        assert factor.weight == 0.15

    def test_adverse_events_weight_15_pct(self, svc: PatientRetentionService):
        """Adverse events factor should have 15% weight."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        factor = next(f for f in profile.risk_factors if f.factor_name == "adverse_events")
        assert factor.weight == 0.15

    def test_demographics_weight_10_pct(self, svc: PatientRetentionService):
        """Demographics factor should have 10% weight."""
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        factor = next(f for f in profile.risk_factors if f.factor_name == "demographics")
        assert factor.weight == 0.10

    def test_dropped_out_high_risk(self, svc: PatientRetentionService):
        """Dropped-out patients should have very high risk scores."""
        profile = svc.get_profile_by_patient("P011")
        assert profile is not None
        assert profile.dropped_out is True
        assert profile.risk_score >= 90.0
        assert profile.risk_level == RetentionRiskLevel.VERY_HIGH

    def test_completed_minimal_risk(self, svc: PatientRetentionService):
        """Completed patients should have minimal risk scores."""
        profile = svc.get_profile_by_patient("P009")
        assert profile is not None
        assert profile.phase == PatientPhase.COMPLETED
        assert profile.risk_score <= 10.0
        assert profile.risk_level == RetentionRiskLevel.MINIMAL

    def test_no_missed_visits_lower_risk(self, svc: PatientRetentionService):
        """Patients with no missed visits should have lower risk than those with many."""
        p_no_miss = svc.get_profile_by_patient("P001")  # 0 missed
        p_high_miss = svc.get_profile_by_patient("P010")  # 3 missed
        assert p_no_miss is not None and p_high_miss is not None
        assert p_no_miss.risk_score < p_high_miss.risk_score

    def test_risk_score_bounded(self, svc: PatientRetentionService):
        """All risk scores should be between 0 and 100."""
        profiles = svc.list_profiles()
        for p in profiles:
            assert 0 <= p.risk_score <= 100

    def test_risk_factors_scores_bounded(self, svc: PatientRetentionService):
        """All individual risk factor scores should be between 0 and 100."""
        profiles = svc.list_profiles()
        for p in profiles:
            for f in p.risk_factors:
                assert 0 <= f.score <= 100

    def test_risk_level_classification(self, svc: PatientRetentionService):
        """Risk levels should follow score thresholds."""
        profiles = svc.list_profiles()
        for p in profiles:
            if p.dropped_out:
                assert p.risk_level == RetentionRiskLevel.VERY_HIGH
            elif p.phase == PatientPhase.COMPLETED:
                assert p.risk_level == RetentionRiskLevel.MINIMAL


# ===========================================================================
# Section 4: Dropout prediction (12 tests)
# ===========================================================================


class TestDropoutPrediction:
    """Test dropout prediction engine."""

    def test_predict_existing_patient(self, svc: PatientRetentionService):
        """Should generate prediction for existing patient."""
        pred = svc.predict_dropout("P001")
        assert pred is not None
        assert pred.patient_id == "P001"

    def test_predict_nonexistent_patient(self, svc: PatientRetentionService):
        """Should return None for nonexistent patient."""
        assert svc.predict_dropout("NONEXISTENT") is None

    def test_prediction_has_risk_score(self, svc: PatientRetentionService):
        """Prediction should include a risk score."""
        pred = svc.predict_dropout("P001")
        assert pred is not None
        assert 0 <= pred.risk_score <= 100

    def test_prediction_has_risk_level(self, svc: PatientRetentionService):
        """Prediction should include a risk level."""
        pred = svc.predict_dropout("P001")
        assert pred is not None
        assert isinstance(pred.risk_level, RetentionRiskLevel)

    def test_prediction_has_top_risk_factors(self, svc: PatientRetentionService):
        """Prediction should include top risk factors."""
        pred = svc.predict_dropout("P010")  # High risk patient
        assert pred is not None
        assert len(pred.top_risk_factors) > 0
        assert len(pred.top_risk_factors) <= 3

    def test_prediction_has_recommendations(self, svc: PatientRetentionService):
        """High-risk predictions should include recommended interventions."""
        pred = svc.predict_dropout("P010")
        assert pred is not None
        assert len(pred.recommended_interventions) > 0

    def test_prediction_confidence_bounded(self, svc: PatientRetentionService):
        """Prediction confidence should be between 0 and 1."""
        pred = svc.predict_dropout("P001")
        assert pred is not None
        assert 0 <= pred.prediction_confidence <= 1.0

    def test_prediction_date_is_today(self, svc: PatientRetentionService):
        """Prediction date should be today."""
        pred = svc.predict_dropout("P001")
        assert pred is not None
        assert pred.prediction_date == date.today()

    def test_high_risk_patient_recommendations(self, svc: PatientRetentionService):
        """High-risk patient should get specific intervention recommendations."""
        # P010 has 3 missed visits - should recommend reminder system
        pred = svc.predict_dropout("P010")
        assert pred is not None
        assert any(
            r in [InterventionType.REMINDER_SYSTEM, InterventionType.PHONE_CALL]
            for r in pred.recommended_interventions
        )

    def test_prediction_recommendations_unique(self, svc: PatientRetentionService):
        """Recommended interventions should not have duplicates."""
        pred = svc.predict_dropout("P010")
        assert pred is not None
        assert len(pred.recommended_interventions) == len(set(pred.recommended_interventions))

    def test_dropped_patient_prediction(self, svc: PatientRetentionService):
        """Dropped-out patient should have very high risk prediction."""
        pred = svc.predict_dropout("P011")
        assert pred is not None
        assert pred.risk_level == RetentionRiskLevel.VERY_HIGH
        assert pred.risk_score >= 90.0

    def test_completed_patient_prediction(self, svc: PatientRetentionService):
        """Completed patient should have minimal risk prediction."""
        pred = svc.predict_dropout("P009")
        assert pred is not None
        assert pred.risk_level == RetentionRiskLevel.MINIMAL


# ===========================================================================
# Section 5: Kaplan-Meier retention curves (12 tests)
# ===========================================================================


class TestRetentionCurve:
    """Test Kaplan-Meier survival curve generation."""

    def test_generate_curve_eylea(self, svc: PatientRetentionService):
        """Should generate retention curve for EYLEA trial."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        assert curve.trial_id == EYLEA_TRIAL_ID

    def test_generate_curve_dupixent(self, svc: PatientRetentionService):
        """Should generate retention curve for Dupixent trial."""
        curve = svc.generate_retention_curve(DUPIXENT_TRIAL_ID)
        assert curve is not None
        assert curve.trial_id == DUPIXENT_TRIAL_ID

    def test_generate_curve_libtayo(self, svc: PatientRetentionService):
        """Should generate retention curve for Libtayo trial."""
        curve = svc.generate_retention_curve(LIBTAYO_TRIAL_ID)
        assert curve is not None
        assert curve.trial_id == LIBTAYO_TRIAL_ID

    def test_curve_nonexistent_trial(self, svc: PatientRetentionService):
        """Should return None for nonexistent trial."""
        assert svc.generate_retention_curve("nonexistent") is None

    def test_curve_starts_at_one(self, svc: PatientRetentionService):
        """Survival curve should start at probability 1.0."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        assert len(curve.data_points) > 0
        assert curve.data_points[0].survival_probability == 1.0

    def test_curve_decreases_monotonically(self, svc: PatientRetentionService):
        """Survival probabilities should decrease monotonically."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        probs = [pt.survival_probability for pt in curve.data_points]
        for i in range(1, len(probs)):
            assert probs[i] <= probs[i - 1]

    def test_curve_has_data_points(self, svc: PatientRetentionService):
        """Curve should have multiple data points."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        assert len(curve.data_points) >= 2

    def test_curve_km_estimate_bounded(self, svc: PatientRetentionService):
        """Kaplan-Meier estimate should be between 0 and 1."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        assert 0 <= curve.kaplan_meier_estimate <= 1.0

    def test_curve_retention_at_30d(self, svc: PatientRetentionService):
        """Retention at 30 days should be calculable."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        assert curve.retention_at_30d is not None
        assert 0 <= curve.retention_at_30d <= 1.0

    def test_curve_retention_at_90d(self, svc: PatientRetentionService):
        """Retention at 90 days should be calculable."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        assert curve.retention_at_90d is not None
        assert 0 <= curve.retention_at_90d <= 1.0

    def test_curve_point_fields(self, svc: PatientRetentionService):
        """Each curve point should have all required fields."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        for pt in curve.data_points:
            assert pt.day >= 0
            assert pt.patients_at_risk >= 0
            assert pt.events >= 0
            assert pt.censored >= 0
            assert 0 <= pt.survival_probability <= 1.0

    def test_curve_day_zero_no_events(self, svc: PatientRetentionService):
        """Day zero should have no events or censored."""
        curve = svc.generate_retention_curve(EYLEA_TRIAL_ID)
        assert curve is not None
        day0 = curve.data_points[0]
        assert day0.day == 0
        assert day0.events == 0
        assert day0.censored == 0


# ===========================================================================
# Section 6: Intervention management (12 tests)
# ===========================================================================


class TestInterventionManagement:
    """Test intervention CRUD and tracking."""

    def test_list_all_interventions(self, svc: PatientRetentionService):
        """Should list all 25 seeded interventions."""
        interventions = svc.list_interventions()
        assert len(interventions) == 25

    def test_filter_by_patient(self, svc: PatientRetentionService):
        """Should filter interventions by patient ID."""
        interventions = svc.list_interventions(patient_id="P010")
        assert len(interventions) >= 2
        for i in interventions:
            assert i.patient_id == "P010"

    def test_filter_by_type(self, svc: PatientRetentionService):
        """Should filter interventions by type."""
        interventions = svc.list_interventions(intervention_type=InterventionType.PHONE_CALL)
        assert len(interventions) >= 3
        for i in interventions:
            assert i.intervention_type == InterventionType.PHONE_CALL

    def test_get_intervention_by_id(self, svc: PatientRetentionService):
        """Should retrieve an intervention by ID."""
        intv = svc.get_intervention("intv-0001")
        assert intv is not None
        assert intv.id == "intv-0001"

    def test_get_nonexistent_intervention(self, svc: PatientRetentionService):
        """Should return None for nonexistent intervention."""
        assert svc.get_intervention("nonexistent") is None

    def test_create_intervention(self, svc: PatientRetentionService):
        """Should create a new intervention."""
        req = InterventionCreateRequest(
            patient_id="P001",
            intervention_type=InterventionType.GIFT_CARD,
            applied_by="Admin",
            notes="Thank you card with gift card",
            cost=50.0,
        )
        intv = svc.create_intervention(req)
        assert intv.id is not None
        assert intv.patient_id == "P001"
        assert intv.intervention_type == InterventionType.GIFT_CARD
        assert intv.cost == 50.0

    def test_create_intervention_links_to_profile(self, svc: PatientRetentionService):
        """Creating an intervention should link it to the patient's profile."""
        req = InterventionCreateRequest(
            patient_id="P001",
            intervention_type=InterventionType.PHONE_CALL,
            cost=25.0,
        )
        intv = svc.create_intervention(req)
        profile = svc.get_profile_by_patient("P001")
        assert profile is not None
        assert intv.id in profile.interventions_applied

    def test_update_intervention_outcome(self, svc: PatientRetentionService):
        """Should update intervention outcome."""
        req = InterventionUpdateRequest(outcome="Patient rescheduled visit successfully")
        intv = svc.update_intervention("intv-0001", req)
        assert intv is not None
        assert intv.outcome == "Patient rescheduled visit successfully"

    def test_update_intervention_notes(self, svc: PatientRetentionService):
        """Should update intervention notes."""
        req = InterventionUpdateRequest(notes="Updated notes after follow-up")
        intv = svc.update_intervention("intv-0001", req)
        assert intv is not None
        assert intv.notes == "Updated notes after follow-up"

    def test_update_nonexistent_intervention(self, svc: PatientRetentionService):
        """Should return None for nonexistent intervention update."""
        req = InterventionUpdateRequest(outcome="test")
        assert svc.update_intervention("nonexistent", req) is None

    def test_interventions_have_cost(self, svc: PatientRetentionService):
        """All interventions should have non-negative cost."""
        interventions = svc.list_interventions()
        for i in interventions:
            assert i.cost >= 0

    def test_interventions_have_dates(self, svc: PatientRetentionService):
        """All interventions should have applied dates."""
        interventions = svc.list_interventions()
        for i in interventions:
            assert i.applied_date is not None


# ===========================================================================
# Section 7: Site retention comparison (8 tests)
# ===========================================================================


class TestSiteComparison:
    """Test site-level retention comparisons."""

    def test_site_comparisons_all_trials(self, svc: PatientRetentionService):
        """Should return comparisons for all sites across all trials."""
        comps = svc.get_site_comparisons()
        assert len(comps) >= 8

    def test_site_comparisons_single_trial(self, svc: PatientRetentionService):
        """Should return comparisons for sites in a single trial."""
        comps = svc.get_site_comparisons(trial_id=EYLEA_TRIAL_ID)
        assert len(comps) == 3  # SITE-101, SITE-102, SITE-105
        site_ids = {c.site_id for c in comps}
        assert site_ids == {"SITE-101", "SITE-102", "SITE-105"}

    def test_site_retention_rate_bounded(self, svc: PatientRetentionService):
        """Site retention rates should be between 0 and 1."""
        comps = svc.get_site_comparisons()
        for c in comps:
            assert 0 <= c.retention_rate <= 1.0

    def test_site_dropout_rate_bounded(self, svc: PatientRetentionService):
        """Site dropout rates should be between 0 and 1."""
        comps = svc.get_site_comparisons()
        for c in comps:
            assert 0 <= c.dropout_rate <= 1.0

    def test_site_rates_sum_to_one(self, svc: PatientRetentionService):
        """Retention + dropout should sum to approximately 1."""
        comps = svc.get_site_comparisons()
        for c in comps:
            assert abs(c.retention_rate + c.dropout_rate - 1.0) < 0.01

    def test_site_avg_days_positive(self, svc: PatientRetentionService):
        """Average days retained should be positive."""
        comps = svc.get_site_comparisons()
        for c in comps:
            assert c.avg_days_retained > 0

    def test_site_sorted_by_retention(self, svc: PatientRetentionService):
        """Sites should be sorted by retention rate descending."""
        comps = svc.get_site_comparisons()
        rates = [c.retention_rate for c in comps]
        assert rates == sorted(rates, reverse=True)

    def test_site_has_name(self, svc: PatientRetentionService):
        """Each site should have a human-readable name."""
        comps = svc.get_site_comparisons()
        for c in comps:
            assert len(c.site_name) > 0


# ===========================================================================
# Section 8: Retention metrics (10 tests)
# ===========================================================================


class TestRetentionMetrics:
    """Test aggregate retention metrics."""

    def test_overall_metrics(self, svc: PatientRetentionService):
        """Should compute overall retention metrics."""
        metrics = svc.get_retention_metrics()
        assert metrics.total_patients == 40

    def test_metrics_dropout_count(self, svc: PatientRetentionService):
        """Should correctly count dropped-out patients."""
        metrics = svc.get_retention_metrics()
        assert metrics.dropped_out_patients == 5

    def test_metrics_retention_rate(self, svc: PatientRetentionService):
        """Should compute correct retention rate."""
        metrics = svc.get_retention_metrics()
        expected_rate = (40 - 5) / 40
        assert abs(metrics.overall_retention_rate - expected_rate) < 0.01

    def test_metrics_dropout_rate(self, svc: PatientRetentionService):
        """Should compute correct dropout rate."""
        metrics = svc.get_retention_metrics()
        assert abs(metrics.overall_dropout_rate - 5 / 40) < 0.01

    def test_metrics_by_trial(self, svc: PatientRetentionService):
        """Should compute metrics filtered by trial."""
        metrics = svc.get_retention_metrics(trial_id=EYLEA_TRIAL_ID)
        assert metrics.total_patients == 15
        assert metrics.dropped_out_patients == 2

    def test_metrics_avg_risk_bounded(self, svc: PatientRetentionService):
        """Average risk score should be between 0 and 100."""
        metrics = svc.get_retention_metrics()
        assert 0 <= metrics.avg_risk_score <= 100

    def test_metrics_high_risk_count(self, svc: PatientRetentionService):
        """Should count high-risk patients."""
        metrics = svc.get_retention_metrics()
        assert metrics.high_risk_count >= 5  # At least dropouts

    def test_metrics_total_interventions(self, svc: PatientRetentionService):
        """Should count total interventions."""
        metrics = svc.get_retention_metrics()
        assert metrics.total_interventions == 25

    def test_metrics_cost_per_retained(self, svc: PatientRetentionService):
        """Cost per retained patient should be positive."""
        metrics = svc.get_retention_metrics()
        assert metrics.cost_per_retained_patient > 0

    def test_metrics_avg_days_positive(self, svc: PatientRetentionService):
        """Average days retained should be positive."""
        metrics = svc.get_retention_metrics()
        assert metrics.avg_days_retained > 0


# ===========================================================================
# Section 9: Retention dashboard (8 tests)
# ===========================================================================


class TestRetentionDashboard:
    """Test comprehensive retention dashboard."""

    def test_dashboard_has_metrics(self, svc: PatientRetentionService):
        """Dashboard should include retention metrics."""
        dashboard = svc.get_dashboard()
        assert dashboard.metrics is not None
        assert dashboard.metrics.total_patients == 40

    def test_dashboard_risk_distribution(self, svc: PatientRetentionService):
        """Dashboard should include risk distribution."""
        dashboard = svc.get_dashboard()
        total = sum(dashboard.risk_distribution.values())
        assert total == 40

    def test_dashboard_phase_distribution(self, svc: PatientRetentionService):
        """Dashboard should include phase distribution."""
        dashboard = svc.get_dashboard()
        total = sum(dashboard.phase_distribution.values())
        assert total == 40

    def test_dashboard_dropout_reasons(self, svc: PatientRetentionService):
        """Dashboard should include dropout reason breakdown."""
        dashboard = svc.get_dashboard()
        total_reasons = sum(dashboard.dropout_reasons.values())
        assert total_reasons == 5

    def test_dashboard_site_comparisons(self, svc: PatientRetentionService):
        """Dashboard should include site comparisons."""
        dashboard = svc.get_dashboard()
        assert len(dashboard.site_comparisons) >= 8

    def test_dashboard_top_risk_patients(self, svc: PatientRetentionService):
        """Dashboard should include top at-risk patients."""
        dashboard = svc.get_dashboard()
        assert len(dashboard.top_risk_patients) > 0
        # Should exclude completed and dropped-out patients
        for p in dashboard.top_risk_patients:
            assert not p.dropped_out
            assert p.phase != PatientPhase.COMPLETED

    def test_dashboard_intervention_effectiveness(self, svc: PatientRetentionService):
        """Dashboard should include intervention effectiveness."""
        dashboard = svc.get_dashboard()
        assert len(dashboard.intervention_effectiveness) > 0

    def test_dashboard_retention_curves(self, svc: PatientRetentionService):
        """Dashboard should include retention curves for all trials."""
        dashboard = svc.get_dashboard()
        assert len(dashboard.retention_curves) == 3


# ===========================================================================
# Section 10: Cohort analysis (10 tests)
# ===========================================================================


class TestCohortAnalysis:
    """Test cohort analysis by various dimensions."""

    def test_cohort_by_trial(self, svc: PatientRetentionService):
        """Should produce cohort analysis by trial."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_TRIAL)
        assert len(cohorts) == 3
        names = {c.cohort_name for c in cohorts}
        assert "EYLEA HD" in names
        assert "Dupixent" in names
        assert "Libtayo" in names

    def test_cohort_by_site(self, svc: PatientRetentionService):
        """Should produce cohort analysis by site."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_SITE)
        assert len(cohorts) >= 8

    def test_cohort_by_phase(self, svc: PatientRetentionService):
        """Should produce cohort analysis by phase."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_PHASE)
        assert len(cohorts) >= 4

    def test_cohort_by_demographics(self, svc: PatientRetentionService):
        """Should produce cohort analysis by demographics."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_DEMOGRAPHICS)
        assert len(cohorts) >= 2

    def test_cohort_overall(self, svc: PatientRetentionService):
        """Should produce overall cohort analysis."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.OVERALL)
        assert len(cohorts) == 1
        assert cohorts[0].cohort_name == "All Patients"
        assert cohorts[0].cohort_size == 40

    def test_cohort_sizes_sum(self, svc: PatientRetentionService):
        """Cohort sizes should sum to total patients."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_TRIAL)
        total = sum(c.cohort_size for c in cohorts)
        assert total == 40

    def test_cohort_rates_bounded(self, svc: PatientRetentionService):
        """Cohort retention rates should be between 0 and 1."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_TRIAL)
        for c in cohorts:
            assert 0 <= c.retention_rate <= 1.0
            assert 0 <= c.dropout_rate <= 1.0

    def test_cohort_sorted_by_retention(self, svc: PatientRetentionService):
        """Cohorts should be sorted by retention rate descending."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_TRIAL)
        rates = [c.retention_rate for c in cohorts]
        assert rates == sorted(rates, reverse=True)

    def test_cohort_with_trial_filter(self, svc: PatientRetentionService):
        """Should accept trial filter with cohort analysis."""
        cohorts = svc.get_cohort_analysis(
            group_by=RetentionMetricType.BY_SITE,
            trial_id=EYLEA_TRIAL_ID,
        )
        assert len(cohorts) == 3  # 3 sites for EYLEA

    def test_cohort_avg_risk_bounded(self, svc: PatientRetentionService):
        """Cohort average risk score should be between 0 and 100."""
        cohorts = svc.get_cohort_analysis(group_by=RetentionMetricType.BY_TRIAL)
        for c in cohorts:
            assert 0 <= c.avg_risk_score <= 100


# ===========================================================================
# Section 11: Intervention effectiveness (8 tests)
# ===========================================================================


class TestInterventionEffectiveness:
    """Test intervention effectiveness analysis."""

    def test_effectiveness_list(self, svc: PatientRetentionService):
        """Should return effectiveness for multiple intervention types."""
        eff = svc.get_intervention_effectiveness()
        assert len(eff) > 0

    def test_effectiveness_has_phone_calls(self, svc: PatientRetentionService):
        """Should include phone call effectiveness."""
        eff = svc.get_intervention_effectiveness()
        types = {e.intervention_type for e in eff}
        assert InterventionType.PHONE_CALL in types

    def test_effectiveness_total_applied(self, svc: PatientRetentionService):
        """Total applied should be positive."""
        eff = svc.get_intervention_effectiveness()
        for e in eff:
            assert e.total_applied > 0

    def test_effectiveness_success_rate_bounded(self, svc: PatientRetentionService):
        """Success rate should be between 0 and 1."""
        eff = svc.get_intervention_effectiveness()
        for e in eff:
            assert 0 <= e.success_rate <= 1.0

    def test_effectiveness_cost_positive(self, svc: PatientRetentionService):
        """Intervention costs should be non-negative."""
        eff = svc.get_intervention_effectiveness()
        for e in eff:
            assert e.avg_cost >= 0
            assert e.total_cost >= 0

    def test_effectiveness_sorted_by_success(self, svc: PatientRetentionService):
        """Should be sorted by success rate descending."""
        eff = svc.get_intervention_effectiveness()
        rates = [e.success_rate for e in eff]
        assert rates == sorted(rates, reverse=True)

    def test_effectiveness_with_trial_filter(self, svc: PatientRetentionService):
        """Should accept trial filter."""
        eff = svc.get_intervention_effectiveness(trial_id=EYLEA_TRIAL_ID)
        assert len(eff) > 0

    def test_effectiveness_retained_vs_dropped(self, svc: PatientRetentionService):
        """Should track retained vs dropped after intervention."""
        eff = svc.get_intervention_effectiveness()
        for e in eff:
            assert e.retained_after + e.dropped_after == e.total_applied


# ===========================================================================
# Section 12: Cost per retained (5 tests)
# ===========================================================================


class TestCostPerRetained:
    """Test cost-per-retained-patient calculations."""

    def test_cost_metrics_overall(self, svc: PatientRetentionService):
        """Should compute cost metrics for all patients."""
        result = svc.get_cost_per_retained()
        assert result["total_patients"] == 40
        assert result["retained_patients"] == 35
        assert result["dropped_patients"] == 5

    def test_cost_per_retained_positive(self, svc: PatientRetentionService):
        """Cost per retained patient should be positive."""
        result = svc.get_cost_per_retained()
        assert result["cost_per_retained_patient"] > 0

    def test_cost_by_type(self, svc: PatientRetentionService):
        """Should break down cost by intervention type."""
        result = svc.get_cost_per_retained()
        assert len(result["cost_by_intervention_type"]) > 0

    def test_cost_with_trial_filter(self, svc: PatientRetentionService):
        """Should compute cost for a specific trial."""
        result = svc.get_cost_per_retained(trial_id=EYLEA_TRIAL_ID)
        assert result["total_patients"] == 15

    def test_interventions_per_patient(self, svc: PatientRetentionService):
        """Interventions per patient should be calculable."""
        result = svc.get_cost_per_retained()
        assert result["interventions_per_patient"] > 0


# ===========================================================================
# Section 13: Batch risk recalculation (3 tests)
# ===========================================================================


class TestBatchRecalculation:
    """Test batch risk recalculation."""

    def test_recalculate_all(self, svc: PatientRetentionService):
        """Should recalculate risks for all profiles."""
        result = svc.recalculate_all_risks()
        assert result["profiles_updated"] == 40

    def test_recalculate_returns_distribution(self, svc: PatientRetentionService):
        """Should return risk distribution after recalculation."""
        result = svc.recalculate_all_risks()
        assert "risk_distribution" in result
        total = sum(result["risk_distribution"].values())
        assert total == 40

    def test_recalculate_idempotent(self, svc: PatientRetentionService):
        """Recalculation should be idempotent with same data."""
        result1 = svc.recalculate_all_risks()
        result2 = svc.recalculate_all_risks()
        assert result1["risk_distribution"] == result2["risk_distribution"]


# ===========================================================================
# Section 14: API integration tests (19 tests for 19 endpoints)
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Test all API endpoints via HTTP client."""

    async def _client(self):
        """Create async HTTP client."""
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    async def test_api_list_profiles(self):
        """GET /profiles should return all profiles."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 40
        assert len(data["items"]) == 40

    async def test_api_list_profiles_filter_trial(self):
        """GET /profiles?trial_id= should filter by trial."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/profiles", params={"trial_id": EYLEA_TRIAL_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    async def test_api_list_profiles_filter_phase(self):
        """GET /profiles?phase= should filter by phase."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/profiles", params={"phase": "DROPPED_OUT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    async def test_api_create_profile(self):
        """POST /profiles should create a new profile."""
        async with await self._client() as client:
            resp = await client.post(f"{API_PREFIX}/profiles", json={
                "patient_id": "API-001",
                "trial_id": EYLEA_TRIAL_ID,
                "site_id": "SITE-101",
                "enrolled_date": str(date.today()),
                "visits_scheduled": 10,
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "API-001"

    async def test_api_get_profile(self):
        """GET /profiles/{profile_id} should return a profile."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/profiles/ret-0001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ret-0001"

    async def test_api_get_profile_not_found(self):
        """GET /profiles/{profile_id} should return 404 for nonexistent."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/profiles/nonexistent")
        assert resp.status_code == 404

    async def test_api_update_profile(self):
        """PUT /profiles/{profile_id} should update a profile."""
        async with await self._client() as client:
            resp = await client.put(f"{API_PREFIX}/profiles/ret-0001", json={
                "missed_visits": 2,
            })
        assert resp.status_code == 200
        assert resp.json()["missed_visits"] == 2

    async def test_api_delete_profile(self):
        """DELETE /profiles/{profile_id} should delete a profile."""
        async with await self._client() as client:
            resp = await client.delete(f"{API_PREFIX}/profiles/ret-0001")
        assert resp.status_code == 204

    async def test_api_delete_profile_not_found(self):
        """DELETE /profiles/{profile_id} should return 404 for nonexistent."""
        async with await self._client() as client:
            resp = await client.delete(f"{API_PREFIX}/profiles/nonexistent")
        assert resp.status_code == 404

    async def test_api_get_profile_by_patient(self):
        """GET /profiles/patient/{patient_id} should return profile."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/profiles/patient/P001")
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == "P001"

    async def test_api_get_profile_by_patient_not_found(self):
        """GET /profiles/patient/{patient_id} should return 404."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/profiles/patient/NONEXISTENT")
        assert resp.status_code == 404

    async def test_api_predict_dropout(self):
        """GET /predictions/{patient_id} should return prediction."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/predictions/P001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "P001"
        assert "risk_score" in data
        assert "recommended_interventions" in data

    async def test_api_predict_dropout_not_found(self):
        """GET /predictions/{patient_id} should return 404."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/predictions/NONEXISTENT")
        assert resp.status_code == 404

    async def test_api_retention_curve(self):
        """GET /curves/{trial_id} should return retention curve."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/curves/{EYLEA_TRIAL_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL_ID
        assert len(data["data_points"]) > 0

    async def test_api_retention_curve_not_found(self):
        """GET /curves/{trial_id} should return 404."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/curves/nonexistent")
        assert resp.status_code == 404

    async def test_api_list_interventions(self):
        """GET /interventions should return all interventions."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/interventions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25

    async def test_api_create_intervention(self):
        """POST /interventions should create an intervention."""
        async with await self._client() as client:
            resp = await client.post(f"{API_PREFIX}/interventions", json={
                "patient_id": "P001",
                "intervention_type": "GIFT_CARD",
                "cost": 50.0,
            })
        assert resp.status_code == 201
        assert resp.json()["intervention_type"] == "GIFT_CARD"

    async def test_api_get_intervention(self):
        """GET /interventions/{id} should return an intervention."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/interventions/intv-0001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "intv-0001"

    async def test_api_get_intervention_not_found(self):
        """GET /interventions/{id} should return 404."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/interventions/nonexistent")
        assert resp.status_code == 404

    async def test_api_update_intervention(self):
        """PUT /interventions/{id} should update an intervention."""
        async with await self._client() as client:
            resp = await client.put(f"{API_PREFIX}/interventions/intv-0001", json={
                "outcome": "Successfully retained patient",
            })
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "Successfully retained patient"

    async def test_api_update_intervention_not_found(self):
        """PUT /interventions/{id} should return 404."""
        async with await self._client() as client:
            resp = await client.put(f"{API_PREFIX}/interventions/nonexistent", json={
                "outcome": "test",
            })
        assert resp.status_code == 404

    async def test_api_site_comparisons(self):
        """GET /sites should return site comparisons."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/sites")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 8

    async def test_api_site_comparisons_by_trial(self):
        """GET /sites?trial_id= should filter site comparisons."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/sites", params={"trial_id": EYLEA_TRIAL_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    async def test_api_metrics(self):
        """GET /metrics should return aggregate metrics."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 40
        assert data["dropped_out_patients"] == 5

    async def test_api_dashboard(self):
        """GET /dashboard should return comprehensive dashboard."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert "risk_distribution" in data
        assert "retention_curves" in data
        assert len(data["retention_curves"]) == 3

    async def test_api_cohorts(self):
        """GET /cohorts should return cohort analysis."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/cohorts", params={"group_by": "BY_TRIAL"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    async def test_api_effectiveness(self):
        """GET /effectiveness should return intervention effectiveness."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/effectiveness")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    async def test_api_cost_per_retained(self):
        """GET /cost-per-retained should return cost metrics."""
        async with await self._client() as client:
            resp = await client.get(f"{API_PREFIX}/cost-per-retained")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 40
        assert data["cost_per_retained_patient"] > 0

    async def test_api_recalculate_risks(self):
        """POST /recalculate-risks should recalculate all risks."""
        async with await self._client() as client:
            resp = await client.post(f"{API_PREFIX}/recalculate-risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profiles_updated"] == 40


# ===========================================================================
# Section 15: Additional edge cases and validations (5 tests)
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_trial_filter(self, svc: PatientRetentionService):
        """Should return empty list for trial with no patients."""
        profiles = svc.list_profiles(trial_id="nonexistent-trial")
        assert len(profiles) == 0

    def test_create_multiple_interventions_for_patient(self, svc: PatientRetentionService):
        """Should allow multiple interventions for the same patient."""
        for i in range(3):
            req = InterventionCreateRequest(
                patient_id="P001",
                intervention_type=InterventionType.PHONE_CALL,
                cost=25.0,
            )
            svc.create_intervention(req)
        interventions = svc.list_interventions(patient_id="P001")
        # P001 had existing interventions from seed + 3 new ones
        assert len(interventions) >= 3

    def test_cohort_empty_trial(self, svc: PatientRetentionService):
        """Cohort analysis should return empty for trial with no patients."""
        cohorts = svc.get_cohort_analysis(
            group_by=RetentionMetricType.BY_SITE,
            trial_id="nonexistent-trial",
        )
        assert len(cohorts) == 0

    def test_site_comparison_empty(self, svc: PatientRetentionService):
        """Site comparison should return empty for nonexistent trial."""
        comps = svc.get_site_comparisons(trial_id="nonexistent-trial")
        assert len(comps) == 0

    def test_singleton_service(self):
        """Service should be a singleton."""
        svc1 = get_patient_retention_service()
        svc2 = get_patient_retention_service()
        assert svc1 is svc2
