"""Tests for Feature Store Service.

Tests cover:
- Feature definition CRUD: list, get, register, update
- Built-in feature population (25+ pre-defined features)
- Feature computation: single patient, specific features, missing data
- Batch computation: multiple patients, error handling
- Feature statistics: numeric, categorical, boolean, null rates
- Feature importance: ranking, scoring, usage counts
- Feature versioning: change tracking, version history
- Service singleton: get/reset pattern
- API endpoints: all routes via ASGI test client
- Edge cases: duplicate names, not found, empty inputs
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.feature_store import (
    FeatureDataType,
    FeatureDomain,
    MissingReason,
    TrendDirection,
)
from app.services.feature_store_service import (
    FeatureStoreService,
    get_feature_store_service,
    reset_feature_store_service,
    _compute_patient_age,
    _compute_has_diabetes_type2,
    _compute_latest_hba1c,
    _compute_bmi,
    _compute_active_medication_count,
    _compute_condition_count,
    _compute_latest_egfr,
    _compute_comorbidity_score,
    _compute_insurance_type,
    _compute_engagement_score,
    _compute_smoking_status,
    _compute_gender,
    _compute_ethnicity,
    _compute_distance_to_nearest_site,
    _compute_screening_history_count,
    _compute_lab_value_trend_hba1c,
    _compute_has_prior_treatment_chemo,
    _compute_has_prior_treatment_radiation,
    _compute_has_prior_treatment_surgery,
    _compute_has_prior_treatment_immunotherapy,
    _compute_days_since_diagnosis_diabetes,
    _compute_days_since_diagnosis_hypertension,
    _compute_days_since_diagnosis_cancer,
    _patient_rng,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_feature_store_service()
    yield
    reset_feature_store_service()


@pytest.fixture
def service() -> FeatureStoreService:
    return get_feature_store_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Built-in Features Tests
# ============================================================================


class TestBuiltinFeatures:
    """Tests for pre-defined built-in features."""

    def test_builtin_features_count(self, service: FeatureStoreService):
        """Service should have at least 25 built-in features."""
        features = service.list_features()
        assert len(features) >= 25, f"Expected 25+ features, got {len(features)}"

    def test_builtin_features_are_marked_builtin(self, service: FeatureStoreService):
        """All initial features should be marked as built-in."""
        features = service.list_features()
        for f in features:
            assert f.is_builtin is True, f"Feature {f.name} should be built-in"

    def test_builtin_feature_names(self, service: FeatureStoreService):
        """Verify key built-in feature names exist."""
        features = service.list_features()
        names = {f.name for f in features}
        expected_names = {
            "patient_age",
            "has_diabetes_type2",
            "latest_hba1c",
            "bmi",
            "active_medication_count",
            "condition_count",
            "latest_egfr",
            "comorbidity_score",
            "insurance_type",
            "distance_to_nearest_site",
            "engagement_score",
            "screening_history_count",
        }
        for en in expected_names:
            assert en in names, f"Missing built-in feature: {en}"

    def test_builtin_features_have_domains(self, service: FeatureStoreService):
        """All built-in features should have a valid domain."""
        features = service.list_features()
        for f in features:
            assert f.domain is not None
            assert isinstance(f.domain, FeatureDomain)

    def test_builtin_features_have_data_types(self, service: FeatureStoreService):
        """All built-in features should have a valid data type."""
        features = service.list_features()
        for f in features:
            assert f.data_type is not None
            assert isinstance(f.data_type, FeatureDataType)

    def test_patient_age_is_numeric_demographic(self, service: FeatureStoreService):
        """patient_age should be NUMERIC in DEMOGRAPHIC domain."""
        feat = service.get_feature("patient_age")
        assert feat is not None
        assert feat.data_type == FeatureDataType.NUMERIC
        assert feat.domain == FeatureDomain.DEMOGRAPHIC

    def test_has_diabetes_type2_is_boolean_condition(self, service: FeatureStoreService):
        """has_diabetes_type2 should be BOOLEAN in CONDITION domain."""
        feat = service.get_feature("has_diabetes_type2")
        assert feat is not None
        assert feat.data_type == FeatureDataType.BOOLEAN
        assert feat.domain == FeatureDomain.CONDITION

    def test_insurance_type_is_categorical(self, service: FeatureStoreService):
        """insurance_type should be CATEGORICAL."""
        feat = service.get_feature("insurance_type")
        assert feat is not None
        assert feat.data_type == FeatureDataType.CATEGORICAL


# ============================================================================
# Feature Definition CRUD Tests
# ============================================================================


class TestFeatureCRUD:
    """Tests for feature definition create, read, update operations."""

    def test_list_features_returns_all(self, service: FeatureStoreService):
        """list_features without filters returns all features."""
        features = service.list_features()
        assert len(features) >= 25

    def test_list_features_filter_by_domain(self, service: FeatureStoreService):
        """Filtering by domain returns only matching features."""
        lab_features = service.list_features(domain=FeatureDomain.LAB)
        for f in lab_features:
            assert f.domain == FeatureDomain.LAB

    def test_list_features_filter_by_data_type(self, service: FeatureStoreService):
        """Filtering by data_type returns only matching features."""
        bool_features = service.list_features(data_type=FeatureDataType.BOOLEAN)
        for f in bool_features:
            assert f.data_type == FeatureDataType.BOOLEAN

    def test_list_features_filter_by_tag(self, service: FeatureStoreService):
        """Filtering by tag returns only features with that tag."""
        screening_features = service.list_features(tag="screening")
        for f in screening_features:
            assert "screening" in f.tags

    def test_get_feature_exists(self, service: FeatureStoreService):
        """Getting an existing feature returns its definition."""
        feat = service.get_feature("patient_age")
        assert feat is not None
        assert feat.name == "patient_age"
        assert feat.version == 1

    def test_get_feature_not_found(self, service: FeatureStoreService):
        """Getting a non-existent feature returns None."""
        feat = service.get_feature("nonexistent_feature")
        assert feat is None

    def test_register_custom_feature(self, service: FeatureStoreService):
        """Registering a custom feature adds it to the store."""
        result = service.register_feature(
            name="custom_risk_score",
            description="Custom risk score for screening",
            data_type=FeatureDataType.NUMERIC,
            domain=FeatureDomain.SCREENING,
            computation_logic="Custom ML model output",
            tags=["custom", "risk"],
        )
        assert result.name == "custom_risk_score"
        assert result.is_builtin is False
        assert result.version == 1

    def test_register_duplicate_feature_raises(self, service: FeatureStoreService):
        """Registering a feature with existing name raises ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            service.register_feature(
                name="patient_age",
                description="Duplicate",
                data_type=FeatureDataType.NUMERIC,
                domain=FeatureDomain.DEMOGRAPHIC,
            )

    def test_update_feature_description(self, service: FeatureStoreService):
        """Updating a feature description bumps the version."""
        result = service.update_feature("patient_age", description="Updated description")
        assert result is not None
        assert result.description == "Updated description"
        assert result.version == 2

    def test_update_feature_not_found(self, service: FeatureStoreService):
        """Updating a non-existent feature returns None."""
        result = service.update_feature("nonexistent", description="test")
        assert result is None

    def test_update_feature_no_changes(self, service: FeatureStoreService):
        """Updating with same values does not bump version."""
        feat = service.get_feature("patient_age")
        result = service.update_feature("patient_age", description=feat.description)
        assert result.version == 1  # no change

    def test_update_multiple_fields(self, service: FeatureStoreService):
        """Updating multiple fields creates a single version bump."""
        result = service.update_feature(
            "patient_age",
            description="New desc",
            tags=["updated", "demographic"],
        )
        assert result is not None
        assert result.version == 2
        assert result.description == "New desc"
        assert "updated" in result.tags


# ============================================================================
# Feature Versioning Tests
# ============================================================================


class TestFeatureVersioning:
    """Tests for feature version tracking."""

    def test_initial_version_is_one(self, service: FeatureStoreService):
        """Built-in features start at version 1."""
        feat = service.get_feature("patient_age")
        assert feat.version == 1

    def test_version_history_initial(self, service: FeatureStoreService):
        """Initial version history has one entry."""
        history = service.get_feature_versions("patient_age")
        assert history is not None
        assert history.current_version == 1
        assert len(history.versions) == 1

    def test_version_history_after_update(self, service: FeatureStoreService):
        """Updating a feature adds a version entry."""
        service.update_feature("patient_age", description="Version 2")
        service.update_feature("patient_age", tags=["v3"])
        history = service.get_feature_versions("patient_age")
        assert history.current_version == 3
        assert len(history.versions) == 3

    def test_version_history_not_found(self, service: FeatureStoreService):
        """Version history for non-existent feature returns None."""
        history = service.get_feature_versions("nonexistent")
        assert history is None

    def test_version_changes_tracked(self, service: FeatureStoreService):
        """Version changes record old and new values."""
        service.update_feature("patient_age", description="Changed desc")
        history = service.get_feature_versions("patient_age")
        latest = history.versions[0]  # newest first
        assert "description" in latest.changes
        assert latest.changes["description"]["new"] == "Changed desc"


# ============================================================================
# Feature Computation Tests
# ============================================================================


class TestFeatureComputation:
    """Tests for computing feature values for patients."""

    def test_compute_all_features(self, service: FeatureStoreService):
        """Computing all features for a patient returns a complete vector."""
        result = service.compute_features("test_patient_1")
        assert result.patient_id == "test_patient_1"
        assert result.computed_count + result.missing_count == len(result.feature_details)
        assert result.total_computation_time_ms >= 0

    def test_compute_specific_features(self, service: FeatureStoreService):
        """Computing specific features only computes those."""
        result = service.compute_features(
            "test_patient_1",
            feature_names=["patient_age", "bmi"],
        )
        assert len(result.feature_details) == 2
        names = {d.feature_name for d in result.feature_details}
        assert names == {"patient_age", "bmi"}

    def test_compute_patient_age_is_integer(self, service: FeatureStoreService):
        """patient_age should be an integer between 18 and 90."""
        result = service.compute_features("pt_123", feature_names=["patient_age"])
        age = result.features["patient_age"]
        assert isinstance(age, int)
        assert 18 <= age <= 90

    def test_compute_has_diabetes_is_boolean(self, service: FeatureStoreService):
        """has_diabetes_type2 should be a boolean."""
        result = service.compute_features("pt_456", feature_names=["has_diabetes_type2"])
        val = result.features["has_diabetes_type2"]
        assert isinstance(val, bool)

    def test_compute_deterministic(self, service: FeatureStoreService):
        """Same patient ID should produce same results (deterministic)."""
        r1 = service.compute_features("deterministic_patient")
        r2 = service.compute_features("deterministic_patient")
        assert r1.features == r2.features

    def test_compute_different_patients_different_values(self, service: FeatureStoreService):
        """Different patients should generally have different feature values."""
        r1 = service.compute_features("patient_A")
        r2 = service.compute_features("patient_B")
        # At least some features should differ
        differences = sum(
            1 for k in r1.features if r1.features.get(k) != r2.features.get(k)
        )
        assert differences > 0, "Different patients should have different features"

    def test_compute_missing_features_tracked(self, service: FeatureStoreService):
        """Missing features should have is_missing=True with a reason."""
        result = service.compute_features("test_missing_data")
        missing_details = [d for d in result.feature_details if d.is_missing]
        # Some features should be missing for various patients
        for md in missing_details:
            assert md.missing_reason is not None
            assert md.value is None

    def test_compute_unknown_feature_ignored(self, service: FeatureStoreService):
        """Requesting unknown feature names should be silently ignored."""
        result = service.compute_features(
            "pt_1", feature_names=["patient_age", "nonexistent_feature"]
        )
        names = {d.feature_name for d in result.feature_details}
        assert "patient_age" in names
        assert "nonexistent_feature" not in names

    def test_feature_details_have_computation_time(self, service: FeatureStoreService):
        """Each computed feature should track computation time."""
        result = service.compute_features("pt_time", feature_names=["patient_age"])
        for detail in result.feature_details:
            assert detail.computation_time_ms >= 0

    def test_compute_custom_feature_returns_no_data(self, service: FeatureStoreService):
        """Custom features without compute functions return NO_DATA."""
        service.register_feature(
            name="custom_uncomputed",
            description="No compute fn",
            data_type=FeatureDataType.NUMERIC,
            domain=FeatureDomain.SCREENING,
        )
        result = service.compute_features("pt_1", feature_names=["custom_uncomputed"])
        detail = result.feature_details[0]
        assert detail.is_missing is True
        assert detail.missing_reason == MissingReason.NO_DATA


# ============================================================================
# Individual Computation Function Tests
# ============================================================================


class TestComputeFunctions:
    """Tests for individual feature computation functions."""

    def test_patient_age_range(self):
        val, reason = _compute_patient_age("test_pt")
        assert isinstance(val, int)
        assert 18 <= val <= 90
        assert reason is None

    def test_has_diabetes_type2_bool(self):
        val, reason = _compute_has_diabetes_type2("test_pt")
        assert isinstance(val, bool)
        assert reason is None

    def test_latest_hba1c_numeric_or_none(self):
        val, reason = _compute_latest_hba1c("has_hba1c_pt")
        if val is not None:
            assert 4.0 <= val <= 14.0
            assert reason is None
        else:
            assert reason == MissingReason.NO_DATA

    def test_bmi_range(self):
        val, reason = _compute_bmi("bmi_pt")
        if val is not None:
            assert 16.0 <= val <= 45.0
            assert reason is None

    def test_active_medication_count(self):
        val, reason = _compute_active_medication_count("med_pt")
        assert isinstance(val, int)
        assert 0 <= val <= 15

    def test_condition_count(self):
        val, reason = _compute_condition_count("cond_pt")
        assert isinstance(val, int)
        assert 0 <= val <= 12

    def test_latest_egfr(self):
        val, reason = _compute_latest_egfr("egfr_pt")
        if val is not None:
            assert 15.0 <= val <= 120.0

    def test_comorbidity_score(self):
        val, reason = _compute_comorbidity_score("comorb_pt")
        assert isinstance(val, int)
        assert 0 <= val <= 15

    def test_insurance_type_valid(self):
        val, reason = _compute_insurance_type("ins_pt")
        assert val in ("commercial", "medicare", "medicaid", "self_pay", "tricare", "other")
        assert reason is None

    def test_engagement_score_range(self):
        val, reason = _compute_engagement_score("eng_pt")
        assert 0.0 <= val <= 100.0

    def test_smoking_status_valid(self):
        val, reason = _compute_smoking_status("smoke_pt")
        assert val in ("never", "former", "current", "unknown")

    def test_gender_valid(self):
        val, reason = _compute_gender("gen_pt")
        assert val in ("male", "female", "other")

    def test_ethnicity_valid(self):
        val, reason = _compute_ethnicity("eth_pt")
        assert val in ("hispanic", "non_hispanic", "unknown")

    def test_distance_to_nearest_site(self):
        val, reason = _compute_distance_to_nearest_site("dist_pt")
        if val is not None:
            assert 0.5 <= val <= 200.0

    def test_screening_history_count(self):
        val, reason = _compute_screening_history_count("screen_pt")
        assert isinstance(val, int)
        assert 0 <= val <= 8

    def test_lab_value_trend_hba1c(self):
        val, reason = _compute_lab_value_trend_hba1c("trend_pt")
        assert val in (
            TrendDirection.INCREASING.value,
            TrendDirection.DECREASING.value,
            TrendDirection.STABLE.value,
            TrendDirection.INSUFFICIENT_DATA.value,
        )

    def test_prior_treatment_chemo(self):
        val, reason = _compute_has_prior_treatment_chemo("chemo_pt")
        assert isinstance(val, bool)

    def test_prior_treatment_radiation(self):
        val, reason = _compute_has_prior_treatment_radiation("rad_pt")
        assert isinstance(val, bool)

    def test_prior_treatment_surgery(self):
        val, reason = _compute_has_prior_treatment_surgery("surg_pt")
        assert isinstance(val, bool)

    def test_prior_treatment_immunotherapy(self):
        val, reason = _compute_has_prior_treatment_immunotherapy("immuno_pt")
        assert isinstance(val, bool)

    def test_days_since_diagnosis_diabetes_or_na(self):
        val, reason = _compute_days_since_diagnosis_diabetes("diab_pt")
        if val is not None:
            assert 30 <= val <= 10950
            assert reason is None
        else:
            assert reason == MissingReason.NOT_APPLICABLE

    def test_days_since_diagnosis_hypertension_or_na(self):
        val, reason = _compute_days_since_diagnosis_hypertension("htn_pt")
        if val is not None:
            assert 30 <= val <= 14600
        else:
            assert reason == MissingReason.NOT_APPLICABLE

    def test_days_since_diagnosis_cancer_or_na(self):
        val, reason = _compute_days_since_diagnosis_cancer("cancer_pt")
        if val is not None:
            assert 1 <= val <= 3650
        else:
            assert reason == MissingReason.NOT_APPLICABLE

    def test_patient_rng_deterministic(self):
        """Same patient ID should produce same random sequence."""
        rng1 = _patient_rng("same_patient")
        rng2 = _patient_rng("same_patient")
        assert rng1.random() == rng2.random()


# ============================================================================
# Batch Computation Tests
# ============================================================================


class TestBatchComputation:
    """Tests for batch feature computation."""

    def test_batch_compute_multiple_patients(self, service: FeatureStoreService):
        """Batch computation returns results for all patients."""
        result = service.batch_compute(
            patient_ids=["pt_1", "pt_2", "pt_3"],
        )
        assert result.total_patients == 3
        assert len(result.results) == 3
        assert result.total_computation_time_ms >= 0

    def test_batch_compute_with_specific_features(self, service: FeatureStoreService):
        """Batch computation with specific features only computes those."""
        result = service.batch_compute(
            patient_ids=["pt_1", "pt_2"],
            feature_names=["patient_age", "bmi"],
        )
        for r in result.results:
            assert len(r.feature_details) == 2

    def test_batch_compute_single_patient(self, service: FeatureStoreService):
        """Batch computation works with a single patient."""
        result = service.batch_compute(patient_ids=["pt_single"])
        assert result.total_patients == 1
        assert len(result.results) == 1

    def test_batch_compute_errors_dict(self, service: FeatureStoreService):
        """Batch computation tracks errors per patient."""
        result = service.batch_compute(patient_ids=["pt_ok"])
        assert isinstance(result.errors, dict)


# ============================================================================
# Feature Statistics Tests
# ============================================================================


class TestFeatureStatistics:
    """Tests for feature statistics computation."""

    def test_compute_statistics(self, service: FeatureStoreService):
        """Statistics computation returns results for all features."""
        stats = service.compute_statistics(
            sample_patient_ids=[f"stat_pt_{i}" for i in range(50)]
        )
        assert stats.total >= 25
        assert len(stats.statistics) >= 25

    def test_numeric_feature_has_numeric_stats(self, service: FeatureStoreService):
        """Numeric features should have min, max, mean, std, median."""
        stats = service.compute_statistics(
            sample_patient_ids=[f"num_pt_{i}" for i in range(50)]
        )
        age_stat = next(
            (s for s in stats.statistics if s.feature_name == "patient_age"), None
        )
        assert age_stat is not None
        assert age_stat.min_value is not None
        assert age_stat.max_value is not None
        assert age_stat.mean_value is not None
        assert age_stat.std_value is not None
        assert age_stat.median_value is not None
        assert age_stat.min_value <= age_stat.mean_value <= age_stat.max_value

    def test_categorical_feature_has_distribution(self, service: FeatureStoreService):
        """Categorical features should have value distribution."""
        stats = service.compute_statistics(
            sample_patient_ids=[f"cat_pt_{i}" for i in range(50)]
        )
        ins_stat = next(
            (s for s in stats.statistics if s.feature_name == "insurance_type"), None
        )
        assert ins_stat is not None
        assert ins_stat.distribution is not None
        assert ins_stat.unique_count is not None
        assert ins_stat.unique_count > 0

    def test_boolean_feature_has_distribution(self, service: FeatureStoreService):
        """Boolean features should have True/False distribution."""
        stats = service.compute_statistics(
            sample_patient_ids=[f"bool_pt_{i}" for i in range(100)]
        )
        diab_stat = next(
            (s for s in stats.statistics if s.feature_name == "has_diabetes_type2"), None
        )
        assert diab_stat is not None
        assert diab_stat.distribution is not None

    def test_null_rate_between_0_and_1(self, service: FeatureStoreService):
        """Null rates should be between 0 and 1."""
        stats = service.compute_statistics(
            sample_patient_ids=[f"null_pt_{i}" for i in range(50)]
        )
        for s in stats.statistics:
            assert 0.0 <= s.null_rate <= 1.0

    def test_cached_statistics(self, service: FeatureStoreService):
        """After computing, statistics should be cached."""
        assert service.get_cached_statistics() is None
        service.compute_statistics(
            sample_patient_ids=[f"cache_pt_{i}" for i in range(10)]
        )
        cached = service.get_cached_statistics()
        assert cached is not None
        assert cached.total >= 25


# ============================================================================
# Feature Importance Tests
# ============================================================================


class TestFeatureImportance:
    """Tests for feature importance ranking."""

    def test_importance_ranking(self, service: FeatureStoreService):
        """Importance should return all features ranked."""
        imp = service.get_importance()
        assert imp.total >= 25
        assert len(imp.importance) >= 25

    def test_importance_sorted_descending(self, service: FeatureStoreService):
        """Features should be sorted by importance score descending."""
        imp = service.get_importance()
        scores = [i.importance_score for i in imp.importance]
        assert scores == sorted(scores, reverse=True)

    def test_importance_ranks_sequential(self, service: FeatureStoreService):
        """Ranks should be sequential starting from 1."""
        imp = service.get_importance()
        ranks = [i.rank for i in imp.importance]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_importance_scores_in_range(self, service: FeatureStoreService):
        """All importance scores should be between 0 and 1."""
        imp = service.get_importance()
        for i in imp.importance:
            assert 0.0 <= i.importance_score <= 1.0

    def test_set_importance(self, service: FeatureStoreService):
        """Setting importance should update the score."""
        assert service.set_importance("patient_age", 0.5) is True
        imp = service.get_importance()
        age_imp = next(i for i in imp.importance if i.feature_name == "patient_age")
        assert age_imp.importance_score == 0.5

    def test_set_importance_nonexistent(self, service: FeatureStoreService):
        """Setting importance for non-existent feature returns False."""
        assert service.set_importance("nonexistent", 0.5) is False

    def test_set_importance_clamps_value(self, service: FeatureStoreService):
        """Importance score should be clamped to [0, 1]."""
        service.set_importance("patient_age", 1.5)
        imp = service.get_importance()
        age_imp = next(i for i in imp.importance if i.feature_name == "patient_age")
        assert age_imp.importance_score == 1.0

        service.set_importance("patient_age", -0.5)
        imp = service.get_importance()
        age_imp = next(i for i in imp.importance if i.feature_name == "patient_age")
        assert age_imp.importance_score == 0.0

    def test_usage_count_increments(self, service: FeatureStoreService):
        """Computing features should increment usage counts."""
        service.compute_features("usage_pt", feature_names=["patient_age"])
        service.compute_features("usage_pt2", feature_names=["patient_age"])
        imp = service.get_importance()
        age_imp = next(i for i in imp.importance if i.feature_name == "patient_age")
        assert age_imp.usage_count >= 2


# ============================================================================
# Service Singleton Tests
# ============================================================================


class TestServiceSingleton:
    """Tests for the singleton pattern."""

    def test_get_service_returns_same_instance(self):
        """get_feature_store_service should return the same instance."""
        s1 = get_feature_store_service()
        s2 = get_feature_store_service()
        assert s1 is s2

    def test_reset_clears_instance(self):
        """reset_feature_store_service should create a new instance."""
        s1 = get_feature_store_service()
        reset_feature_store_service()
        s2 = get_feature_store_service()
        assert s1 is not s2

    def test_service_stats(self, service: FeatureStoreService):
        """Service stats should report correct counts."""
        stats = service.get_stats()
        assert stats["total_features"] >= 25
        assert stats["builtin_features"] >= 25
        assert stats["custom_features"] == 0
        assert isinstance(stats["domains"], dict)


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for Feature Store API endpoints."""

    @pytest.mark.anyio
    async def test_list_features_endpoint(self, client: AsyncClient):
        """GET /features should return all features."""
        resp = await client.get("/api/v1/feature-store/features")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 25
        assert len(data["features"]) >= 25

    @pytest.mark.anyio
    async def test_list_features_filter_domain(self, client: AsyncClient):
        """GET /features?domain=lab should filter by domain."""
        resp = await client.get(
            "/api/v1/feature-store/features", params={"domain": "lab"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for f in data["features"]:
            assert f["domain"] == "lab"

    @pytest.mark.anyio
    async def test_list_features_filter_data_type(self, client: AsyncClient):
        """GET /features?data_type=boolean should filter by data type."""
        resp = await client.get(
            "/api/v1/feature-store/features", params={"data_type": "boolean"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for f in data["features"]:
            assert f["data_type"] == "boolean"

    @pytest.mark.anyio
    async def test_get_feature_endpoint(self, client: AsyncClient):
        """GET /features/{name} should return feature detail."""
        resp = await client.get("/api/v1/feature-store/features/patient_age")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "patient_age"
        assert data["data_type"] == "numeric"

    @pytest.mark.anyio
    async def test_get_feature_not_found(self, client: AsyncClient):
        """GET /features/{name} should return 404 for unknown feature."""
        resp = await client.get("/api/v1/feature-store/features/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_register_feature_endpoint(self, client: AsyncClient):
        """POST /features should create a new feature."""
        resp = await client.post(
            "/api/v1/feature-store/features",
            json={
                "name": "api_test_feature",
                "description": "Test feature via API",
                "data_type": "numeric",
                "domain": "screening",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "api_test_feature"
        assert data["is_builtin"] is False

    @pytest.mark.anyio
    async def test_register_duplicate_feature_endpoint(self, client: AsyncClient):
        """POST /features with duplicate name should return 409."""
        resp = await client.post(
            "/api/v1/feature-store/features",
            json={
                "name": "patient_age",
                "description": "Duplicate",
                "data_type": "numeric",
                "domain": "demographic",
            },
        )
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_update_feature_endpoint(self, client: AsyncClient):
        """PUT /features/{name} should update feature."""
        resp = await client.put(
            "/api/v1/feature-store/features/patient_age",
            json={"description": "Updated via API"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated via API"
        assert data["version"] == 2

    @pytest.mark.anyio
    async def test_update_feature_not_found_endpoint(self, client: AsyncClient):
        """PUT /features/{name} for unknown feature should return 404."""
        resp = await client.put(
            "/api/v1/feature-store/features/nonexistent",
            json={"description": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_feature_versions_endpoint(self, client: AsyncClient):
        """GET /features/{name}/versions should return version history."""
        resp = await client.get(
            "/api/v1/feature-store/features/patient_age/versions"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["feature_name"] == "patient_age"
        assert data["current_version"] == 1
        assert len(data["versions"]) == 1

    @pytest.mark.anyio
    async def test_compute_features_endpoint(self, client: AsyncClient):
        """POST /features/compute/{patient_id} should compute features."""
        resp = await client.post(
            "/api/v1/feature-store/features/compute/api_test_patient"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "api_test_patient"
        assert data["computed_count"] + data["missing_count"] > 0

    @pytest.mark.anyio
    async def test_compute_features_with_names(self, client: AsyncClient):
        """POST /features/compute/{patient_id}?feature_names=... should filter."""
        resp = await client.post(
            "/api/v1/feature-store/features/compute/api_pt",
            params={"feature_names": ["patient_age", "bmi"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["feature_details"]) == 2

    @pytest.mark.anyio
    async def test_batch_compute_endpoint(self, client: AsyncClient):
        """POST /features/batch-compute should compute for multiple patients."""
        resp = await client.post(
            "/api/v1/feature-store/features/batch-compute",
            json={"patient_ids": ["batch_pt_1", "batch_pt_2", "batch_pt_3"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 3
        assert len(data["results"]) == 3

    @pytest.mark.anyio
    async def test_batch_compute_with_feature_names(self, client: AsyncClient):
        """POST /features/batch-compute with feature_names should filter."""
        resp = await client.post(
            "/api/v1/feature-store/features/batch-compute",
            json={
                "patient_ids": ["batch_pt_1"],
                "feature_names": ["patient_age"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"][0]["feature_details"]) == 1

    @pytest.mark.anyio
    async def test_statistics_endpoint(self, client: AsyncClient):
        """GET /features/statistics should return feature statistics."""
        resp = await client.get(
            "/api/v1/feature-store/features/statistics",
            params={"recompute": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 25
        assert len(data["statistics"]) >= 25

    @pytest.mark.anyio
    async def test_importance_endpoint(self, client: AsyncClient):
        """GET /features/importance should return importance rankings."""
        resp = await client.get("/api/v1/feature-store/features/importance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 25
        assert len(data["importance"]) >= 25
        # Check sorted descending
        scores = [i["importance_score"] for i in data["importance"]]
        assert scores == sorted(scores, reverse=True)
