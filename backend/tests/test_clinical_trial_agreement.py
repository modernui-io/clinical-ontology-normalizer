"""Tests for Clinical Trial Agreement Management (CTA-MGT).

Covers:
- Seed data verification (agreements, negotiations, line items, amendments, milestones)
- Agreement CRUD (create, read, update, delete, list, filter by trial/status/type)
- Negotiation record CRUD (create, read, update, delete, list, filter)
- Budget line item CRUD (create, read, update, delete, list, filter)
- Amendment CRUD (create, read, update, delete, list, filter)
- Contract milestone CRUD (create, read, update, delete, list, filter)
- Metrics computation
- Error handling (404s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_trial_agreement import (
    AgreementStatus,
    AgreementType,
    PaymentTerms,
)
from app.services.clinical_trial_agreement_service import (
    ClinicalTrialAgreementService,
    get_clinical_trial_agreement_service,
    reset_clinical_trial_agreement_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-trial-agreement"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_trial_agreement_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalTrialAgreementService:
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


def _make_agreement_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-999",
        "agreement_type": "clinical_trial_agreement",
        "title": "Test Agreement",
        "contract_manager": "Test Manager",
        "total_budget": 500000.00,
        "currency": "USD",
        "payment_terms": "milestone_based",
    }
    defaults.update(overrides)
    return defaults


def _make_negotiation_create(**overrides) -> dict:
    defaults = {
        "agreement_id": "CTA-001",
        "round_number": 4,
        "issue": "indemnification",
        "sponsor_position": "Standard terms",
        "site_position": "Expanded coverage",
        "negotiated_by": "Test Negotiator",
    }
    defaults.update(overrides)
    return defaults


def _make_line_item_create(**overrides) -> dict:
    defaults = {
        "agreement_id": "CTA-001",
        "category": "Test Category",
        "description": "Test line item",
        "unit_cost": 100.00,
        "quantity": 10,
        "total_cost": 1000.00,
        "currency": "USD",
    }
    defaults.update(overrides)
    return defaults


def _make_amendment_create(**overrides) -> dict:
    defaults = {
        "agreement_id": "CTA-001",
        "amendment_number": 3,
        "title": "Test Amendment",
        "description": "Test amendment description",
        "change_type": "budget_increase",
        "initiated_by": "Test Initiator",
        "budget_impact": 25000.00,
    }
    defaults.update(overrides)
    return defaults


def _make_milestone_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "agreement_id": "CTA-001",
        "milestone_name": "Test Milestone",
        "description": "Test milestone description",
        "payment_amount": 50000.00,
        "due_date": (now + timedelta(days=90)).isoformat(),
        "currency": "USD",
        "evidence_required": "Test evidence",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_agreements_count(self, svc: ClinicalTrialAgreementService):
        agreements = svc.list_agreements()
        assert len(agreements) == 12

    def test_seed_agreements_all_trials(self, svc: ClinicalTrialAgreementService):
        trials = {a.trial_id for a in svc.list_agreements()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_negotiations_count(self, svc: ClinicalTrialAgreementService):
        negotiations = svc.list_negotiations()
        assert len(negotiations) == 15

    def test_seed_line_items_count(self, svc: ClinicalTrialAgreementService):
        items = svc.list_line_items()
        assert len(items) == 18

    def test_seed_amendments_count(self, svc: ClinicalTrialAgreementService):
        amendments = svc.list_amendments()
        assert len(amendments) == 10

    def test_seed_milestones_count(self, svc: ClinicalTrialAgreementService):
        milestones = svc.list_milestones()
        assert len(milestones) == 15

    def test_seed_agreement_types_present(self, svc: ClinicalTrialAgreementService):
        agreements = svc.list_agreements()
        types = {a.agreement_type for a in agreements}
        assert AgreementType.CTA in types
        assert AgreementType.CDA in types
        assert AgreementType.BUDGET in types
        assert AgreementType.MASTER_CTA in types

    def test_seed_agreement_statuses_present(self, svc: ClinicalTrialAgreementService):
        agreements = svc.list_agreements()
        statuses = {a.status for a in agreements}
        assert AgreementStatus.EXECUTED in statuses
        assert AgreementStatus.DRAFT in statuses
        assert AgreementStatus.NEGOTIATION in statuses

    def test_seed_eylea_agreements(self, svc: ClinicalTrialAgreementService):
        agreements = svc.list_agreements(trial_id=EYLEA_TRIAL)
        assert len(agreements) == 4

    def test_seed_dupixent_agreements(self, svc: ClinicalTrialAgreementService):
        agreements = svc.list_agreements(trial_id=DUPIXENT_TRIAL)
        assert len(agreements) == 4

    def test_seed_libtayo_agreements(self, svc: ClinicalTrialAgreementService):
        agreements = svc.list_agreements(trial_id=LIBTAYO_TRIAL)
        assert len(agreements) == 4


# =====================================================================
# AGREEMENT CRUD
# =====================================================================


class TestAgreementCrud:
    """Test agreement create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_agreements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_agreements_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_agreements_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"status": "executed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "executed"

    @pytest.mark.anyio
    async def test_list_agreements_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"agreement_type": "clinical_trial_agreement"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["agreement_type"] == "clinical_trial_agreement"

    @pytest.mark.anyio
    async def test_get_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/CTA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CTA-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_agreement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/CTA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_agreement(self, client: AsyncClient):
        payload = _make_agreement_create()
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Agreement"
        assert data["status"] == "draft"
        assert data["id"].startswith("CTA-")

    @pytest.mark.anyio
    async def test_update_agreement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/CTA-004",
            json={"status": "legal_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "legal_review"

    @pytest.mark.anyio
    async def test_update_agreement_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/CTA-NONEXISTENT",
            json={"status": "draft"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agreement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/CTA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/agreements/CTA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agreement_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/CTA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# NEGOTIATION RECORD CRUD
# =====================================================================


class TestNegotiationCrud:
    """Test negotiation record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_negotiations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_negotiations_filter_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations", params={"agreement_id": "CTA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["agreement_id"] == "CTA-001"

    @pytest.mark.anyio
    async def test_list_negotiations_filter_resolved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations", params={"resolved": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resolved"] is True

    @pytest.mark.anyio
    async def test_get_negotiation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations/NEG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "NEG-001"
        assert data["issue"] == "indemnification"

    @pytest.mark.anyio
    async def test_get_negotiation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations/NEG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_negotiation(self, client: AsyncClient):
        payload = _make_negotiation_create()
        resp = await client.post(f"{API_PREFIX}/negotiations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["agreement_id"] == "CTA-001"
        assert data["id"].startswith("NEG-")

    @pytest.mark.anyio
    async def test_update_negotiation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/negotiations/NEG-006",
            json={"resolved": True, "resolution": "Agreed at $7,800"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert data["resolution"] == "Agreed at $7,800"

    @pytest.mark.anyio
    async def test_update_negotiation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/negotiations/NEG-NONEXISTENT",
            json={"resolved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_negotiation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/negotiations/NEG-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/negotiations/NEG-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_negotiation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/negotiations/NEG-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# BUDGET LINE ITEM CRUD
# =====================================================================


class TestLineItemCrud:
    """Test budget line item CRUD operations."""

    @pytest.mark.anyio
    async def test_list_line_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 18

    @pytest.mark.anyio
    async def test_list_line_items_filter_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items", params={"agreement_id": "CTA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["agreement_id"] == "CTA-001"

    @pytest.mark.anyio
    async def test_list_line_items_filter_approved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items", params={"approved": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["approved"] is False

    @pytest.mark.anyio
    async def test_get_line_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items/BLI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BLI-001"
        assert data["category"] == "Patient Visits"

    @pytest.mark.anyio
    async def test_get_line_item_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items/BLI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_line_item(self, client: AsyncClient):
        payload = _make_line_item_create()
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "Test Category"
        assert data["id"].startswith("BLI-")

    @pytest.mark.anyio
    async def test_update_line_item(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-items/BLI-014",
            json={"approved": True, "approved_by": "Test Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True
        assert data["approved_by"] == "Test Approver"

    @pytest.mark.anyio
    async def test_update_line_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-items/BLI-NONEXISTENT",
            json={"approved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_line_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-items/BLI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/line-items/BLI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_line_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-items/BLI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# AMENDMENT CRUD
# =====================================================================


class TestAmendmentCrud:
    """Test agreement amendment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_amendments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/amendments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_amendments_filter_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/amendments", params={"agreement_id": "CTA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["agreement_id"] == "CTA-001"

    @pytest.mark.anyio
    async def test_list_amendments_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/amendments", params={"status": "executed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "executed"

    @pytest.mark.anyio
    async def test_get_amendment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/amendments/AMD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AMD-001"
        assert data["amendment_number"] == 1

    @pytest.mark.anyio
    async def test_get_amendment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/amendments/AMD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_amendment(self, client: AsyncClient):
        payload = _make_amendment_create()
        resp = await client.post(f"{API_PREFIX}/amendments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Amendment"
        assert data["id"].startswith("AMD-")
        assert data["status"] == "draft"

    @pytest.mark.anyio
    async def test_update_amendment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/amendments/AMD-007",
            json={"status": "executed", "approved_by": "Test Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "executed"
        assert data["approved_by"] == "Test Approver"

    @pytest.mark.anyio
    async def test_update_amendment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/amendments/AMD-NONEXISTENT",
            json={"status": "executed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_amendment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/amendments/AMD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/amendments/AMD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_amendment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/amendments/AMD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MILESTONE CRUD
# =====================================================================


class TestMilestoneCrud:
    """Test contract milestone CRUD operations."""

    @pytest.mark.anyio
    async def test_list_milestones(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_milestones_filter_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones", params={"agreement_id": "CTA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["agreement_id"] == "CTA-001"

    @pytest.mark.anyio
    async def test_list_milestones_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_milestone(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/CMS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CMS-001"
        assert data["milestone_name"] == "Site Initiation Visit"

    @pytest.mark.anyio
    async def test_get_milestone_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/CMS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_milestone(self, client: AsyncClient):
        payload = _make_milestone_create()
        resp = await client.post(f"{API_PREFIX}/milestones", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["milestone_name"] == "Test Milestone"
        assert data["id"].startswith("CMS-")
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_update_milestone(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/CMS-004",
            json={"status": "completed", "verified_by": "Test Verifier"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["verified_by"] == "Test Verifier"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_milestone_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/CMS-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_milestone(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestones/CMS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/milestones/CMS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_milestone_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestones/CMS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test agreement management metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agreements"] == 12
        assert data["executed_agreements"] > 0
        assert data["avg_negotiation_rounds"] > 0
        assert data["total_budget_committed"] > 0
        assert data["total_negotiations"] == 15
        assert data["open_negotiations"] > 0
        assert data["total_line_items"] == 18
        assert data["approved_line_items"] > 0
        assert data["total_amendments"] == 10
        assert data["total_milestones"] == 15
        assert data["completed_milestones"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agreements"] == 4

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agreements"] == 0
        assert data["total_budget_committed"] == 0

    def test_metrics_agreements_by_type(self, svc: ClinicalTrialAgreementService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.agreements_by_type.values())
        assert total_by_type == metrics.total_agreements

    def test_metrics_agreements_by_status(self, svc: ClinicalTrialAgreementService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.agreements_by_status.values())
        assert total_by_status == metrics.total_agreements

    def test_metrics_executed_count(self, svc: ClinicalTrialAgreementService):
        metrics = svc.get_metrics()
        executed = [a for a in svc.list_agreements() if a.status == AgreementStatus.EXECUTED]
        assert metrics.executed_agreements == len(executed)

    def test_metrics_open_negotiations(self, svc: ClinicalTrialAgreementService):
        metrics = svc.get_metrics()
        open_negs = [n for n in svc.list_negotiations() if not n.resolved]
        assert metrics.open_negotiations == len(open_negs)

    def test_metrics_approved_line_items(self, svc: ClinicalTrialAgreementService):
        metrics = svc.get_metrics()
        approved = [li for li in svc.list_line_items() if li.approved]
        assert metrics.approved_line_items == len(approved)

    def test_metrics_completed_milestones(self, svc: ClinicalTrialAgreementService):
        metrics = svc.get_metrics()
        completed = [ms for ms in svc.list_milestones() if ms.status == "completed"]
        assert metrics.completed_milestones == len(completed)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_trial_agreement_service()
        svc2 = get_clinical_trial_agreement_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_trial_agreement_service()
        svc2 = reset_clinical_trial_agreement_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_trial_agreement_service()
        svc.delete_agreement("CTA-001")
        assert svc.get_agreement("CTA-001") is None
        svc2 = reset_clinical_trial_agreement_service()
        assert svc2.get_agreement("CTA-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_agreements_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_negotiations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_line_items_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_amendments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/amendments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_milestones_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones")
        assert resp.status_code == 200

    def test_executed_agreements_have_dates(self, svc: ClinicalTrialAgreementService):
        executed = svc.list_agreements(status=AgreementStatus.EXECUTED)
        for a in executed:
            assert a.executed_date is not None
            assert a.effective_date is not None

    def test_completed_milestones_have_dates(self, svc: ClinicalTrialAgreementService):
        completed = svc.list_milestones(status="completed")
        for ms in completed:
            assert ms.completed_date is not None
            assert ms.verified_by is not None

    def test_pending_milestones_no_completion(self, svc: ClinicalTrialAgreementService):
        pending = svc.list_milestones(status="pending")
        for ms in pending:
            assert ms.completed_date is None

    def test_resolved_negotiations_have_resolution(self, svc: ClinicalTrialAgreementService):
        resolved = svc.list_negotiations(resolved=True)
        for n in resolved:
            assert n.resolution is not None

    def test_unresolved_negotiations_no_resolution(self, svc: ClinicalTrialAgreementService):
        unresolved = svc.list_negotiations(resolved=False)
        for n in unresolved:
            assert n.resolution is None

    @pytest.mark.anyio
    async def test_agreement_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/CTA-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "site_id" in data
        assert "agreement_type" in data
        assert "status" in data
        assert "title" in data
        assert "contract_manager" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_agreements" in data
        assert "agreements_by_type" in data
        assert "agreements_by_status" in data
        assert "executed_agreements" in data
        assert "avg_negotiation_rounds" in data
        assert "total_budget_committed" in data
        assert "total_negotiations" in data
        assert "open_negotiations" in data
        assert "total_line_items" in data
        assert "approved_line_items" in data
        assert "total_amendments" in data
        assert "total_milestones" in data
        assert "completed_milestones" in data
