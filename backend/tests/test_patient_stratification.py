"""Tests for Patient Stratification Management (STRAT-MGT).

Covers:
- Seed data verification (factors, assessments, covariates, assignments, balances)
- Stratification Factor CRUD (create, read, update, delete, list, filter)
- Balance Assessment CRUD (create, read, update, delete, list, filter)
- Covariate Analysis CRUD (create, read, update, delete, list, filter)
- Arm Assignment CRUD (create, read, update, delete, list, filter)
- Randomization Balance CRUD (create, read, update, delete, list, filter)
- Metrics computation
- Not-found error handling (404s)
- Edge cases (empty filters, confirmation auto-date)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.patient_stratification import (
    AssignmentMethod,
    BalanceStatus,
    CovariateStatus,
    StratFactorType,
)
from app.services.patient_stratification_service import (
    PatientStratificationService,
    get_patient_stratification_service,
    reset_patient_stratification_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/patient-stratification"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_stratification_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientStratificationService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_factor_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "factor_name": "Test Factor",
        "factor_type": "demographic",
        "levels": ["Level A", "Level B"],
        "created_by": "Test User",
        "is_dynamic": False,
        "weight": 0.8,
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "factor_id": "SF-001",
        "factor_name": "Age Group",
        "assessed_by": "Test System",
        "arm_counts": {"Arm A": 25, "Arm B": 24},
    }
    defaults.update(overrides)
    return defaults


def _make_covariate_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "covariate_name": "Test Covariate",
        "covariate_type": "continuous",
        "analyst": "Dr. Test",
        "sample_size": 50,
    }
    defaults.update(overrides)
    return defaults


def _make_assignment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "subject_id": "SUBJ-TEST-001",
        "arm_name": "Treatment A",
        "assignment_method": "permuted_block",
        "stratification_values": {"Age Group": "50-64"},
    }
    defaults.update(overrides)
    return defaults


def _make_balance_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "generated_by": "Test System",
        "target_ratio": "1:1",
        "arm_distribution": {"Arm A": 30, "Arm B": 28},
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_factors_count(self, svc: PatientStratificationService):
        factors = svc.list_stratification_factors()
        assert len(factors) == 12

    def test_seed_factors_trials(self, svc: PatientStratificationService):
        factors = svc.list_stratification_factors()
        trial_ids = {f.trial_id for f in factors}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_factors_types(self, svc: PatientStratificationService):
        factors = svc.list_stratification_factors()
        types = {f.factor_type for f in factors}
        assert StratFactorType.DEMOGRAPHIC in types
        assert StratFactorType.DISEASE_SEVERITY in types
        assert StratFactorType.BIOMARKER in types
        assert StratFactorType.GEOGRAPHIC in types
        assert StratFactorType.PRIOR_THERAPY in types

    def test_seed_assessments_count(self, svc: PatientStratificationService):
        assessments = svc.list_balance_assessments()
        assert len(assessments) == 10

    def test_seed_assessments_statuses(self, svc: PatientStratificationService):
        assessments = svc.list_balance_assessments()
        statuses = {a.balance_status for a in assessments}
        assert BalanceStatus.BALANCED in statuses
        assert BalanceStatus.CRITICAL in statuses

    def test_seed_covariates_count(self, svc: PatientStratificationService):
        covariates = svc.list_covariate_analyses()
        assert len(covariates) == 10

    def test_seed_assignments_count(self, svc: PatientStratificationService):
        assignments = svc.list_arm_assignments()
        assert len(assignments) == 15

    def test_seed_assignments_methods(self, svc: PatientStratificationService):
        assignments = svc.list_arm_assignments()
        methods = {a.assignment_method for a in assignments}
        assert AssignmentMethod.PERMUTED_BLOCK in methods
        assert AssignmentMethod.MINIMIZATION in methods

    def test_seed_balances_count(self, svc: PatientStratificationService):
        balances = svc.list_randomization_balances()
        assert len(balances) == 10

    def test_seed_has_inactive_factor(self, svc: PatientStratificationService):
        factor = svc.get_stratification_factor("SF-011")
        assert factor is not None
        assert factor.is_active is False

    def test_seed_has_unconfirmed_assignment(self, svc: PatientStratificationService):
        assignment = svc.get_arm_assignment("AA-014")
        assert assignment is not None
        assert assignment.is_confirmed is False


# =====================================================================
# STRATIFICATION FACTOR CRUD
# =====================================================================


class TestFactorCrud:
    """Test stratification factor CRUD operations."""

    @pytest.mark.anyio
    async def test_list_factors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_factors_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_factors_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors", params={"factor_type": "biomarker"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["factor_type"] == "biomarker"

    @pytest.mark.anyio
    async def test_list_factors_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors", params={"is_active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 11  # 12 total minus 1 inactive

    @pytest.mark.anyio
    async def test_get_factor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors/SF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SF-001"
        assert data["factor_name"] == "Age Group"

    @pytest.mark.anyio
    async def test_get_factor_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors/SF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_factor(self, client: AsyncClient):
        payload = _make_factor_create()
        resp = await client.post(f"{API_PREFIX}/factors", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["factor_name"] == "Test Factor"
        assert data["factor_type"] == "demographic"
        assert data["id"].startswith("SF-")

    @pytest.mark.anyio
    async def test_update_factor(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/factors/SF-001",
            json={"weight": 0.5, "description": "Updated description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight"] == 0.5
        assert data["description"] == "Updated description"

    @pytest.mark.anyio
    async def test_update_factor_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/factors/SF-NONEXISTENT",
            json={"weight": 0.5},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_factor(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/factors/SF-011")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/factors/SF-011")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_factor_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/factors/SF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# BALANCE ASSESSMENT CRUD
# =====================================================================


class TestAssessmentCrud:
    """Test balance assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_assessments_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"balance_status": "balanced"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["balance_status"] == "balanced"

    @pytest.mark.anyio
    async def test_list_assessments_filter_factor(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"factor_id": "SF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["factor_id"] == "SF-001"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BA-001"
        assert data["balance_status"] == "balanced"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["factor_id"] == "SF-001"
        assert data["id"].startswith("BA-")
        assert data["total_randomized"] == 49

    @pytest.mark.anyio
    async def test_create_assessment_auto_balance_status(self, client: AsyncClient):
        """Creating with imbalanced counts should auto-set status."""
        payload = _make_assessment_create(arm_counts={"Arm A": 50, "Arm B": 30})
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["balance_status"] in ["imbalanced", "critical"]

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BA-001",
            json={"notes": "Updated assessment notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated assessment notes"

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/BA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/BA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/BA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COVARIATE ANALYSIS CRUD
# =====================================================================


class TestCovariateCrud:
    """Test covariate analysis CRUD operations."""

    @pytest.mark.anyio
    async def test_list_covariates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/covariates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_covariates_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/covariates", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_covariates_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/covariates", params={"status": "validated"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "validated"

    @pytest.mark.anyio
    async def test_get_covariate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/covariates/COV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COV-001"
        assert data["covariate_name"] == "Central Retinal Thickness"

    @pytest.mark.anyio
    async def test_get_covariate_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/covariates/COV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_covariate(self, client: AsyncClient):
        payload = _make_covariate_create()
        resp = await client.post(f"{API_PREFIX}/covariates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["covariate_name"] == "Test Covariate"
        assert data["id"].startswith("COV-")
        assert data["status"] == "planned"

    @pytest.mark.anyio
    async def test_update_covariate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/covariates/COV-008",
            json={"status": "collecting", "notes": "Data collection started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "collecting"
        assert data["notes"] == "Data collection started"

    @pytest.mark.anyio
    async def test_update_covariate_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/covariates/COV-NONEXISTENT",
            json={"status": "collecting"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_covariate(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/covariates/COV-009")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/covariates/COV-009")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_covariate_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/covariates/COV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ARM ASSIGNMENT CRUD
# =====================================================================


class TestAssignmentCrud:
    """Test arm assignment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_assignments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assignments", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_assignments_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assignments", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_assignments_filter_arm(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assignments", params={"arm_name": "Libtayo"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["arm_name"] == "Libtayo"

    @pytest.mark.anyio
    async def test_list_assignments_filter_method(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assignments", params={"assignment_method": "minimization"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["assignment_method"] == "minimization"

    @pytest.mark.anyio
    async def test_list_assignments_filter_confirmed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assignments", params={"is_confirmed": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # AA-014 and AA-015
        for item in data["items"]:
            assert item["is_confirmed"] is False

    @pytest.mark.anyio
    async def test_get_assignment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments/AA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AA-001"
        assert data["arm_name"] == "Eylea HD"
        assert data["is_confirmed"] is True

    @pytest.mark.anyio
    async def test_get_assignment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments/AA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assignment(self, client: AsyncClient):
        payload = _make_assignment_create()
        resp = await client.post(f"{API_PREFIX}/assignments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "SUBJ-TEST-001"
        assert data["arm_name"] == "Treatment A"
        assert data["id"].startswith("AA-")
        assert data["is_confirmed"] is False

    @pytest.mark.anyio
    async def test_update_assignment_confirm(self, client: AsyncClient):
        """Confirming an assignment should auto-set confirmed_date."""
        resp = await client.put(
            f"{API_PREFIX}/assignments/AA-014",
            json={"is_confirmed": True, "confirmed_by": "Dr. Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_confirmed"] is True
        assert data["confirmed_date"] is not None

    @pytest.mark.anyio
    async def test_update_assignment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assignments/AA-NONEXISTENT",
            json={"is_confirmed": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assignment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assignments/AA-015")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assignments/AA-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assignment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assignments/AA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RANDOMIZATION BALANCE CRUD
# =====================================================================


class TestBalanceCrud:
    """Test randomization balance CRUD operations."""

    @pytest.mark.anyio
    async def test_list_balances(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/balances")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_balances_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/balances", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_balances_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/balances", params={"overall_balance_status": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["overall_balance_status"] == "critical"

    @pytest.mark.anyio
    async def test_get_balance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/balances/RB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RB-001"
        assert data["overall_balance_status"] == "balanced"

    @pytest.mark.anyio
    async def test_get_balance_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/balances/RB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_balance(self, client: AsyncClient):
        payload = _make_balance_create()
        resp = await client.post(f"{API_PREFIX}/balances", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RB-")
        assert data["total_randomized"] == 58
        assert data["overall_balance_status"] == "balanced"

    @pytest.mark.anyio
    async def test_create_balance_imbalanced(self, client: AsyncClient):
        """Creating with significantly imbalanced counts should flag it."""
        payload = _make_balance_create(arm_distribution={"Arm A": 60, "Arm B": 40})
        resp = await client.post(f"{API_PREFIX}/balances", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["overall_balance_status"] in ["imbalanced", "critical"]

    @pytest.mark.anyio
    async def test_update_balance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/balances/RB-009",
            json={"recommendation": "Implement adaptive randomization"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendation"] == "Implement adaptive randomization"

    @pytest.mark.anyio
    async def test_update_balance_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/balances/RB-NONEXISTENT",
            json={"recommendation": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_balance(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/balances/RB-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/balances/RB-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_balance_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/balances/RB-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test patient stratification metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_factors"] == 12
        assert data["active_factors"] == 11
        assert data["total_assessments"] == 10
        assert data["total_covariates"] == 10
        assert data["total_assignments"] == 15
        assert data["total_balance_snapshots"] == 10

    @pytest.mark.anyio
    async def test_metrics_factors_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_type = sum(data["factors_by_type"].values())
        assert total_by_type == data["total_factors"]

    @pytest.mark.anyio
    async def test_metrics_assessments_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["assessments_by_status"].values())
        assert total_by_status == data["total_assessments"]

    @pytest.mark.anyio
    async def test_metrics_assignments_by_method(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_method = sum(data["assignments_by_method"].values())
        assert total_by_method == data["total_assignments"]

    @pytest.mark.anyio
    async def test_metrics_confirmed_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["confirmed_assignments"] == 13  # 15 total, 2 unconfirmed

    def test_metrics_current_balance_status(self, svc: PatientStratificationService):
        metrics = svc.get_metrics()
        assert metrics.current_balance_status is not None


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_patient_stratification_service()
        svc2 = get_patient_stratification_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_patient_stratification_service()
        svc2 = reset_patient_stratification_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_patient_stratification_service()
        svc.delete_stratification_factor("SF-001")
        assert svc.get_stratification_factor("SF-001") is None
        svc2 = reset_patient_stratification_service()
        assert svc2.get_stratification_factor("SF-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_factors_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_covariates_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/covariates")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_assignments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_balances_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/balances")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_factor_with_all_fields(self, client: AsyncClient):
        payload = _make_factor_create(
            factor_name="Complete Factor",
            factor_type="biomarker",
            levels=["Low", "Medium", "High"],
            weight=0.9,
            is_dynamic=True,
        )
        resp = await client.post(f"{API_PREFIX}/factors", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_dynamic"] is True
        assert len(data["levels"]) == 3

    @pytest.mark.anyio
    async def test_update_factor_deactivate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/factors/SF-001",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False

    @pytest.mark.anyio
    async def test_assignment_stratification_values(self, client: AsyncClient):
        """Verify stratification values are preserved in assignments."""
        resp = await client.get(f"{API_PREFIX}/assignments/AA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "Age Group" in data["stratification_values"]
        assert data["stratification_values"]["Age Group"] == "65-74"

    @pytest.mark.anyio
    async def test_balance_arm_distribution(self, client: AsyncClient):
        """Verify arm distribution data is preserved."""
        resp = await client.get(f"{API_PREFIX}/balances/RB-010")
        assert resp.status_code == 200
        data = resp.json()
        assert "Libtayo" in data["arm_distribution"]
        assert data["arm_distribution"]["Libtayo"] == 62

    @pytest.mark.anyio
    async def test_assessment_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        dates = [item["assessment_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_covariates_by_status_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        covariates_by_status = data["covariates_by_status"]
        total = sum(covariates_by_status.values())
        assert total == data["total_covariates"]

    def test_create_assignment_auto_sequence(self, svc: PatientStratificationService):
        """New assignments should get the next sequence number for their trial."""
        from app.schemas.patient_stratification import ArmAssignmentCreate

        payload = ArmAssignmentCreate(
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            subject_id="SUBJ-NEW-001",
            arm_name="Eylea HD",
            assignment_method=AssignmentMethod.PERMUTED_BLOCK,
        )
        assignment = svc.create_arm_assignment(payload)
        assert assignment.sequence_number == 6  # 5 existing EYLEA assignments + 1

    def test_update_assignment_confirm_sets_date(self, svc: PatientStratificationService):
        """Confirming an unconfirmed assignment should auto-set confirmed_date."""
        from app.schemas.patient_stratification import ArmAssignmentUpdate

        assignment = svc.get_arm_assignment("AA-014")
        assert assignment is not None
        assert assignment.is_confirmed is False
        assert assignment.confirmed_date is None

        updated = svc.update_arm_assignment(
            "AA-014", ArmAssignmentUpdate(is_confirmed=True, confirmed_by="Dr. Test")
        )
        assert updated is not None
        assert updated.is_confirmed is True
        assert updated.confirmed_date is not None


# =====================================================================
# ENUMERATIONS
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_factor_types_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/factors")
        data = resp.json()
        types = {item["factor_type"] for item in data["items"]}
        assert "demographic" in types
        assert "disease_severity" in types
        assert "biomarker" in types
        assert "geographic" in types
        assert "prior_therapy" in types
        assert "comorbidity" in types

    @pytest.mark.anyio
    async def test_balance_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        statuses = {item["balance_status"] for item in data["items"]}
        assert "balanced" in statuses
        assert "slightly_imbalanced" in statuses
        assert "imbalanced" in statuses
        assert "critical" in statuses

    @pytest.mark.anyio
    async def test_assignment_methods_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments")
        data = resp.json()
        methods = {item["assignment_method"] for item in data["items"]}
        assert "permuted_block" in methods
        assert "minimization" in methods
        assert "biased_coin" in methods

    @pytest.mark.anyio
    async def test_covariate_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/covariates")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "planned" in statuses
        assert "collecting" in statuses
        assert "complete" in statuses
        assert "validated" in statuses
        assert "locked" in statuses
