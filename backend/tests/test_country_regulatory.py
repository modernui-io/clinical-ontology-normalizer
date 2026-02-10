"""Tests for Country-Level Regulatory Requirements (REG-COUNTRY).

Covers:
- Seed data verification (requirements, ethics, licenses, agents, activations)
- Country Requirements CRUD (create, read, update, delete, list, filters)
- Ethics Submissions CRUD (create, read, update, delete, list, filters)
- Import/Export Licenses CRUD (create, read, update, delete, list, filters)
- Local Agents CRUD (create, read, update, delete, list, filters)
- Country Activations CRUD (create, read, update, delete, list, filters)
- Activation checklist tracking (regulatory, ethics, import, agent)
- Country regulatory metrics computation
- Error handling (404s, 400s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.country_regulatory import (
    ActivationStatus,
    AgentRole,
    ApprovalStatus,
    SubmissionType,
)
from app.services.country_regulatory_service import (
    CountryRegulatoryService,
    get_country_regulatory_service,
    reset_country_regulatory_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/country-regulatory"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_country_regulatory_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CountryRegulatoryService:
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


def _make_requirement_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "country": "Spain",
        "country_code": "ES",
        "requirement_type": "regulatory_authority",
        "description": "AEMPS CTA submission for EYLEA HD",
        "regulatory_authority": "AEMPS",
        "submission_deadline": (now + timedelta(days=30)).isoformat(),
        "responsible_person": "Dr. Test Person",
        "documents_required": ["Protocol", "IB"],
    }
    defaults.update(overrides)
    return defaults


def _make_ethics_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "country": "Spain",
        "committee_name": "CEIC Hospital Vall d'Hebron",
        "protocol_version": "3.0",
        "icf_version": "2.0-ES",
        "submitted_by": "Dr. Test Submitter",
    }
    defaults.update(overrides)
    return defaults


def _make_license_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "country": "Spain",
        "license_type": "import",
        "product_name": "EYLEA HD (aflibercept 8mg)",
        "quantity_authorized": 200,
        "responsible_person": "Dr. Test Person",
    }
    defaults.update(overrides)
    return defaults


def _make_agent_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "country": "Spain",
        "agent_name": "Carlos Garcia",
        "organization": "Spanish Regulatory Partners",
        "role": "local_regulatory_agent",
        "contact_email": "c.garcia@spanishreg.es",
        "contact_phone": "+34-91-555-1234",
        "contract_start": now.isoformat(),
        "contract_end": (now + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_activation_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "country": "Spain",
        "country_code": "ES",
        "planned_activation_date": (now + timedelta(days=60)).isoformat(),
        "sites_planned": 5,
        "target_enrollment": 80,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_requirements_count(self, svc: CountryRegulatoryService):
        requirements = svc.list_requirements()
        assert len(requirements) == 12

    def test_seed_requirements_multiple_trials(self, svc: CountryRegulatoryService):
        trials = {r.trial_id for r in svc.list_requirements()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_requirements_multiple_countries(self, svc: CountryRegulatoryService):
        countries = {r.country for r in svc.list_requirements()}
        assert "United States" in countries
        assert "United Kingdom" in countries
        assert "Germany" in countries
        assert "Japan" in countries

    def test_seed_requirements_statuses(self, svc: CountryRegulatoryService):
        statuses = {r.approval_status for r in svc.list_requirements()}
        assert ApprovalStatus.APPROVED in statuses
        assert ApprovalStatus.UNDER_REVIEW in statuses
        assert ApprovalStatus.CONDITIONALLY_APPROVED in statuses

    def test_seed_ethics_count(self, svc: CountryRegulatoryService):
        ethics = svc.list_ethics()
        assert len(ethics) == 10

    def test_seed_ethics_multiple_trials(self, svc: CountryRegulatoryService):
        trials = {e.trial_id for e in svc.list_ethics()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_licenses_count(self, svc: CountryRegulatoryService):
        licenses = svc.list_licenses()
        assert len(licenses) == 10

    def test_seed_licenses_types(self, svc: CountryRegulatoryService):
        types = {lic.license_type for lic in svc.list_licenses()}
        assert "import" in types
        assert "export" in types

    def test_seed_agents_count(self, svc: CountryRegulatoryService):
        agents = svc.list_agents()
        assert len(agents) == 10

    def test_seed_agents_roles(self, svc: CountryRegulatoryService):
        roles = {a.role for a in svc.list_agents()}
        assert AgentRole.LOCAL_REGULATORY_AGENT in roles
        assert AgentRole.LEGAL_REPRESENTATIVE in roles
        assert AgentRole.PHARMACOVIGILANCE_CONTACT in roles
        assert AgentRole.IMPORT_AGENT in roles

    def test_seed_activations_count(self, svc: CountryRegulatoryService):
        activations = svc.list_activations()
        assert len(activations) == 12

    def test_seed_activations_statuses(self, svc: CountryRegulatoryService):
        statuses = {a.status for a in svc.list_activations()}
        assert ActivationStatus.ACTIVATED in statuses
        assert ActivationStatus.IN_PROGRESS in statuses
        assert ActivationStatus.PLANNED in statuses
        assert ActivationStatus.SUSPENDED in statuses

    def test_seed_activated_countries_have_checklist_complete(self, svc: CountryRegulatoryService):
        activated = [a for a in svc.list_activations() if a.status == ActivationStatus.ACTIVATED]
        assert len(activated) > 0
        for a in activated:
            assert a.regulatory_approved is True
            assert a.ethics_approved is True
            assert a.import_license_obtained is True
            assert a.local_agent_assigned is True

    def test_seed_planned_countries_have_checklist_incomplete(self, svc: CountryRegulatoryService):
        planned = [a for a in svc.list_activations() if a.status == ActivationStatus.PLANNED]
        assert len(planned) > 0
        for a in planned:
            assert a.regulatory_approved is False

    def test_seed_requirement_has_documents_required(self, svc: CountryRegulatoryService):
        req = svc.get_requirement("CREQ-001")
        assert req is not None
        assert len(req.documents_required) > 0

    def test_seed_ethics_has_committee_name(self, svc: CountryRegulatoryService):
        eth = svc.get_ethics("ETH-001")
        assert eth is not None
        assert len(eth.committee_name) > 0

    def test_seed_license_has_product_name(self, svc: CountryRegulatoryService):
        lic = svc.get_license("LIC-001")
        assert lic is not None
        assert len(lic.product_name) > 0

    def test_seed_agent_has_contact_email(self, svc: CountryRegulatoryService):
        agent = svc.get_agent("AGT-001")
        assert agent is not None
        assert "@" in agent.contact_email


# =====================================================================
# COUNTRY REQUIREMENTS CRUD
# =====================================================================


class TestRequirementsCrud:
    """Test country requirement CRUD operations."""

    @pytest.mark.anyio
    async def test_list_requirements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_requirements_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_requirements_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements", params={"country": "United States"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "United States"

    @pytest.mark.anyio
    async def test_list_requirements_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements", params={"approval_status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["approval_status"] == "approved"

    @pytest.mark.anyio
    async def test_list_requirements_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements", params={"requirement_type": "regulatory_authority"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["requirement_type"] == "regulatory_authority"

    @pytest.mark.anyio
    async def test_get_requirement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements/CREQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CREQ-001"
        assert data["country"] == "United States"

    @pytest.mark.anyio
    async def test_get_requirement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements/CREQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_requirement(self, client: AsyncClient):
        payload = _make_requirement_create()
        resp = await client.post(f"{API_PREFIX}/requirements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "Spain"
        assert data["id"].startswith("CREQ-")
        assert data["approval_status"] == "not_submitted"

    @pytest.mark.anyio
    async def test_update_requirement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requirements/CREQ-007",
            json={"approval_status": "approved", "approval_reference": "ANVISA-2024-APPROVED"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_status"] == "approved"
        assert data["approval_reference"] == "ANVISA-2024-APPROVED"

    @pytest.mark.anyio
    async def test_update_requirement_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requirements/CREQ-NONEXISTENT",
            json={"approval_status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_requirement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requirements/CREQ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/requirements/CREQ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_requirement_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requirements/CREQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_requirement_conditions(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requirements/CREQ-004",
            json={"conditions": ["Updated condition 1", "Updated condition 2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conditions"]) == 2

    @pytest.mark.anyio
    async def test_list_requirements_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requirements",
            params={"trial_id": EYLEA_TRIAL, "approval_status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["approval_status"] == "approved"


# =====================================================================
# ETHICS SUBMISSIONS CRUD
# =====================================================================


class TestEthicsCrud:
    """Test ethics submission CRUD operations."""

    @pytest.mark.anyio
    async def test_list_ethics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_ethics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_ethics_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics", params={"country": "United States"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "United States"

    @pytest.mark.anyio
    async def test_list_ethics_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics", params={"approval_status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["approval_status"] == "approved"

    @pytest.mark.anyio
    async def test_get_ethics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics/ETH-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ETH-001"
        assert data["country"] == "United States"

    @pytest.mark.anyio
    async def test_get_ethics_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics/ETH-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_ethics(self, client: AsyncClient):
        payload = _make_ethics_create()
        resp = await client.post(f"{API_PREFIX}/ethics", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "Spain"
        assert data["id"].startswith("ETH-")
        assert data["approval_status"] == "submitted"

    @pytest.mark.anyio
    async def test_update_ethics(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ethics/ETH-007",
            json={"approval_status": "approved", "approval_reference": "CEP-USP-2024-APPROVED"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_status"] == "approved"
        assert data["approval_reference"] == "CEP-USP-2024-APPROVED"

    @pytest.mark.anyio
    async def test_update_ethics_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ethics/ETH-NONEXISTENT",
            json={"approval_status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ethics(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ethics/ETH-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/ethics/ETH-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ethics_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ethics/ETH-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_ethics_conditions(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ethics/ETH-004",
            json={"conditions": ["Updated condition"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"] == ["Updated condition"]

    @pytest.mark.anyio
    async def test_update_ethics_expiry(self, client: AsyncClient):
        future = (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/ethics/ETH-001",
            json={"expiry_date": future},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["expiry_date"] is not None

    def test_ethics_has_required_fields(self, svc: CountryRegulatoryService):
        eth = svc.get_ethics("ETH-001")
        assert eth is not None
        assert eth.id
        assert eth.trial_id
        assert eth.country
        assert eth.committee_name
        assert eth.protocol_version
        assert eth.icf_version
        assert eth.submitted_by


# =====================================================================
# IMPORT/EXPORT LICENSES CRUD
# =====================================================================


class TestLicensesCrud:
    """Test import/export license CRUD operations."""

    @pytest.mark.anyio
    async def test_list_licenses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_licenses_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_licenses_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses", params={"country": "United Kingdom"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "United Kingdom"

    @pytest.mark.anyio
    async def test_list_licenses_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses", params={"status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_licenses_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses", params={"license_type": "import"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["license_type"] == "import"

    @pytest.mark.anyio
    async def test_list_licenses_filter_export(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses", params={"license_type": "export"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["license_type"] == "export"

    @pytest.mark.anyio
    async def test_get_license(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses/LIC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LIC-001"
        assert data["country"] == "United Kingdom"

    @pytest.mark.anyio
    async def test_get_license_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses/LIC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_license(self, client: AsyncClient):
        payload = _make_license_create()
        resp = await client.post(f"{API_PREFIX}/licenses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "Spain"
        assert data["id"].startswith("LIC-")
        assert data["status"] == "submitted"

    @pytest.mark.anyio
    async def test_update_license(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/licenses/LIC-005",
            json={"status": "approved", "license_number": "IMP-BR-2024-9999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["license_number"] == "IMP-BR-2024-9999"

    @pytest.mark.anyio
    async def test_update_license_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/licenses/LIC-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_license(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/licenses/LIC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/licenses/LIC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_license_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/licenses/LIC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_license_customs_reference(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/licenses/LIC-005",
            json={"customs_reference": "CUSTOMS-BR-2024-NEW"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["customs_reference"] == "CUSTOMS-BR-2024-NEW"

    def test_license_has_required_fields(self, svc: CountryRegulatoryService):
        lic = svc.get_license("LIC-001")
        assert lic is not None
        assert lic.id
        assert lic.trial_id
        assert lic.country
        assert lic.license_type
        assert lic.product_name
        assert lic.quantity_authorized > 0
        assert lic.responsible_person


# =====================================================================
# LOCAL AGENTS CRUD
# =====================================================================


class TestAgentsCrud:
    """Test local agent CRUD operations."""

    @pytest.mark.anyio
    async def test_list_agents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_agents_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_agents_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents", params={"country": "France"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "France"

    @pytest.mark.anyio
    async def test_list_agents_filter_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents", params={"role": "local_regulatory_agent"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["role"] == "local_regulatory_agent"

    @pytest.mark.anyio
    async def test_list_agents_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["active"] is True

    @pytest.mark.anyio
    async def test_list_agents_filter_inactive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents", params={"active": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["active"] is False

    @pytest.mark.anyio
    async def test_get_agent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents/AGT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AGT-001"
        assert data["country"] == "United Kingdom"

    @pytest.mark.anyio
    async def test_get_agent_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents/AGT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_agent(self, client: AsyncClient):
        payload = _make_agent_create()
        resp = await client.post(f"{API_PREFIX}/agents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_name"] == "Carlos Garcia"
        assert data["id"].startswith("AGT-")
        assert data["active"] is True

    @pytest.mark.anyio
    async def test_update_agent(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agents/AGT-010",
            json={"active": True, "organization": "Updated PV France"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert data["organization"] == "Updated PV France"

    @pytest.mark.anyio
    async def test_update_agent_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agents/AGT-NONEXISTENT",
            json={"active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agent(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agents/AGT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/agents/AGT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agent_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agents/AGT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_agent_contact_email(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agents/AGT-001",
            json={"contact_email": "new.email@test.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["contact_email"] == "new.email@test.com"

    @pytest.mark.anyio
    async def test_update_agent_contact_phone(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agents/AGT-001",
            json={"contact_phone": "+44-20-9999-0000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["contact_phone"] == "+44-20-9999-0000"

    def test_agent_has_required_fields(self, svc: CountryRegulatoryService):
        agent = svc.get_agent("AGT-001")
        assert agent is not None
        assert agent.id
        assert agent.trial_id
        assert agent.country
        assert agent.agent_name
        assert agent.organization
        assert agent.role is not None
        assert agent.contact_email


# =====================================================================
# COUNTRY ACTIVATIONS CRUD
# =====================================================================


class TestActivationsCrud:
    """Test country activation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_activations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_activations_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_activations_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations", params={"country": "United States"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "United States"

    @pytest.mark.anyio
    async def test_list_activations_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations", params={"status": "activated"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "activated"

    @pytest.mark.anyio
    async def test_list_activations_filter_planned(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations", params={"status": "planned"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "planned"

    @pytest.mark.anyio
    async def test_list_activations_filter_suspended(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations", params={"status": "suspended"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "suspended"

    @pytest.mark.anyio
    async def test_get_activation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations/ACT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ACT-001"
        assert data["country"] == "United States"
        assert data["status"] == "activated"

    @pytest.mark.anyio
    async def test_get_activation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations/ACT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_activation(self, client: AsyncClient):
        payload = _make_activation_create()
        resp = await client.post(f"{API_PREFIX}/activations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "Spain"
        assert data["id"].startswith("ACT-")
        assert data["status"] == "planned"
        assert data["regulatory_approved"] is False
        assert data["ethics_approved"] is False
        assert data["import_license_obtained"] is False
        assert data["local_agent_assigned"] is False

    @pytest.mark.anyio
    async def test_update_activation_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-004",
            json={"status": "activated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "activated"

    @pytest.mark.anyio
    async def test_update_activation_checklist(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-007",
            json={
                "regulatory_approved": True,
                "ethics_approved": True,
                "import_license_obtained": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regulatory_approved"] is True
        assert data["ethics_approved"] is True
        assert data["import_license_obtained"] is True

    @pytest.mark.anyio
    async def test_update_activation_enrollment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-001",
            json={"current_enrollment": 200, "sites_activated": 14},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_enrollment"] == 200
        assert data["sites_activated"] == 14

    @pytest.mark.anyio
    async def test_update_activation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-NONEXISTENT",
            json={"status": "activated"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_activation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/activations/ACT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/activations/ACT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_activation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/activations/ACT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_activation_checklist_complete_for_activated(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations", params={"status": "activated"})
        data = resp.json()
        for item in data["items"]:
            assert item["regulatory_approved"] is True
            assert item["ethics_approved"] is True
            assert item["import_license_obtained"] is True
            assert item["local_agent_assigned"] is True

    def test_activation_has_correct_structure(self, svc: CountryRegulatoryService):
        act = svc.get_activation("ACT-001")
        assert act is not None
        assert act.id
        assert act.trial_id
        assert act.country
        assert act.country_code
        assert act.sites_planned >= 0
        assert act.sites_activated >= 0
        assert act.target_enrollment >= 0
        assert act.current_enrollment >= 0

    def test_activated_countries_have_actual_date(self, svc: CountryRegulatoryService):
        activated = [a for a in svc.list_activations() if a.status == ActivationStatus.ACTIVATED]
        for a in activated:
            assert a.actual_activation_date is not None

    def test_planned_countries_no_actual_date(self, svc: CountryRegulatoryService):
        planned = [a for a in svc.list_activations() if a.status == ActivationStatus.PLANNED]
        for a in planned:
            assert a.actual_activation_date is None


# =====================================================================
# ACTIVATION CHECKLIST TRACKING
# =====================================================================


class TestActivationChecklist:
    """Test activation checklist boolean tracking."""

    @pytest.mark.anyio
    async def test_update_regulatory_approved(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-008",
            json={"regulatory_approved": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regulatory_approved"] is True
        assert data["ethics_approved"] is False  # Unchanged

    @pytest.mark.anyio
    async def test_update_ethics_approved(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-008",
            json={"ethics_approved": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ethics_approved"] is True

    @pytest.mark.anyio
    async def test_update_import_license_obtained(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-008",
            json={"import_license_obtained": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["import_license_obtained"] is True

    @pytest.mark.anyio
    async def test_update_local_agent_assigned(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-008",
            json={"local_agent_assigned": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["local_agent_assigned"] is True

    @pytest.mark.anyio
    async def test_update_all_checklist_items(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/activations/ACT-008",
            json={
                "regulatory_approved": True,
                "ethics_approved": True,
                "import_license_obtained": True,
                "local_agent_assigned": True,
                "status": "activated",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regulatory_approved"] is True
        assert data["ethics_approved"] is True
        assert data["import_license_obtained"] is True
        assert data["local_agent_assigned"] is True
        assert data["status"] == "activated"

    def test_in_progress_partial_checklist(self, svc: CountryRegulatoryService):
        act = svc.get_activation("ACT-007")
        assert act is not None
        assert act.status == ActivationStatus.IN_PROGRESS
        # Brazil: only local_agent_assigned is True
        assert act.local_agent_assigned is True
        assert act.regulatory_approved is False


# =====================================================================
# METRICS
# =====================================================================


class TestCountryRegulatoryMetrics:
    """Test country regulatory metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requirements"] == 12
        assert data["total_ethics_submissions"] == 10
        assert data["total_licenses"] == 10
        assert data["total_agents"] == 10
        assert data["total_countries"] == 12

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requirements"] > 0
        assert data["total_ethics_submissions"] > 0

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requirements"] == 0
        assert data["total_ethics_submissions"] == 0
        assert data["total_licenses"] == 0
        assert data["total_agents"] == 0
        assert data["total_countries"] == 0
        assert data["overall_activation_pct"] == 0.0

    def test_metrics_requirements_by_status(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.requirements_by_status.values())
        assert total_by_status == metrics.total_requirements

    def test_metrics_requirements_by_type(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.requirements_by_type.values())
        assert total_by_type == metrics.total_requirements

    def test_metrics_ethics_by_status(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.ethics_by_status.values())
        assert total_by_status == metrics.total_ethics_submissions

    def test_metrics_licenses_by_status(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.licenses_by_status.values())
        assert total_by_status == metrics.total_licenses

    def test_metrics_active_agents(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        assert metrics.active_agents <= metrics.total_agents
        assert metrics.active_agents > 0

    def test_metrics_countries_activated(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        assert metrics.countries_activated <= metrics.total_countries
        assert metrics.countries_activated > 0

    def test_metrics_activation_pct(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.overall_activation_pct <= 100.0
        expected_pct = round(metrics.countries_activated / metrics.total_countries * 100.0, 1)
        assert abs(metrics.overall_activation_pct - expected_pct) < 0.2

    def test_metrics_countries_by_status(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.countries_by_status.values())
        assert total_by_status == metrics.total_countries

    def test_metrics_has_correct_structure(self, svc: CountryRegulatoryService):
        metrics = svc.get_metrics()
        assert isinstance(metrics.requirements_by_status, dict)
        assert isinstance(metrics.requirements_by_type, dict)
        assert isinstance(metrics.ethics_by_status, dict)
        assert isinstance(metrics.licenses_by_status, dict)
        assert isinstance(metrics.countries_by_status, dict)

    @pytest.mark.anyio
    async def test_metrics_structure_via_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_requirements" in data
        assert "requirements_by_status" in data
        assert "requirements_by_type" in data
        assert "total_ethics_submissions" in data
        assert "ethics_by_status" in data
        assert "total_licenses" in data
        assert "licenses_by_status" in data
        assert "total_agents" in data
        assert "active_agents" in data
        assert "total_countries" in data
        assert "countries_activated" in data
        assert "countries_by_status" in data
        assert "overall_activation_pct" in data


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_country_regulatory_service()
        svc2 = get_country_regulatory_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_country_regulatory_service()
        svc2 = reset_country_regulatory_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_country_regulatory_service()
        svc.delete_requirement("CREQ-001")
        assert svc.get_requirement("CREQ-001") is None
        svc2 = reset_country_regulatory_service()
        assert svc2.get_requirement("CREQ-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_requirements_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_ethics_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_licenses_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_agents_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_activations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_filter_returns_all(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_ethics_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics", params={"country": "Nonexistent Country"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_licenses_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses", params={"country": "Nonexistent Country"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_agents_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents", params={"country": "Nonexistent Country"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_activations_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations", params={"country": "Nonexistent Country"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_requirement_with_all_fields(self, client: AsyncClient):
        payload = _make_requirement_create(
            documents_required=["Doc1", "Doc2", "Doc3"],
        )
        resp = await client.post(f"{API_PREFIX}/requirements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["documents_required"]) == 3

    @pytest.mark.anyio
    async def test_create_agent_without_optional_fields(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "trial_id": EYLEA_TRIAL,
            "country": "Italy",
            "agent_name": "Marco Rossi",
            "organization": "Italian Regulatory Services",
            "role": "local_regulatory_agent",
            "contact_email": "m.rossi@italreg.it",
            "contract_start": now.isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/agents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["contact_phone"] is None
        assert data["contract_end"] is None

    @pytest.mark.anyio
    async def test_create_activation_minimal(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "trial_id": EYLEA_TRIAL,
            "country": "Italy",
            "country_code": "IT",
            "planned_activation_date": (now + timedelta(days=90)).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/activations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sites_planned"] == 0
        assert data["target_enrollment"] == 0
        assert data["current_enrollment"] == 0
        assert data["sites_activated"] == 0

    @pytest.mark.anyio
    async def test_create_license_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "country": "Italy",
            "license_type": "import",
            "product_name": "EYLEA HD",
            "quantity_authorized": 100,
            "responsible_person": "Dr. Test",
        }
        resp = await client.post(f"{API_PREFIX}/licenses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["license_number"] is None
        assert data["customs_reference"] is None


# =====================================================================
# ENUMERATION TESTS
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_approval_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements")
        data = resp.json()
        statuses = {item["approval_status"] for item in data["items"]}
        assert "approved" in statuses
        assert "under_review" in statuses
        assert "conditionally_approved" in statuses

    @pytest.mark.anyio
    async def test_all_activation_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "activated" in statuses
        assert "in_progress" in statuses
        assert "planned" in statuses
        assert "suspended" in statuses

    @pytest.mark.anyio
    async def test_all_agent_roles_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents")
        data = resp.json()
        roles = {item["role"] for item in data["items"]}
        assert "local_regulatory_agent" in roles
        assert "legal_representative" in roles
        assert "pharmacovigilance_contact" in roles
        assert "import_agent" in roles

    @pytest.mark.anyio
    async def test_license_types_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses")
        data = resp.json()
        types = {item["license_type"] for item in data["items"]}
        assert "import" in types
        assert "export" in types


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_requirement_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements/CREQ-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "country" in data
        assert "country_code" in data
        assert "requirement_type" in data
        assert "description" in data
        assert "regulatory_authority" in data
        assert "submission_deadline" in data
        assert "approval_status" in data
        assert "documents_required" in data
        assert "responsible_person" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_ethics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ethics/ETH-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "country" in data
        assert "committee_name" in data
        assert "submission_date" in data
        assert "protocol_version" in data
        assert "icf_version" in data
        assert "approval_status" in data
        assert "submitted_by" in data

    @pytest.mark.anyio
    async def test_license_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/licenses/LIC-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "country" in data
        assert "license_type" in data
        assert "product_name" in data
        assert "quantity_authorized" in data
        assert "status" in data
        assert "application_date" in data
        assert "responsible_person" in data

    @pytest.mark.anyio
    async def test_agent_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agents/AGT-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "country" in data
        assert "agent_name" in data
        assert "organization" in data
        assert "role" in data
        assert "contact_email" in data
        assert "contract_start" in data
        assert "active" in data

    @pytest.mark.anyio
    async def test_activation_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/activations/ACT-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "country" in data
        assert "country_code" in data
        assert "status" in data
        assert "planned_activation_date" in data
        assert "regulatory_approved" in data
        assert "ethics_approved" in data
        assert "import_license_obtained" in data
        assert "local_agent_assigned" in data
        assert "sites_planned" in data
        assert "sites_activated" in data
        assert "target_enrollment" in data
        assert "current_enrollment" in data

    def test_approved_requirements_have_approval_date(self, svc: CountryRegulatoryService):
        approved = [r for r in svc.list_requirements() if r.approval_status == ApprovalStatus.APPROVED]
        for r in approved:
            assert r.approval_date is not None
            assert r.approval_reference is not None

    def test_approved_ethics_have_approval_date(self, svc: CountryRegulatoryService):
        approved = [e for e in svc.list_ethics() if e.approval_status == ApprovalStatus.APPROVED]
        for e in approved:
            assert e.approval_date is not None
            assert e.approval_reference is not None

    def test_approved_licenses_have_license_number(self, svc: CountryRegulatoryService):
        approved = [lic for lic in svc.list_licenses() if lic.status == ApprovalStatus.APPROVED]
        for lic in approved:
            assert lic.license_number is not None

    def test_under_review_requirements_no_approval_date(self, svc: CountryRegulatoryService):
        under_review = [r for r in svc.list_requirements() if r.approval_status == ApprovalStatus.UNDER_REVIEW]
        for r in under_review:
            assert r.approval_date is None

    def test_rejected_requirement_exists(self, svc: CountryRegulatoryService):
        rejected = [r for r in svc.list_requirements() if r.approval_status == ApprovalStatus.REJECTED]
        assert len(rejected) >= 1

    def test_rejected_license_exists(self, svc: CountryRegulatoryService):
        rejected = [lic for lic in svc.list_licenses() if lic.status == ApprovalStatus.REJECTED]
        assert len(rejected) >= 1

    def test_inactive_agent_exists(self, svc: CountryRegulatoryService):
        inactive = [a for a in svc.list_agents() if not a.active]
        assert len(inactive) >= 1

    def test_eylea_requirements_count(self, svc: CountryRegulatoryService):
        eylea = svc.list_requirements(trial_id=EYLEA_TRIAL)
        assert len(eylea) >= 4

    def test_dupixent_requirements_count(self, svc: CountryRegulatoryService):
        dupixent = svc.list_requirements(trial_id=DUPIXENT_TRIAL)
        assert len(dupixent) >= 3

    def test_libtayo_requirements_count(self, svc: CountryRegulatoryService):
        libtayo = svc.list_requirements(trial_id=LIBTAYO_TRIAL)
        assert len(libtayo) >= 2

    def test_us_activations_across_trials(self, svc: CountryRegulatoryService):
        us_acts = svc.list_activations(country="United States")
        trials = {a.trial_id for a in us_acts}
        assert len(trials) == 3  # All three trials have US activations

    def test_suspended_activation_details(self, svc: CountryRegulatoryService):
        suspended = [a for a in svc.list_activations() if a.status == ActivationStatus.SUSPENDED]
        assert len(suspended) >= 1
        for a in suspended:
            assert a.actual_activation_date is None
            assert a.sites_activated == 0
            assert a.current_enrollment == 0
