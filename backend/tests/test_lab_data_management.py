"""Tests for Lab Data Management (LAB-DATA).

Covers:
- Seed data verification (normal ranges, alert rules, specimens, results, alerts)
- Normal Range CRUD (create, read, update, delete, list, filter by category/test_code)
- Alert Rule CRUD (create, read, update, delete, list, filter by trial_id/active)
- Specimen CRUD (create, read, update, delete, list, filter by trial_id/status/subject_id)
- Result CRUD (create, read, update, delete, list, filter by trial_id/status/subject/category/flag)
- Alert CRUD (create/acknowledge, read, update, delete, list, filter by trial_id/severity/acknowledged)
- Metrics computation
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from fastapi import FastAPI

from app.api.lab_data_management import router as lab_data_management_router
from app.schemas.lab_data_management import (
    AbnormalFlag,
    AlertSeverity,
    GradeLevel,
    LabCategory,
    ResultStatus,
    SpecimenStatus,
)
from app.services.lab_data_management_service import (
    LabDataManagementService,
    get_lab_data_management_service,
    reset_lab_data_management_service,
)

# Build a lightweight test app with only our router registered
_test_app = FastAPI()
_test_app.include_router(lab_data_management_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/lab-data-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_lab_data_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> LabDataManagementService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_normal_range_create(**overrides) -> dict:
    defaults = {
        "test_name": "Glucose",
        "test_code": "GLU",
        "category": "chemistry",
        "unit": "mg/dL",
        "lower_limit": 70.0,
        "upper_limit": 100.0,
        "source": "ADA Guidelines 2024",
    }
    defaults.update(overrides)
    return defaults


def _make_alert_rule_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "test_name": "Glucose",
        "test_code": "GLU",
        "severity": "high",
        "condition": "value > 200",
        "threshold_value": 200.0,
        "threshold_unit": "mg/dL",
        "action_required": "Notify PI; check for diabetes",
        "notification_list": ["PI"],
        "created_by": "Dr. Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_specimen_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "visit": "Week 1",
        "specimen_type": "Whole Blood",
        "central_lab": "Test Central Lab",
        "site_id": "SITE-TEST",
    }
    defaults.update(overrides)
    return defaults


def _make_result_create(**overrides) -> dict:
    defaults = {
        "specimen_id": "SPEC-001",
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-1001",
        "test_name": "Glucose",
        "test_code": "GLU",
        "category": "chemistry",
        "unit": "mg/dL",
        "value": 95.0,
    }
    defaults.update(overrides)
    return defaults


def _make_alert_update(**overrides) -> dict:
    defaults = {
        "acknowledged": True,
        "acknowledged_by": "Dr. Test User",
        "action_taken": "Reviewed and addressed",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedDataNormalRanges:
    """Verify pre-seeded normal ranges."""

    def test_seed_total_normal_ranges(self, svc: LabDataManagementService):
        items = svc.list_normal_ranges()
        assert len(items) == 12

    def test_seed_hemoglobin_male(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-001")
        assert r is not None
        assert r.test_name == "Hemoglobin"
        assert r.test_code == "HGB"
        assert r.category == LabCategory.HEMATOLOGY
        assert r.gender == "M"
        assert r.lower_limit == 12.0
        assert r.upper_limit == 17.5

    def test_seed_hemoglobin_female(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-002")
        assert r is not None
        assert r.gender == "F"
        assert r.lower_limit == 11.5

    def test_seed_wbc(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-003")
        assert r is not None
        assert r.test_code == "WBC"
        assert not r.gender_specific

    def test_seed_platelet(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-004")
        assert r is not None
        assert r.test_code == "PLT"

    def test_seed_alt(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-005")
        assert r is not None
        assert r.category == LabCategory.HEPATIC

    def test_seed_ast(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-006")
        assert r is not None
        assert r.test_code == "AST"

    def test_seed_creatinine_male(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-007")
        assert r is not None
        assert r.category == LabCategory.RENAL

    def test_seed_cholesterol(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-009")
        assert r is not None
        assert r.category == LabCategory.LIPID

    def test_seed_tsh(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-010")
        assert r is not None
        assert r.category == LabCategory.ENDOCRINE

    def test_seed_crp(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-011")
        assert r is not None
        assert r.category == LabCategory.IMMUNOLOGY

    def test_seed_troponin(self, svc: LabDataManagementService):
        r = svc.get_normal_range("NR-012")
        assert r is not None
        assert r.category == LabCategory.CARDIAC


class TestSeedDataAlertRules:
    """Verify pre-seeded alert rules."""

    def test_seed_total_alert_rules(self, svc: LabDataManagementService):
        items = svc.list_alert_rules()
        assert len(items) == 12

    def test_seed_eylea_rules(self, svc: LabDataManagementService):
        items = svc.list_alert_rules(trial_id=EYLEA_TRIAL)
        assert len(items) == 4

    def test_seed_dupixent_rules(self, svc: LabDataManagementService):
        items = svc.list_alert_rules(trial_id=DUPIXENT_TRIAL)
        assert len(items) == 4

    def test_seed_libtayo_rules(self, svc: LabDataManagementService):
        items = svc.list_alert_rules(trial_id=LIBTAYO_TRIAL)
        assert len(items) == 4

    def test_seed_active_rules(self, svc: LabDataManagementService):
        items = svc.list_alert_rules(active=True)
        assert len(items) == 11

    def test_seed_inactive_rules(self, svc: LabDataManagementService):
        items = svc.list_alert_rules(active=False)
        assert len(items) == 1

    def test_seed_rule_001(self, svc: LabDataManagementService):
        r = svc.get_alert_rule("AR-001")
        assert r is not None
        assert r.severity == AlertSeverity.CRITICAL
        assert r.trial_id == EYLEA_TRIAL

    def test_seed_rule_011_panic(self, svc: LabDataManagementService):
        r = svc.get_alert_rule("AR-011")
        assert r is not None
        assert r.severity == AlertSeverity.PANIC

    def test_seed_rule_012_inactive(self, svc: LabDataManagementService):
        r = svc.get_alert_rule("AR-012")
        assert r is not None
        assert r.active is False


class TestSeedDataSpecimens:
    """Verify pre-seeded specimens."""

    def test_seed_total_specimens(self, svc: LabDataManagementService):
        items = svc.list_specimens()
        assert len(items) == 15

    def test_seed_eylea_specimens(self, svc: LabDataManagementService):
        items = svc.list_specimens(trial_id=EYLEA_TRIAL)
        assert len(items) == 5

    def test_seed_dupixent_specimens(self, svc: LabDataManagementService):
        items = svc.list_specimens(trial_id=DUPIXENT_TRIAL)
        assert len(items) == 5

    def test_seed_libtayo_specimens(self, svc: LabDataManagementService):
        items = svc.list_specimens(trial_id=LIBTAYO_TRIAL)
        assert len(items) == 5

    def test_seed_specimen_001(self, svc: LabDataManagementService):
        s = svc.get_specimen("SPEC-001")
        assert s is not None
        assert s.status == SpecimenStatus.ANALYZED
        assert s.subject_id == "SUBJ-1001"

    def test_seed_specimen_005_in_transit(self, svc: LabDataManagementService):
        s = svc.get_specimen("SPEC-005")
        assert s is not None
        assert s.status == SpecimenStatus.IN_TRANSIT

    def test_seed_specimen_015_lost(self, svc: LabDataManagementService):
        s = svc.get_specimen("SPEC-015")
        assert s is not None
        assert s.status == SpecimenStatus.LOST

    def test_seed_specimens_by_subject(self, svc: LabDataManagementService):
        items = svc.list_specimens(subject_id="SUBJ-1001")
        assert len(items) == 2

    def test_seed_specimens_by_status(self, svc: LabDataManagementService):
        items = svc.list_specimens(status=SpecimenStatus.ANALYZED)
        assert len(items) == 9


class TestSeedDataResults:
    """Verify pre-seeded results."""

    def test_seed_total_results(self, svc: LabDataManagementService):
        items = svc.list_results()
        assert len(items) == 18

    def test_seed_eylea_results(self, svc: LabDataManagementService):
        items = svc.list_results(trial_id=EYLEA_TRIAL)
        assert len(items) == 6

    def test_seed_dupixent_results(self, svc: LabDataManagementService):
        items = svc.list_results(trial_id=DUPIXENT_TRIAL)
        assert len(items) == 6

    def test_seed_libtayo_results(self, svc: LabDataManagementService):
        items = svc.list_results(trial_id=LIBTAYO_TRIAL)
        assert len(items) == 6

    def test_seed_result_001_normal(self, svc: LabDataManagementService):
        r = svc.get_result("RES-001")
        assert r is not None
        assert r.abnormal_flag == AbnormalFlag.NORMAL
        assert r.status == ResultStatus.FINAL

    def test_seed_result_004_high(self, svc: LabDataManagementService):
        r = svc.get_result("RES-004")
        assert r is not None
        assert r.abnormal_flag == AbnormalFlag.HIGH
        assert r.clinically_significant is True

    def test_seed_result_009_critical_high(self, svc: LabDataManagementService):
        r = svc.get_result("RES-009")
        assert r is not None
        assert r.abnormal_flag == AbnormalFlag.CRITICAL_HIGH
        assert r.grade == GradeLevel.GRADE_3

    def test_seed_result_015_grade4(self, svc: LabDataManagementService):
        r = svc.get_result("RES-015")
        assert r is not None
        assert r.grade == GradeLevel.GRADE_4

    def test_seed_result_018_pending(self, svc: LabDataManagementService):
        r = svc.get_result("RES-018")
        assert r is not None
        assert r.status == ResultStatus.PENDING

    def test_seed_results_by_status(self, svc: LabDataManagementService):
        items = svc.list_results(status=ResultStatus.FINAL)
        assert len(items) >= 15

    def test_seed_results_by_category(self, svc: LabDataManagementService):
        items = svc.list_results(category=LabCategory.HEMATOLOGY)
        assert len(items) >= 6

    def test_seed_results_by_flag(self, svc: LabDataManagementService):
        items = svc.list_results(abnormal_flag=AbnormalFlag.NORMAL)
        assert len(items) >= 7


class TestSeedDataAlerts:
    """Verify pre-seeded alerts."""

    def test_seed_total_alerts(self, svc: LabDataManagementService):
        items = svc.list_alerts()
        assert len(items) == 10

    def test_seed_eylea_alerts(self, svc: LabDataManagementService):
        items = svc.list_alerts(trial_id=EYLEA_TRIAL)
        assert len(items) == 3

    def test_seed_dupixent_alerts(self, svc: LabDataManagementService):
        items = svc.list_alerts(trial_id=DUPIXENT_TRIAL)
        assert len(items) == 2

    def test_seed_libtayo_alerts(self, svc: LabDataManagementService):
        items = svc.list_alerts(trial_id=LIBTAYO_TRIAL)
        assert len(items) == 5

    def test_seed_alert_001_acknowledged(self, svc: LabDataManagementService):
        a = svc.get_alert("ALERT-001")
        assert a is not None
        assert a.acknowledged is True
        assert a.acknowledged_by == "Dr. Sarah Kim"

    def test_seed_alert_004_unacknowledged(self, svc: LabDataManagementService):
        a = svc.get_alert("ALERT-004")
        assert a is not None
        assert a.acknowledged is False

    def test_seed_alert_008_panic(self, svc: LabDataManagementService):
        a = svc.get_alert("ALERT-008")
        assert a is not None
        assert a.severity == AlertSeverity.PANIC

    def test_seed_acknowledged_alerts(self, svc: LabDataManagementService):
        items = svc.list_alerts(acknowledged=True)
        assert len(items) == 8

    def test_seed_unacknowledged_alerts(self, svc: LabDataManagementService):
        items = svc.list_alerts(acknowledged=False)
        assert len(items) == 2

    def test_seed_alerts_by_severity_critical(self, svc: LabDataManagementService):
        items = svc.list_alerts(severity=AlertSeverity.CRITICAL)
        assert len(items) == 1


# ===========================================================================
# NORMAL RANGE API CRUD
# ===========================================================================


class TestNormalRangeAPI:
    """Test Normal Range API endpoints."""

    @pytest.mark.anyio
    async def test_list_normal_ranges(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/normal-ranges")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_normal_ranges_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/normal-ranges", params={"category": "hematology"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_normal_ranges_filter_test_code(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/normal-ranges", params={"test_code": "HGB"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_normal_ranges_filter_hepatic(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/normal-ranges", params={"category": "hepatic"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_normal_ranges_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/normal-ranges", params={"test_code": "NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_normal_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/normal-ranges/NR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["test_name"] == "Hemoglobin"

    @pytest.mark.anyio
    async def test_get_normal_range_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/normal-ranges/NR-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_normal_range(self, client: AsyncClient):
        payload = _make_normal_range_create()
        resp = await client.post(f"{API_PREFIX}/normal-ranges", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["test_name"] == "Glucose"
        assert data["test_code"] == "GLU"
        assert data["id"].startswith("NR-")

    @pytest.mark.anyio
    async def test_create_normal_range_minimal(self, client: AsyncClient):
        payload = _make_normal_range_create(lower_limit=None, upper_limit=None)
        resp = await client.post(f"{API_PREFIX}/normal-ranges", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_normal_range_increases_total(self, client: AsyncClient):
        payload = _make_normal_range_create()
        await client.post(f"{API_PREFIX}/normal-ranges", json=payload)
        resp = await client.get(f"{API_PREFIX}/normal-ranges")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_normal_range(self, client: AsyncClient):
        payload = _make_normal_range_create(
            test_name="Hemoglobin",
            test_code="HGB",
            category="hematology",
            unit="g/dL",
            lower_limit=13.0,
            upper_limit=18.0,
            source="Updated Guidelines",
        )
        resp = await client.put(f"{API_PREFIX}/normal-ranges/NR-001", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["lower_limit"] == 13.0

    @pytest.mark.anyio
    async def test_update_normal_range_not_found(self, client: AsyncClient):
        payload = _make_normal_range_create()
        resp = await client.put(f"{API_PREFIX}/normal-ranges/NR-999", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_normal_range(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/normal-ranges/NR-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_normal_range_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/normal-ranges/NR-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_normal_range_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/normal-ranges/NR-001")
        resp = await client.get(f"{API_PREFIX}/normal-ranges/NR-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_normal_range_reduces_total(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/normal-ranges/NR-001")
        resp = await client.get(f"{API_PREFIX}/normal-ranges")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_create_and_get_normal_range(self, client: AsyncClient):
        payload = _make_normal_range_create()
        create_resp = await client.post(f"{API_PREFIX}/normal-ranges", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.get(f"{API_PREFIX}/normal-ranges/{created_id}")
        assert resp.status_code == 200
        assert resp.json()["test_name"] == "Glucose"

    @pytest.mark.anyio
    async def test_create_and_delete_normal_range(self, client: AsyncClient):
        payload = _make_normal_range_create()
        create_resp = await client.post(f"{API_PREFIX}/normal-ranges", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.delete(f"{API_PREFIX}/normal-ranges/{created_id}")
        assert resp.status_code == 204


# ===========================================================================
# ALERT RULE API CRUD
# ===========================================================================


class TestAlertRuleAPI:
    """Test Alert Rule API endpoints."""

    @pytest.mark.anyio
    async def test_list_alert_rules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alert-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_alert_rules_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alert-rules", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_list_alert_rules_filter_active_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alert-rules", params={"active": True})
        assert resp.status_code == 200
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_list_alert_rules_filter_active_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alert-rules", params={"active": False})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_alert_rules_combined_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/alert-rules",
            params={"trial_id": LIBTAYO_TRIAL, "active": True},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_list_alert_rules_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alert-rules", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_alert_rule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alert-rules/AR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "critical"

    @pytest.mark.anyio
    async def test_get_alert_rule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alert-rules/AR-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_alert_rule(self, client: AsyncClient):
        payload = _make_alert_rule_create()
        resp = await client.post(f"{API_PREFIX}/alert-rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["test_name"] == "Glucose"
        assert data["id"].startswith("AR-")

    @pytest.mark.anyio
    async def test_create_alert_rule_increases_total(self, client: AsyncClient):
        payload = _make_alert_rule_create()
        await client.post(f"{API_PREFIX}/alert-rules", json=payload)
        resp = await client.get(f"{API_PREFIX}/alert-rules")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_alert_rule(self, client: AsyncClient):
        payload = {"severity": "medium", "active": False}
        resp = await client.put(f"{API_PREFIX}/alert-rules/AR-001", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "medium"
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_update_alert_rule_partial(self, client: AsyncClient):
        payload = {"active": False}
        resp = await client.put(f"{API_PREFIX}/alert-rules/AR-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["active"] is False
        assert resp.json()["severity"] == "critical"  # unchanged

    @pytest.mark.anyio
    async def test_update_alert_rule_not_found(self, client: AsyncClient):
        payload = {"severity": "low"}
        resp = await client.put(f"{API_PREFIX}/alert-rules/AR-999", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert_rule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alert-rules/AR-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_alert_rule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alert-rules/AR-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert_rule_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/alert-rules/AR-001")
        resp = await client.get(f"{API_PREFIX}/alert-rules/AR-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_alert_rule(self, client: AsyncClient):
        payload = _make_alert_rule_create()
        create_resp = await client.post(f"{API_PREFIX}/alert-rules", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.get(f"{API_PREFIX}/alert-rules/{created_id}")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_and_delete_alert_rule(self, client: AsyncClient):
        payload = _make_alert_rule_create()
        create_resp = await client.post(f"{API_PREFIX}/alert-rules", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.delete(f"{API_PREFIX}/alert-rules/{created_id}")
        assert resp.status_code == 204


# ===========================================================================
# SPECIMEN API CRUD
# ===========================================================================


class TestSpecimenAPI:
    """Test Specimen API endpoints."""

    @pytest.mark.anyio
    async def test_list_specimens(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_specimens_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    @pytest.mark.anyio
    async def test_list_specimens_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"status": "analyzed"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 9

    @pytest.mark.anyio
    async def test_list_specimens_filter_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"subject_id": "SUBJ-1001"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_specimens_combined_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/specimens",
            params={"trial_id": LIBTAYO_TRIAL, "status": "analyzed"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_list_specimens_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_id"] == "SUBJ-1001"

    @pytest.mark.anyio
    async def test_get_specimen_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_specimen(self, client: AsyncClient):
        payload = _make_specimen_create()
        resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SPEC-")
        assert data["status"] == "collected"

    @pytest.mark.anyio
    async def test_create_specimen_with_fasting(self, client: AsyncClient):
        payload = _make_specimen_create(fasting=True)
        resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        assert resp.status_code == 201
        assert resp.json()["fasting"] is True

    @pytest.mark.anyio
    async def test_create_specimen_increases_total(self, client: AsyncClient):
        payload = _make_specimen_create()
        await client.post(f"{API_PREFIX}/specimens", json=payload)
        resp = await client.get(f"{API_PREFIX}/specimens")
        assert resp.json()["total"] == 16

    @pytest.mark.anyio
    async def test_update_specimen(self, client: AsyncClient):
        payload = {"status": "received", "accession_number": "ACC-TEST-001"}
        resp = await client.put(f"{API_PREFIX}/specimens/SPEC-005", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received"
        assert data["accession_number"] == "ACC-TEST-001"

    @pytest.mark.anyio
    async def test_update_specimen_partial(self, client: AsyncClient):
        payload = {"condition_on_receipt": "Hemolyzed"}
        resp = await client.put(f"{API_PREFIX}/specimens/SPEC-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["condition_on_receipt"] == "Hemolyzed"

    @pytest.mark.anyio
    async def test_update_specimen_not_found(self, client: AsyncClient):
        payload = {"status": "received"}
        resp = await client.put(f"{API_PREFIX}/specimens/SPEC-999", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimens/SPEC-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_specimen_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimens/SPEC-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/specimens/SPEC-001")
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_specimen(self, client: AsyncClient):
        payload = _make_specimen_create()
        create_resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.get(f"{API_PREFIX}/specimens/{created_id}")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_and_delete_specimen(self, client: AsyncClient):
        payload = _make_specimen_create()
        create_resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.delete(f"{API_PREFIX}/specimens/{created_id}")
        assert resp.status_code == 204


# ===========================================================================
# RESULT API CRUD
# ===========================================================================


class TestResultAPI:
    """Test Result API endpoints."""

    @pytest.mark.anyio
    async def test_list_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 18

    @pytest.mark.anyio
    async def test_list_results_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 6

    @pytest.mark.anyio
    async def test_list_results_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"status": "final"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 15

    @pytest.mark.anyio
    async def test_list_results_filter_subject(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"subject_id": "SUBJ-1001"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 4

    @pytest.mark.anyio
    async def test_list_results_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"category": "hematology"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 6

    @pytest.mark.anyio
    async def test_list_results_filter_abnormal_flag(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"abnormal_flag": "normal"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 7

    @pytest.mark.anyio
    async def test_list_results_filter_critical_high(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"abnormal_flag": "critical_high"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    @pytest.mark.anyio
    async def test_list_results_combined_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/results",
            params={"trial_id": LIBTAYO_TRIAL, "category": "hepatic"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.anyio
    async def test_list_results_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/RES-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["test_name"] == "Hemoglobin"

    @pytest.mark.anyio
    async def test_get_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/RES-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_result(self, client: AsyncClient):
        payload = _make_result_create()
        resp = await client.post(f"{API_PREFIX}/results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RES-")
        assert data["status"] == "pending"
        assert data["abnormal_flag"] == "normal"

    @pytest.mark.anyio
    async def test_create_result_with_value_text(self, client: AsyncClient):
        payload = _make_result_create(value=None, value_text="Positive")
        resp = await client.post(f"{API_PREFIX}/results", json=payload)
        assert resp.status_code == 201
        assert resp.json()["value_text"] == "Positive"

    @pytest.mark.anyio
    async def test_create_result_increases_total(self, client: AsyncClient):
        payload = _make_result_create()
        await client.post(f"{API_PREFIX}/results", json=payload)
        resp = await client.get(f"{API_PREFIX}/results")
        assert resp.json()["total"] == 19

    @pytest.mark.anyio
    async def test_update_result(self, client: AsyncClient):
        payload = {
            "status": "final",
            "abnormal_flag": "high",
            "grade": "grade_1_mild",
            "verified_by": "Dr. Test",
            "clinically_significant": True,
            "investigator_comment": "Needs follow-up",
        }
        resp = await client.put(f"{API_PREFIX}/results/RES-018", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "final"
        assert data["abnormal_flag"] == "high"
        assert data["verified_by"] == "Dr. Test"

    @pytest.mark.anyio
    async def test_update_result_partial(self, client: AsyncClient):
        payload = {"status": "amended"}
        resp = await client.put(f"{API_PREFIX}/results/RES-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "amended"
        assert resp.json()["test_name"] == "Hemoglobin"  # unchanged

    @pytest.mark.anyio
    async def test_update_result_not_found(self, client: AsyncClient):
        payload = {"status": "final"}
        resp = await client.put(f"{API_PREFIX}/results/RES-999", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/results/RES-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_result_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/results/RES-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_result_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/results/RES-001")
        resp = await client.get(f"{API_PREFIX}/results/RES-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_get_result(self, client: AsyncClient):
        payload = _make_result_create()
        create_resp = await client.post(f"{API_PREFIX}/results", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.get(f"{API_PREFIX}/results/{created_id}")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_and_delete_result(self, client: AsyncClient):
        payload = _make_result_create()
        create_resp = await client.post(f"{API_PREFIX}/results", json=payload)
        created_id = create_resp.json()["id"]
        resp = await client.delete(f"{API_PREFIX}/results/{created_id}")
        assert resp.status_code == 204


# ===========================================================================
# ALERT API CRUD
# ===========================================================================


class TestAlertAPI:
    """Test Alert API endpoints."""

    @pytest.mark.anyio
    async def test_list_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_alerts_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_list_alerts_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"severity": "panic"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_alerts_filter_acknowledged_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"acknowledged": True})
        assert resp.status_code == 200
        assert resp.json()["total"] == 8

    @pytest.mark.anyio
    async def test_list_alerts_filter_acknowledged_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"acknowledged": False})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_alerts_combined_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/alerts",
            params={"trial_id": LIBTAYO_TRIAL, "acknowledged": False},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_alerts_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/ALERT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "high"

    @pytest.mark.anyio
    async def test_get_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/ALERT-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_alert_acknowledge(self, client: AsyncClient):
        payload = _make_alert_update()
        resp = await client.put(f"{API_PREFIX}/alerts/ALERT-004", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["acknowledged_by"] == "Dr. Test User"
        assert data["acknowledged_date"] is not None
        assert data["action_taken"] == "Reviewed and addressed"

    @pytest.mark.anyio
    async def test_update_alert_partial(self, client: AsyncClient):
        payload = {"action_taken": "Under review"}
        resp = await client.put(f"{API_PREFIX}/alerts/ALERT-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "Under review"

    @pytest.mark.anyio
    async def test_update_alert_not_found(self, client: AsyncClient):
        payload = _make_alert_update()
        resp = await client.put(f"{API_PREFIX}/alerts/ALERT-999", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alerts/ALERT-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_alert_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alerts/ALERT-999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/alerts/ALERT-001")
        resp = await client.get(f"{API_PREFIX}/alerts/ALERT-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert_reduces_total(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/alerts/ALERT-001")
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.json()["total"] == 9


# ===========================================================================
# METRICS API
# ===========================================================================


class TestMetricsAPI:
    """Test Metrics API endpoint."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_normal_ranges"] == 12
        assert data["total_alert_rules"] == 12
        assert data["active_alert_rules"] == 11
        assert data["total_specimens"] == 15
        assert data["total_results"] == 18
        assert data["total_alerts"] == 10
        assert data["unacknowledged_alerts"] == 2

    @pytest.mark.anyio
    async def test_get_metrics_ranges_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "hematology" in data["ranges_by_category"]
        assert data["ranges_by_category"]["hematology"] == 4

    @pytest.mark.anyio
    async def test_get_metrics_specimens_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "analyzed" in data["specimens_by_status"]
        assert data["specimens_by_status"]["analyzed"] == 9

    @pytest.mark.anyio
    async def test_get_metrics_results_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "final" in data["results_by_status"]

    @pytest.mark.anyio
    async def test_get_metrics_results_by_flag(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "normal" in data["results_by_flag"]

    @pytest.mark.anyio
    async def test_get_metrics_abnormal_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["abnormal_rate_pct"] > 0
        assert data["abnormal_rate_pct"] <= 100

    @pytest.mark.anyio
    async def test_get_metrics_critical_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["critical_results"] >= 3

    @pytest.mark.anyio
    async def test_get_metrics_alerts_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "panic" in data["alerts_by_severity"]
        assert data["alerts_by_severity"]["panic"] == 1

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 5
        assert data["total_results"] == 6
        assert data["total_alerts"] == 3

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 5
        assert data["total_results"] == 6
        assert data["total_alerts"] == 2

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 5
        assert data["total_results"] == 6
        assert data["total_alerts"] == 5

    @pytest.mark.anyio
    async def test_get_metrics_filter_empty_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 0
        assert data["total_results"] == 0
        assert data["total_alerts"] == 0
        assert data["abnormal_rate_pct"] == 0.0

    @pytest.mark.anyio
    async def test_metrics_after_create_result(self, client: AsyncClient):
        payload = _make_result_create()
        await client.post(f"{API_PREFIX}/results", json=payload)
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.json()["total_results"] == 19

    @pytest.mark.anyio
    async def test_metrics_after_delete_alert(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/alerts/ALERT-004")
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_alerts"] == 9
        assert data["unacknowledged_alerts"] == 1

    @pytest.mark.anyio
    async def test_metrics_normal_ranges_not_filtered_by_trial(self, client: AsyncClient):
        """Normal ranges are global, not trial-specific; total should remain 12."""
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        data = resp.json()
        assert data["total_normal_ranges"] == 12


# ===========================================================================
# SERVICE LAYER UNIT TESTS
# ===========================================================================


class TestServiceNormalRange:
    """Test service-level normal range operations."""

    def test_create_normal_range(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabNormalRangeCreate
        payload = LabNormalRangeCreate(
            test_name="Glucose",
            test_code="GLU",
            category=LabCategory.CHEMISTRY,
            unit="mg/dL",
            lower_limit=70.0,
            upper_limit=100.0,
            source="ADA Guidelines",
        )
        result = svc.create_normal_range(payload)
        assert result.id.startswith("NR-")
        assert result.test_name == "Glucose"

    def test_get_nonexistent_normal_range(self, svc: LabDataManagementService):
        assert svc.get_normal_range("NR-NOPE") is None

    def test_delete_nonexistent_normal_range(self, svc: LabDataManagementService):
        assert svc.delete_normal_range("NR-NOPE") is False

    def test_update_nonexistent_normal_range(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabNormalRangeCreate
        payload = LabNormalRangeCreate(
            test_name="X",
            test_code="X",
            category=LabCategory.CHEMISTRY,
            unit="mg/dL",
            source="Test",
        )
        assert svc.update_normal_range("NR-NOPE", payload) is None

    def test_filter_by_category(self, svc: LabDataManagementService):
        items = svc.list_normal_ranges(category=LabCategory.CARDIAC)
        assert len(items) == 1
        assert items[0].test_code == "TROP-I"

    def test_filter_by_test_code(self, svc: LabDataManagementService):
        items = svc.list_normal_ranges(test_code="CREAT")
        assert len(items) == 2


class TestServiceAlertRule:
    """Test service-level alert rule operations."""

    def test_create_alert_rule(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabAlertRuleCreate
        payload = LabAlertRuleCreate(
            trial_id=EYLEA_TRIAL,
            test_name="Glucose",
            test_code="GLU",
            severity=AlertSeverity.HIGH,
            condition="value > 200",
            action_required="Notify PI",
            created_by="Test",
        )
        result = svc.create_alert_rule(payload)
        assert result.id.startswith("AR-")
        assert result.active is True

    def test_get_nonexistent_alert_rule(self, svc: LabDataManagementService):
        assert svc.get_alert_rule("AR-NOPE") is None

    def test_delete_nonexistent_alert_rule(self, svc: LabDataManagementService):
        assert svc.delete_alert_rule("AR-NOPE") is False

    def test_update_nonexistent_alert_rule(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabAlertRuleUpdate
        payload = LabAlertRuleUpdate(active=False)
        assert svc.update_alert_rule("AR-NOPE", payload) is None

    def test_filter_active_and_trial(self, svc: LabDataManagementService):
        items = svc.list_alert_rules(trial_id=LIBTAYO_TRIAL, active=True)
        assert len(items) == 3


class TestServiceSpecimen:
    """Test service-level specimen operations."""

    def test_create_specimen(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabSpecimenCreate
        payload = LabSpecimenCreate(
            trial_id=EYLEA_TRIAL,
            subject_id="SUBJ-TEST",
            visit="Screening",
            specimen_type="Whole Blood",
            central_lab="Test Lab",
            site_id="SITE-T1",
        )
        result = svc.create_specimen(payload)
        assert result.id.startswith("SPEC-")
        assert result.status == SpecimenStatus.COLLECTED

    def test_get_nonexistent_specimen(self, svc: LabDataManagementService):
        assert svc.get_specimen("SPEC-NOPE") is None

    def test_delete_nonexistent_specimen(self, svc: LabDataManagementService):
        assert svc.delete_specimen("SPEC-NOPE") is False

    def test_update_nonexistent_specimen(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabSpecimenUpdate
        payload = LabSpecimenUpdate(status=SpecimenStatus.RECEIVED)
        assert svc.update_specimen("SPEC-NOPE", payload) is None

    def test_filter_by_status(self, svc: LabDataManagementService):
        items = svc.list_specimens(status=SpecimenStatus.LOST)
        assert len(items) == 1

    def test_filter_by_subject_and_trial(self, svc: LabDataManagementService):
        items = svc.list_specimens(trial_id=DUPIXENT_TRIAL, subject_id="SUBJ-2001")
        assert len(items) == 2


class TestServiceResult:
    """Test service-level result operations."""

    def test_create_result(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabResultCreate
        payload = LabResultCreate(
            specimen_id="SPEC-001",
            trial_id=EYLEA_TRIAL,
            subject_id="SUBJ-1001",
            test_name="Glucose",
            test_code="GLU",
            category=LabCategory.CHEMISTRY,
            unit="mg/dL",
            value=95.0,
        )
        result = svc.create_result(payload)
        assert result.id.startswith("RES-")
        assert result.status == ResultStatus.PENDING

    def test_get_nonexistent_result(self, svc: LabDataManagementService):
        assert svc.get_result("RES-NOPE") is None

    def test_delete_nonexistent_result(self, svc: LabDataManagementService):
        assert svc.delete_result("RES-NOPE") is False

    def test_update_nonexistent_result(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabResultUpdate
        payload = LabResultUpdate(status=ResultStatus.FINAL)
        assert svc.update_result("RES-NOPE", payload) is None

    def test_filter_by_flag(self, svc: LabDataManagementService):
        items = svc.list_results(abnormal_flag=AbnormalFlag.CRITICAL_HIGH)
        assert len(items) >= 3

    def test_filter_by_category_and_trial(self, svc: LabDataManagementService):
        items = svc.list_results(trial_id=EYLEA_TRIAL, category=LabCategory.HEPATIC)
        assert len(items) == 2


class TestServiceAlert:
    """Test service-level alert operations."""

    def test_create_alert(self, svc: LabDataManagementService):
        alert = svc.create_alert(
            result_id="RES-001",
            rule_id="AR-001",
            trial_id=EYLEA_TRIAL,
            subject_id="SUBJ-1001",
            severity=AlertSeverity.HIGH,
            message="Test alert",
        )
        assert alert.id.startswith("ALERT-")
        assert alert.acknowledged is False

    def test_get_nonexistent_alert(self, svc: LabDataManagementService):
        assert svc.get_alert("ALERT-NOPE") is None

    def test_delete_nonexistent_alert(self, svc: LabDataManagementService):
        assert svc.delete_alert("ALERT-NOPE") is False

    def test_update_nonexistent_alert(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabAlertUpdate
        payload = LabAlertUpdate(acknowledged=True)
        assert svc.update_alert("ALERT-NOPE", payload) is None

    def test_acknowledge_alert_sets_date(self, svc: LabDataManagementService):
        from app.schemas.lab_data_management import LabAlertUpdate
        payload = LabAlertUpdate(acknowledged=True, acknowledged_by="Tester")
        result = svc.update_alert("ALERT-004", payload)
        assert result is not None
        assert result.acknowledged is True
        assert result.acknowledged_date is not None

    def test_filter_by_severity(self, svc: LabDataManagementService):
        items = svc.list_alerts(severity=AlertSeverity.PANIC)
        assert len(items) == 1

    def test_filter_by_acknowledged(self, svc: LabDataManagementService):
        items = svc.list_alerts(acknowledged=False)
        assert len(items) == 2


class TestServiceMetrics:
    """Test service-level metrics computation."""

    def test_metrics_totals(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.total_normal_ranges == 12
        assert m.total_alert_rules == 12
        assert m.total_specimens == 15
        assert m.total_results == 18
        assert m.total_alerts == 10

    def test_metrics_active_rules(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.active_alert_rules == 11

    def test_metrics_abnormal_rate(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.abnormal_rate_pct > 0

    def test_metrics_critical_results(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.critical_results >= 3

    def test_metrics_unacknowledged(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.unacknowledged_alerts == 2

    def test_metrics_trial_filter(self, svc: LabDataManagementService):
        m = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert m.total_specimens == 5
        assert m.total_results == 6
        assert m.total_alerts == 3

    def test_metrics_empty_trial(self, svc: LabDataManagementService):
        m = svc.get_metrics(trial_id="nonexistent")
        assert m.total_specimens == 0
        assert m.total_results == 0
        assert m.abnormal_rate_pct == 0.0

    def test_metrics_ranges_by_category(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.ranges_by_category["hematology"] == 4
        assert m.ranges_by_category["hepatic"] == 2
        assert m.ranges_by_category["renal"] == 2

    def test_metrics_specimens_by_status(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.specimens_by_status["analyzed"] == 9

    def test_metrics_results_by_flag(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert "normal" in m.results_by_flag

    def test_metrics_alerts_by_severity(self, svc: LabDataManagementService):
        m = svc.get_metrics()
        assert m.alerts_by_severity["panic"] == 1


# ===========================================================================
# VALIDATION / ERROR EDGE CASES
# ===========================================================================


class TestValidationErrors:
    """Test validation and edge cases."""

    @pytest.mark.anyio
    async def test_create_normal_range_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/normal-ranges", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_alert_rule_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/alert-rules", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_specimen_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/specimens", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_result_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/results", json={})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_normal_range_invalid_category(self, client: AsyncClient):
        payload = _make_normal_range_create(category="nonexistent_category")
        resp = await client.post(f"{API_PREFIX}/normal-ranges", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_alert_rule_invalid_severity(self, client: AsyncClient):
        payload = _make_alert_rule_create(severity="nonexistent_severity")
        resp = await client.post(f"{API_PREFIX}/alert-rules", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_result_invalid_status(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/results/RES-001", json={"status": "invalid_status"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_specimen_invalid_status(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/specimens/SPEC-001", json={"status": "invalid_status"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_result_invalid_category(self, client: AsyncClient):
        payload = _make_result_create(category="nonexistent")
        resp = await client.post(f"{API_PREFIX}/results", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_double_delete_normal_range(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/normal-ranges/NR-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/normal-ranges/NR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_alert_rule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alert-rules/AR-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/alert-rules/AR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_specimen(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimens/SPEC-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/specimens/SPEC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/results/RES-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/results/RES-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_alert(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alerts/ALERT-001")
        assert resp.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/alerts/ALERT-001")
        assert resp2.status_code == 404


# ===========================================================================
# SINGLETON TESTS
# ===========================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_returns_same_instance(self):
        svc1 = get_lab_data_management_service()
        svc2 = get_lab_data_management_service()
        assert svc1 is svc2

    def test_reset_returns_new_instance(self):
        svc1 = get_lab_data_management_service()
        svc2 = reset_lab_data_management_service()
        assert svc1 is not svc2

    def test_reset_preserves_seed_data(self):
        svc = reset_lab_data_management_service()
        assert len(svc.list_normal_ranges()) == 12
        assert len(svc.list_alert_rules()) == 12
        assert len(svc.list_specimens()) == 15
        assert len(svc.list_results()) == 18
        assert len(svc.list_alerts()) == 10
