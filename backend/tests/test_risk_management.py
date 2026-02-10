"""Tests for Clinical Trial Risk Management (RISK-MGMT).

Covers:
- Seed data verification (risks, mitigations, reviews, issues)
- Risk CRUD (create, read, update, delete, list, filter by trial/category/level/status)
- Risk level computation from probability x impact matrix
- Mitigation CRUD (create, read, update, delete, list, filter by risk/status)
- Mitigation linked to risk via risk_id
- Review management (create, list, filter; updates risk last_reviewed)
- Issue CRUD (create, read, update, delete, list, filter by trial/risk/status/severity/category)
- Issues optionally linked to risks
- Metrics computation (overdue mitigations, critical risks, open issues)
- Error handling (404s, 400s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.risk_management import (
    IssueStatus,
    MitigationStatus,
    RiskCategory,
    RiskImpact,
    RiskLevel,
    RiskProbability,
    RiskStatus,
)
from app.services.risk_management_service import (
    RiskManagementService,
    compute_risk_level,
    get_risk_management_service,
    reset_risk_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/risk-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_risk_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> RiskManagementService:
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


def _make_risk_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "risk_title": "Test Risk Title",
        "category": "safety",
        "description": "A test risk description",
        "probability": "possible",
        "impact": "major",
        "risk_level": "high",
        "identified_by": "Test User",
        "owner": "Test Owner",
        "affected_areas": ["area1", "area2"],
        "triggers": ["trigger1"],
    }
    defaults.update(overrides)
    return defaults


def _make_mitigation_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "risk_id": "RSK-001",
        "action": "Test mitigation action",
        "responsible_party": "Test Person",
        "due_date": (now + timedelta(days=30)).isoformat(),
        "cost_estimate": 10000.0,
    }
    defaults.update(overrides)
    return defaults


def _make_review_create(**overrides) -> dict:
    defaults = {
        "risk_id": "RSK-001",
        "reviewer": "Test Reviewer",
        "current_probability": "possible",
        "current_impact": "major",
        "current_risk_level": "high",
        "notes": "Test review notes",
        "action_items": ["action1", "action2"],
        "next_review_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_issue_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "risk_id": "RSK-001",
        "title": "Test Issue Title",
        "description": "A test issue description",
        "category": "safety",
        "severity": "high",
        "reported_by": "Test Reporter",
        "assigned_to": "Test Assignee",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_risks_count(self, svc: RiskManagementService):
        risks = svc.list_risks()
        assert len(risks) == 12

    def test_seed_risks_across_trials(self, svc: RiskManagementService):
        trials = {r.trial_id for r in svc.list_risks()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_risks_categories_present(self, svc: RiskManagementService):
        categories = {r.category for r in svc.list_risks()}
        assert RiskCategory.SAFETY in categories
        assert RiskCategory.QUALITY in categories
        assert RiskCategory.OPERATIONAL in categories
        assert RiskCategory.REGULATORY in categories
        assert RiskCategory.FINANCIAL in categories
        assert RiskCategory.SCIENTIFIC in categories
        assert RiskCategory.REPUTATIONAL in categories
        assert RiskCategory.SUPPLY in categories

    def test_seed_risks_levels_present(self, svc: RiskManagementService):
        levels = {r.risk_level for r in svc.list_risks()}
        assert RiskLevel.HIGH in levels
        assert RiskLevel.CRITICAL in levels
        assert RiskLevel.MEDIUM in levels

    def test_seed_risks_statuses_present(self, svc: RiskManagementService):
        statuses = {r.status for r in svc.list_risks()}
        assert RiskStatus.IDENTIFIED in statuses
        assert RiskStatus.ASSESSED in statuses
        assert RiskStatus.MITIGATING in statuses
        assert RiskStatus.MONITORING in statuses

    def test_seed_mitigations_count(self, svc: RiskManagementService):
        mitigations = svc.list_mitigations()
        assert len(mitigations) == 15

    def test_seed_mitigations_statuses_present(self, svc: RiskManagementService):
        statuses = {m.status for m in svc.list_mitigations()}
        assert MitigationStatus.PLANNED in statuses
        assert MitigationStatus.IN_PROGRESS in statuses
        assert MitigationStatus.IMPLEMENTED in statuses
        assert MitigationStatus.EFFECTIVE in statuses

    def test_seed_reviews_count(self, svc: RiskManagementService):
        reviews = svc.list_reviews()
        assert len(reviews) == 10

    def test_seed_issues_count(self, svc: RiskManagementService):
        issues = svc.list_issues()
        assert len(issues) == 10

    def test_seed_issues_statuses_present(self, svc: RiskManagementService):
        statuses = {i.status for i in svc.list_issues()}
        assert IssueStatus.OPEN in statuses
        assert IssueStatus.RESOLVED in statuses
        assert IssueStatus.INVESTIGATING in statuses
        assert IssueStatus.ACTION_REQUIRED in statuses

    def test_seed_risk_has_affected_areas(self, svc: RiskManagementService):
        risk = svc.get_risk("RSK-001")
        assert risk is not None
        assert len(risk.affected_areas) > 0

    def test_seed_risk_has_triggers(self, svc: RiskManagementService):
        risk = svc.get_risk("RSK-001")
        assert risk is not None
        assert len(risk.triggers) > 0

    def test_seed_eylea_risks_count(self, svc: RiskManagementService):
        risks = svc.list_risks(trial_id=EYLEA_TRIAL)
        assert len(risks) == 4

    def test_seed_dupixent_risks_count(self, svc: RiskManagementService):
        risks = svc.list_risks(trial_id=DUPIXENT_TRIAL)
        assert len(risks) == 4

    def test_seed_libtayo_risks_count(self, svc: RiskManagementService):
        risks = svc.list_risks(trial_id=LIBTAYO_TRIAL)
        assert len(risks) == 4

    def test_seed_issue_linked_to_risk(self, svc: RiskManagementService):
        issue = svc.get_issue("ISS-001")
        assert issue is not None
        assert issue.risk_id == "RSK-001"

    def test_seed_issue_without_risk(self, svc: RiskManagementService):
        issue = svc.get_issue("ISS-006")
        assert issue is not None
        assert issue.risk_id is None

    def test_seed_critical_risk_exists(self, svc: RiskManagementService):
        risk = svc.get_risk("RSK-009")
        assert risk is not None
        assert risk.risk_level == RiskLevel.CRITICAL


# =====================================================================
# RISK LEVEL COMPUTATION
# =====================================================================


class TestRiskLevelComputation:
    """Test probability x impact -> risk level matrix."""

    def test_rare_negligible_is_low(self):
        assert compute_risk_level(RiskProbability.RARE, RiskImpact.NEGLIGIBLE) == RiskLevel.LOW

    def test_rare_catastrophic_is_high(self):
        assert compute_risk_level(RiskProbability.RARE, RiskImpact.CATASTROPHIC) == RiskLevel.HIGH

    def test_possible_major_is_high(self):
        assert compute_risk_level(RiskProbability.POSSIBLE, RiskImpact.MAJOR) == RiskLevel.HIGH

    def test_possible_catastrophic_is_critical(self):
        assert compute_risk_level(RiskProbability.POSSIBLE, RiskImpact.CATASTROPHIC) == RiskLevel.CRITICAL

    def test_likely_moderate_is_high(self):
        assert compute_risk_level(RiskProbability.LIKELY, RiskImpact.MODERATE) == RiskLevel.HIGH

    def test_almost_certain_major_is_critical(self):
        assert compute_risk_level(RiskProbability.ALMOST_CERTAIN, RiskImpact.MAJOR) == RiskLevel.CRITICAL

    def test_almost_certain_catastrophic_is_critical(self):
        assert compute_risk_level(RiskProbability.ALMOST_CERTAIN, RiskImpact.CATASTROPHIC) == RiskLevel.CRITICAL

    def test_unlikely_minor_is_low(self):
        assert compute_risk_level(RiskProbability.UNLIKELY, RiskImpact.MINOR) == RiskLevel.LOW

    def test_unlikely_moderate_is_medium(self):
        assert compute_risk_level(RiskProbability.UNLIKELY, RiskImpact.MODERATE) == RiskLevel.MEDIUM

    def test_possible_minor_is_medium(self):
        assert compute_risk_level(RiskProbability.POSSIBLE, RiskImpact.MINOR) == RiskLevel.MEDIUM

    def test_likely_negligible_is_low(self):
        assert compute_risk_level(RiskProbability.LIKELY, RiskImpact.NEGLIGIBLE) == RiskLevel.LOW

    def test_almost_certain_negligible_is_medium(self):
        assert compute_risk_level(RiskProbability.ALMOST_CERTAIN, RiskImpact.NEGLIGIBLE) == RiskLevel.MEDIUM


# =====================================================================
# RISK CRUD
# =====================================================================


class TestRiskCrud:
    """Test risk create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_risks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_risks_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_risks_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"category": "safety"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "safety"

    @pytest.mark.anyio
    async def test_list_risks_filter_risk_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"risk_level": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["risk_level"] == "critical"

    @pytest.mark.anyio
    async def test_list_risks_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"status": "mitigating"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "mitigating"

    @pytest.mark.anyio
    async def test_get_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RSK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RSK-001"
        assert data["category"] == "safety"

    @pytest.mark.anyio
    async def test_get_risk_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RSK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_risk(self, client: AsyncClient):
        payload = _make_risk_create()
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_title"] == "Test Risk Title"
        assert data["id"].startswith("RSK-")
        assert data["status"] == "identified"

    @pytest.mark.anyio
    async def test_create_risk_computes_level(self, client: AsyncClient):
        payload = _make_risk_create(probability="almost_certain", impact="catastrophic")
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_level"] == "critical"

    @pytest.mark.anyio
    async def test_create_risk_low_level(self, client: AsyncClient):
        payload = _make_risk_create(probability="rare", impact="negligible")
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_level"] == "low"

    @pytest.mark.anyio
    async def test_update_risk(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RSK-001",
            json={"risk_title": "Updated Risk Title", "status": "monitoring"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_title"] == "Updated Risk Title"
        assert data["status"] == "monitoring"

    @pytest.mark.anyio
    async def test_update_risk_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RSK-NONEXISTENT",
            json={"risk_title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_risk_recomputes_level(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RSK-001",
            json={"probability": "almost_certain", "impact": "catastrophic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "critical"

    @pytest.mark.anyio
    async def test_update_risk_close_sets_closed_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RSK-001",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["closed_date"] is not None

    @pytest.mark.anyio
    async def test_delete_risk(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risks/RSK-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/risks/RSK-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risks/RSK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_risks_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks")
        data = resp.json()
        dates = [item["identified_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_risk_has_all_required_fields(self, svc: RiskManagementService):
        risk = svc.get_risk("RSK-001")
        assert risk is not None
        assert risk.id
        assert risk.trial_id
        assert risk.risk_title
        assert risk.category is not None
        assert risk.description
        assert risk.probability is not None
        assert risk.impact is not None
        assert risk.risk_level is not None
        assert risk.status is not None
        assert risk.identified_by
        assert risk.identified_date is not None
        assert risk.owner
        assert risk.created_at is not None


# =====================================================================
# MITIGATION CRUD
# =====================================================================


class TestMitigationCrud:
    """Test mitigation create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_mitigations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_mitigations_filter_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations", params={"risk_id": "RSK-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["risk_id"] == "RSK-001"

    @pytest.mark.anyio
    async def test_list_mitigations_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations", params={"status": "effective"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "effective"

    @pytest.mark.anyio
    async def test_get_mitigation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations/MIT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MIT-001"
        assert data["risk_id"] == "RSK-001"

    @pytest.mark.anyio
    async def test_get_mitigation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations/MIT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_mitigation(self, client: AsyncClient):
        payload = _make_mitigation_create()
        resp = await client.post(f"{API_PREFIX}/mitigations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action"] == "Test mitigation action"
        assert data["id"].startswith("MIT-")
        assert data["status"] == "planned"

    @pytest.mark.anyio
    async def test_create_mitigation_invalid_risk(self, client: AsyncClient):
        payload = _make_mitigation_create(risk_id="RSK-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/mitigations", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_mitigation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mitigations/MIT-003",
            json={"status": "implemented", "effectiveness_notes": "Working well"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "implemented"
        assert data["effectiveness_notes"] == "Working well"
        assert data["completion_date"] is not None

    @pytest.mark.anyio
    async def test_update_mitigation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mitigations/MIT-NONEXISTENT",
            json={"status": "implemented"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_mitigation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/mitigations/MIT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/mitigations/MIT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_mitigation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/mitigations/MIT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_mitigations_sorted_by_due_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations")
        data = resp.json()
        dates = [item["due_date"] for item in data["items"]]
        assert dates == sorted(dates)

    def test_mitigation_linked_to_risk(self, svc: RiskManagementService):
        mitigation = svc.get_mitigation("MIT-001")
        assert mitigation is not None
        assert mitigation.risk_id == "RSK-001"
        # Verify the risk exists
        risk = svc.get_risk(mitigation.risk_id)
        assert risk is not None

    def test_mitigation_has_cost_estimate(self, svc: RiskManagementService):
        mitigation = svc.get_mitigation("MIT-001")
        assert mitigation is not None
        assert mitigation.cost_estimate is not None
        assert mitigation.cost_estimate > 0

    def test_completed_mitigation_has_completion_date(self, svc: RiskManagementService):
        mitigation = svc.get_mitigation("MIT-001")
        assert mitigation is not None
        assert mitigation.status == MitigationStatus.IMPLEMENTED
        assert mitigation.completion_date is not None

    def test_planned_mitigation_no_completion_date(self, svc: RiskManagementService):
        mitigation = svc.get_mitigation("MIT-005")
        assert mitigation is not None
        assert mitigation.status == MitigationStatus.PLANNED
        assert mitigation.completion_date is None


# =====================================================================
# REVIEW MANAGEMENT
# =====================================================================


class TestReviewManagement:
    """Test risk review operations."""

    @pytest.mark.anyio
    async def test_list_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_reviews_filter_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"risk_id": "RSK-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["risk_id"] == "RSK-001"

    @pytest.mark.anyio
    async def test_get_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/RVW-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RVW-001"
        assert data["risk_id"] == "RSK-001"

    @pytest.mark.anyio
    async def test_get_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/RVW-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_review(self, client: AsyncClient):
        payload = _make_review_create()
        resp = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer"] == "Test Reviewer"
        assert data["id"].startswith("RVW-")

    @pytest.mark.anyio
    async def test_create_review_invalid_risk(self, client: AsyncClient):
        payload = _make_review_create(risk_id="RSK-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_review_updates_risk_last_reviewed(self, client: AsyncClient):
        # Get current last_reviewed
        resp1 = await client.get(f"{API_PREFIX}/risks/RSK-004")
        old_last_reviewed = resp1.json()["last_reviewed"]

        # Create a review for RSK-004 (which had last_reviewed = None)
        payload = _make_review_create(risk_id="RSK-004")
        resp2 = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp2.status_code == 201

        # Verify last_reviewed was updated
        resp3 = await client.get(f"{API_PREFIX}/risks/RSK-004")
        new_last_reviewed = resp3.json()["last_reviewed"]
        assert new_last_reviewed is not None
        assert new_last_reviewed != old_last_reviewed

    @pytest.mark.anyio
    async def test_reviews_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        data = resp.json()
        dates = [item["review_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_review_has_action_items(self, svc: RiskManagementService):
        review = svc.get_review("RVW-001")
        assert review is not None
        assert len(review.action_items) > 0

    def test_review_has_next_review_date(self, svc: RiskManagementService):
        review = svc.get_review("RVW-001")
        assert review is not None
        assert review.next_review_date is not None

    def test_review_linked_to_risk(self, svc: RiskManagementService):
        review = svc.get_review("RVW-001")
        assert review is not None
        risk = svc.get_risk(review.risk_id)
        assert risk is not None


# =====================================================================
# ISSUE CRUD
# =====================================================================


class TestIssueCrud:
    """Test risk issue CRUD operations."""

    @pytest.mark.anyio
    async def test_list_issues(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_issues_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_issues_filter_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues", params={"risk_id": "RSK-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["risk_id"] == "RSK-001"

    @pytest.mark.anyio
    async def test_list_issues_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_issues_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_issues_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues", params={"category": "safety"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "safety"

    @pytest.mark.anyio
    async def test_get_issue(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues/ISS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ISS-001"
        assert data["severity"] == "critical"

    @pytest.mark.anyio
    async def test_get_issue_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues/ISS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_issue(self, client: AsyncClient):
        payload = _make_issue_create()
        resp = await client.post(f"{API_PREFIX}/issues", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Issue Title"
        assert data["id"].startswith("ISS-")
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_create_issue_without_risk(self, client: AsyncClient):
        payload = _make_issue_create(risk_id=None)
        resp = await client.post(f"{API_PREFIX}/issues", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_id"] is None

    @pytest.mark.anyio
    async def test_update_issue(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/issues/ISS-007",
            json={"status": "resolved", "resolution": "Patient recovered."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolution"] == "Patient recovered."
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_update_issue_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/issues/ISS-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_issue_severity(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/issues/ISS-010",
            json={"severity": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "high"

    @pytest.mark.anyio
    async def test_delete_issue(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/issues/ISS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/issues/ISS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_issue_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/issues/ISS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_issues_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues")
        data = resp.json()
        dates = [item["reported_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_resolved_issue_has_resolution(self, svc: RiskManagementService):
        issue = svc.get_issue("ISS-001")
        assert issue is not None
        assert issue.status == IssueStatus.RESOLVED
        assert issue.resolution is not None
        assert issue.resolved_date is not None

    def test_open_issue_no_resolution(self, svc: RiskManagementService):
        issue = svc.get_issue("ISS-007")
        assert issue is not None
        assert issue.status == IssueStatus.OPEN
        assert issue.resolution is None
        assert issue.resolved_date is None


# =====================================================================
# METRICS
# =====================================================================


class TestRiskManagementMetrics:
    """Test risk management metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_risks"] == 12
        assert data["total_mitigations"] == 15
        assert data["total_reviews"] == 10
        assert data["total_issues"] == 10

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_risks"] == 4

    @pytest.mark.anyio
    async def test_metrics_critical_risks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["critical_risks"] >= 1

    @pytest.mark.anyio
    async def test_metrics_overdue_mitigations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overdue_mitigations"] >= 1

    @pytest.mark.anyio
    async def test_metrics_open_risks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_risks"] > 0
        assert data["open_risks"] <= data["total_risks"]

    @pytest.mark.anyio
    async def test_metrics_open_issues(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_issues"] > 0
        assert data["open_issues"] <= data["total_issues"]

    @pytest.mark.anyio
    async def test_metrics_risks_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_category = sum(data["risks_by_category"].values())
        assert total_by_category == data["total_risks"]

    @pytest.mark.anyio
    async def test_metrics_risks_by_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_level = sum(data["risks_by_level"].values())
        assert total_by_level == data["total_risks"]

    @pytest.mark.anyio
    async def test_metrics_risks_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["risks_by_status"].values())
        assert total_by_status == data["total_risks"]

    @pytest.mark.anyio
    async def test_metrics_mitigations_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["mitigations_by_status"].values())
        assert total_by_status == data["total_mitigations"]

    @pytest.mark.anyio
    async def test_metrics_issues_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_severity = sum(data["issues_by_severity"].values())
        assert total_by_severity == data["total_issues"]

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_risks"] == 0
        assert data["total_mitigations"] == 0
        assert data["total_issues"] == 0

    def test_metrics_overdue_calculation(self, svc: RiskManagementService):
        """Verify overdue mitigations are those with due_date < now and not implemented/effective."""
        now = datetime.now(timezone.utc)
        metrics = svc.get_metrics()
        mitigations = svc.list_mitigations()
        expected_overdue = sum(
            1 for m in mitigations
            if m.due_date < now
            and m.status not in (MitigationStatus.IMPLEMENTED, MitigationStatus.EFFECTIVE)
        )
        assert metrics.overdue_mitigations == expected_overdue

    def test_metrics_critical_risk_count(self, svc: RiskManagementService):
        metrics = svc.get_metrics()
        expected_critical = sum(
            1 for r in svc.list_risks() if r.risk_level == RiskLevel.CRITICAL
        )
        assert metrics.critical_risks == expected_critical

    def test_metrics_open_issues_count(self, svc: RiskManagementService):
        metrics = svc.get_metrics()
        expected_open = sum(
            1 for i in svc.list_issues()
            if i.status not in (IssueStatus.RESOLVED, IssueStatus.CLOSED)
        )
        assert metrics.open_issues == expected_open

    def test_metrics_open_risks_count(self, svc: RiskManagementService):
        metrics = svc.get_metrics()
        expected_open = sum(
            1 for r in svc.list_risks() if r.status != RiskStatus.CLOSED
        )
        assert metrics.open_risks == expected_open


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_risk_management_service()
        svc2 = get_risk_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_risk_management_service()
        svc2 = reset_risk_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_risk_management_service()
        svc.delete_risk("RSK-001")
        assert svc.get_risk("RSK-001") is None
        svc2 = reset_risk_management_service()
        assert svc2.get_risk("RSK-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_risks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_mitigations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reviews_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_issues_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_risk_all_categories(self, client: AsyncClient):
        for cat in ["safety", "quality", "operational", "regulatory", "financial", "reputational", "scientific", "supply"]:
            payload = _make_risk_create(category=cat, risk_title=f"Risk {cat}")
            resp = await client.post(f"{API_PREFIX}/risks", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["category"] == cat

    @pytest.mark.anyio
    async def test_create_risk_all_probability_levels(self, client: AsyncClient):
        for prob in ["rare", "unlikely", "possible", "likely", "almost_certain"]:
            payload = _make_risk_create(probability=prob, risk_title=f"Risk {prob}")
            resp = await client.post(f"{API_PREFIX}/risks", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["probability"] == prob

    @pytest.mark.anyio
    async def test_create_risk_all_impact_levels(self, client: AsyncClient):
        for imp in ["negligible", "minor", "moderate", "major", "catastrophic"]:
            payload = _make_risk_create(impact=imp, risk_title=f"Risk {imp}")
            resp = await client.post(f"{API_PREFIX}/risks", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["impact"] == imp

    @pytest.mark.anyio
    async def test_create_issue_all_severities(self, client: AsyncClient):
        for sev in ["low", "medium", "high", "critical"]:
            payload = _make_issue_create(severity=sev, title=f"Issue {sev}")
            resp = await client.post(f"{API_PREFIX}/issues", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["severity"] == sev

    @pytest.mark.anyio
    async def test_create_risk_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "risk_title": "Minimal Risk",
            "category": "safety",
            "description": "Minimal risk description",
            "probability": "rare",
            "impact": "negligible",
            "risk_level": "low",
            "identified_by": "Test",
            "owner": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["affected_areas"] == []
        assert data["triggers"] == []

    @pytest.mark.anyio
    async def test_create_mitigation_with_cost(self, client: AsyncClient):
        payload = _make_mitigation_create(cost_estimate=999999.99)
        resp = await client.post(f"{API_PREFIX}/mitigations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["cost_estimate"] == 999999.99

    @pytest.mark.anyio
    async def test_create_mitigation_without_cost(self, client: AsyncClient):
        payload = _make_mitigation_create()
        del payload["cost_estimate"]
        resp = await client.post(f"{API_PREFIX}/mitigations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["cost_estimate"] is None

    @pytest.mark.anyio
    async def test_update_issue_assign(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/issues/ISS-007",
            json={"assigned_to": "New Assignee"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_to"] == "New Assignee"

    @pytest.mark.anyio
    async def test_list_risks_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_issues_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_mitigations_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations", params={"risk_id": "RSK-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_reviews_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"risk_id": "RSK-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_risk_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RSK-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "risk_title" in data
        assert "category" in data
        assert "description" in data
        assert "probability" in data
        assert "impact" in data
        assert "risk_level" in data
        assert "status" in data
        assert "identified_by" in data
        assert "identified_date" in data
        assert "owner" in data
        assert "affected_areas" in data
        assert "triggers" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_mitigation_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mitigations/MIT-001")
        data = resp.json()
        assert "id" in data
        assert "risk_id" in data
        assert "action" in data
        assert "responsible_party" in data
        assert "due_date" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_review_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/RVW-001")
        data = resp.json()
        assert "id" in data
        assert "risk_id" in data
        assert "review_date" in data
        assert "reviewer" in data
        assert "current_probability" in data
        assert "current_impact" in data
        assert "current_risk_level" in data
        assert "notes" in data
        assert "action_items" in data

    @pytest.mark.anyio
    async def test_issue_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/issues/ISS-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "title" in data
        assert "description" in data
        assert "category" in data
        assert "severity" in data
        assert "status" in data
        assert "reported_by" in data
        assert "reported_date" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_risks" in data
        assert "risks_by_category" in data
        assert "risks_by_level" in data
        assert "risks_by_status" in data
        assert "open_risks" in data
        assert "critical_risks" in data
        assert "total_mitigations" in data
        assert "mitigations_by_status" in data
        assert "overdue_mitigations" in data
        assert "total_reviews" in data
        assert "total_issues" in data
        assert "open_issues" in data
        assert "issues_by_severity" in data

    def test_risks_with_residual_level(self, svc: RiskManagementService):
        risks = svc.list_risks()
        risks_with_residual = [r for r in risks if r.residual_risk_level is not None]
        assert len(risks_with_residual) > 0
        for r in risks_with_residual:
            assert r.status in (RiskStatus.MITIGATING, RiskStatus.MONITORING)

    def test_risks_without_residual_level(self, svc: RiskManagementService):
        risks = svc.list_risks()
        risks_without_residual = [r for r in risks if r.residual_risk_level is None]
        assert len(risks_without_residual) > 0

    def test_risks_with_last_reviewed(self, svc: RiskManagementService):
        risks = svc.list_risks()
        risks_reviewed = [r for r in risks if r.last_reviewed is not None]
        assert len(risks_reviewed) > 0

    def test_risks_without_last_reviewed(self, svc: RiskManagementService):
        risks = svc.list_risks()
        risks_not_reviewed = [r for r in risks if r.last_reviewed is None]
        assert len(risks_not_reviewed) > 0

    def test_safety_risks_count(self, svc: RiskManagementService):
        risks = svc.list_risks(category=RiskCategory.SAFETY)
        assert len(risks) == 3

    def test_all_risks_have_owner(self, svc: RiskManagementService):
        for r in svc.list_risks():
            assert r.owner

    def test_all_mitigations_have_responsible_party(self, svc: RiskManagementService):
        for m in svc.list_mitigations():
            assert m.responsible_party

    def test_all_issues_have_reporter(self, svc: RiskManagementService):
        for i in svc.list_issues():
            assert i.reported_by

    def test_eylea_issues_count(self, svc: RiskManagementService):
        issues = svc.list_issues(trial_id=EYLEA_TRIAL)
        assert len(issues) == 3

    def test_dupixent_issues_count(self, svc: RiskManagementService):
        issues = svc.list_issues(trial_id=DUPIXENT_TRIAL)
        assert len(issues) == 3

    def test_libtayo_issues_count(self, svc: RiskManagementService):
        issues = svc.list_issues(trial_id=LIBTAYO_TRIAL)
        assert len(issues) == 4

    def test_mitigations_for_rsk001(self, svc: RiskManagementService):
        mitigations = svc.list_mitigations(risk_id="RSK-001")
        assert len(mitigations) == 3

    def test_reviews_for_rsk001(self, svc: RiskManagementService):
        reviews = svc.list_reviews(risk_id="RSK-001")
        assert len(reviews) == 1

    def test_effective_mitigations_have_notes(self, svc: RiskManagementService):
        mitigations = svc.list_mitigations(status=MitigationStatus.EFFECTIVE)
        for m in mitigations:
            assert m.effectiveness_notes is not None
            assert len(m.effectiveness_notes) > 0
