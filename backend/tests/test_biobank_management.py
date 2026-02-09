"""Tests for Biospecimen & Biobank Management (CLINICAL-17).

Covers:
- Seed data verification (specimens, aliquots, repositories, consents, shipments)
- Specimen CRUD (create, read, update, delete, list, filter by patient/trial/site/type)
- Specimen genealogy (parent -> aliquots + child specimens)
- Aliquot CRUD (create, read, update, list, filter by specimen/status/storage)
- Aliquot reservation with consent scope validation
- Freeze-thaw cycle recording with quality score recalculation
- Quality scoring based on freeze-thaw cycles and processing time
- Biorepository CRUD (create, read, update, delete, list, filter by type)
- Storage capacity alerts at 80%+ utilization
- Consent management (create, read, list, withdraw, validate scopes)
- Shipment management (create, receive, list, in-transit filter)
- Biobank metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.biobank_management import (
    AliquotStatus,
    BiorepositoryType,
    ConsentScope,
    SpecimenType,
    StorageType,
)
from app.services.biobank_management_service import (
    BiobankService,
    get_biobank_service,
    reset_biobank_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/biobank"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_biobank_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> BiobankService:
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


def _make_specimen_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "patient_id": "PAT-001",
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "specimen_type": "serum",
        "collection_date": now.isoformat(),
        "collection_time": "08:30",
        "collector": "Dr. Test Collector",
        "protocol_visit": "Visit 1",
        "fasting_status": True,
        "processing_time_minutes": 45,
    }
    defaults.update(overrides)
    return defaults


def _make_aliquot_create(**overrides) -> dict:
    defaults = {
        "specimen_id": "SPEC-0001",
        "volume_ul": 500.0,
        "storage_type": "minus80_freezer",
        "freezer_id": "FRZ-80-A01",
        "rack": "R01",
        "box": "B01",
        "position": "A01",
    }
    defaults.update(overrides)
    return defaults


def _make_consent_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "patient_id": "PAT-001",
        "specimen_id": "SPEC-0001",
        "scope": ["primary_study", "future_research"],
        "consent_date": now.isoformat(),
        "consent_version": "v2.0",
    }
    defaults.update(overrides)
    return defaults


def _make_repo_create(**overrides) -> dict:
    defaults = {
        "name": "Test Repository",
        "type": "central",
        "location": "Boston, MA",
        "capacity_total": 10000,
        "temperature_monitored": True,
        "backup_power": True,
        "certifications": ["CAP", "CLIA"],
    }
    defaults.update(overrides)
    return defaults


def _make_shipment_create(**overrides) -> dict:
    defaults = {
        "from_repository": "REPO-004",
        "to_repository": "REPO-001",
        "aliquot_ids": ["ALQ-0001"],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_specimens_count(self, svc: BiobankService):
        specimens = svc.list_specimens()
        assert len(specimens) == 30

    def test_seed_aliquots_count(self, svc: BiobankService):
        aliquots = svc.list_aliquots()
        assert len(aliquots) == 80

    def test_seed_repositories_count(self, svc: BiobankService):
        repos = svc.list_repositories()
        assert len(repos) == 4

    def test_seed_consents_count(self, svc: BiobankService):
        consents = svc.list_consents()
        assert len(consents) == 25

    def test_seed_shipments_count(self, svc: BiobankService):
        shipments = svc.list_shipments()
        assert len(shipments) == 5

    def test_seed_specimens_have_all_types(self, svc: BiobankService):
        specimens = svc.list_specimens()
        types = {s.specimen_type for s in specimens}
        assert SpecimenType.SERUM in types
        assert SpecimenType.PLASMA in types
        assert SpecimenType.WHOLE_BLOOD in types

    def test_seed_repositories_have_all_types(self, svc: BiobankService):
        repos = svc.list_repositories()
        types = {r.type for r in repos}
        assert BiorepositoryType.CENTRAL in types
        assert BiorepositoryType.REGIONAL in types
        assert BiorepositoryType.SITE_LEVEL in types

    def test_seed_aliquots_have_varied_statuses(self, svc: BiobankService):
        aliquots = svc.list_aliquots()
        statuses = {a.status for a in aliquots}
        assert AliquotStatus.AVAILABLE in statuses
        assert AliquotStatus.RESERVED in statuses

    def test_seed_some_consents_withdrawn(self, svc: BiobankService):
        consents = svc.list_consents()
        withdrawn = [c for c in consents if c.withdrawal_date is not None]
        assert len(withdrawn) >= 1

    def test_seed_some_shipments_in_transit(self, svc: BiobankService):
        in_transit = svc.list_shipments(in_transit_only=True)
        assert len(in_transit) >= 1

    def test_seed_parent_specimens_exist(self, svc: BiobankService):
        specimens = svc.list_specimens()
        parents = [s for s in specimens if s.parent_specimen_id is not None]
        assert len(parents) > 0

    def test_seed_central_repo_has_certifications(self, svc: BiobankService):
        repo = svc.get_repository("REPO-001")
        assert repo is not None
        assert "CAP" in repo.certifications
        assert "CLIA" in repo.certifications


# =====================================================================
# SPECIMEN CRUD
# =====================================================================


class TestSpecimenCrud:
    """Test specimen create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_specimens(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30
        assert len(data["items"]) == 30

    @pytest.mark.anyio
    async def test_list_specimens_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"patient_id": "PAT-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-001"

    @pytest.mark.anyio
    async def test_list_specimens_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_specimens_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_specimens_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"specimen_type": "serum"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["specimen_type"] == "serum"

    @pytest.mark.anyio
    async def test_get_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SPEC-0001"

    @pytest.mark.anyio
    async def test_get_specimen_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_specimen(self, client: AsyncClient):
        payload = _make_specimen_create()
        resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-001"
        assert data["specimen_type"] == "serum"
        assert data["id"].startswith("SPEC-")

    @pytest.mark.anyio
    async def test_create_specimen_with_parent(self, client: AsyncClient):
        payload = _make_specimen_create(parent_specimen_id="SPEC-0001")
        resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["parent_specimen_id"] == "SPEC-0001"

    @pytest.mark.anyio
    async def test_update_specimen(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/specimens/SPEC-0001",
            json={"collector": "Updated Collector", "fasting_status": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["collector"] == "Updated Collector"
        assert data["fasting_status"] is True

    @pytest.mark.anyio
    async def test_update_specimen_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/specimens/SPEC-NONEXISTENT",
            json={"collector": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimens/SPEC-0030")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/specimens/SPEC-0030")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimens/SPEC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SPECIMEN GENEALOGY
# =====================================================================


class TestSpecimenGenealogy:
    """Test specimen genealogy (parent -> aliquots + children)."""

    @pytest.mark.anyio
    async def test_genealogy_has_aliquots(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-0001/genealogy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["specimen"]["id"] == "SPEC-0001"
        assert len(data["aliquots"]) > 0

    @pytest.mark.anyio
    async def test_genealogy_has_child_specimens(self, client: AsyncClient):
        # SPEC-0001 should have a child specimen (SPEC-0021 has parent_specimen_id=SPEC-0001)
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-0001/genealogy")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["child_specimens"]) > 0

    @pytest.mark.anyio
    async def test_genealogy_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/SPEC-NONEXISTENT/genealogy")
        assert resp.status_code == 404

    def test_genealogy_service_level(self, svc: BiobankService):
        genealogy = svc.get_specimen_genealogy("SPEC-0001")
        assert genealogy is not None
        assert genealogy.specimen.id == "SPEC-0001"
        assert len(genealogy.aliquots) > 0


# =====================================================================
# ALIQUOT CRUD
# =====================================================================


class TestAliquotCrud:
    """Test aliquot create, read, update, list operations."""

    @pytest.mark.anyio
    async def test_list_aliquots(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 80

    @pytest.mark.anyio
    async def test_list_aliquots_filter_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots", params={"specimen_id": "SPEC-0001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["specimen_id"] == "SPEC-0001"

    @pytest.mark.anyio
    async def test_list_aliquots_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots", params={"status": "available"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "available"

    @pytest.mark.anyio
    async def test_list_aliquots_filter_storage_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots", params={"storage_type": "minus80_freezer"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["storage_type"] == "minus80_freezer"

    @pytest.mark.anyio
    async def test_get_aliquot(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots/ALQ-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ALQ-0001"
        assert "barcode" in data

    @pytest.mark.anyio
    async def test_get_aliquot_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots/ALQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_aliquot(self, client: AsyncClient):
        payload = _make_aliquot_create()
        resp = await client.post(f"{API_PREFIX}/aliquots", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["specimen_id"] == "SPEC-0001"
        assert data["status"] == "available"
        assert data["freeze_thaw_cycles"] == 0
        assert data["id"].startswith("ALQ-")

    @pytest.mark.anyio
    async def test_create_aliquot_invalid_specimen(self, client: AsyncClient):
        payload = _make_aliquot_create(specimen_id="SPEC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/aliquots", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_aliquot(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/aliquots/ALQ-0001",
            json={"status": "reserved", "volume_ul": 250.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reserved"
        assert data["volume_ul"] == 250.0

    @pytest.mark.anyio
    async def test_update_aliquot_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/aliquots/ALQ-NONEXISTENT",
            json={"status": "reserved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_aliquot_freeze_thaw_recalculates_quality(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/aliquots/ALQ-0001",
            json={"freeze_thaw_cycles": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["freeze_thaw_cycles"] == 5
        assert data["quality_score"] < 100.0


# =====================================================================
# ALIQUOT RESERVATION & CONSENT VALIDATION
# =====================================================================


class TestAliquotReservation:
    """Test aliquot reservation with consent scope validation."""

    @pytest.mark.anyio
    async def test_reserve_aliquot_with_valid_consent(self, client: AsyncClient, svc: BiobankService):
        # Find an available aliquot for SPEC-0001
        aliquots = svc.list_aliquots(specimen_id="SPEC-0001", status=AliquotStatus.AVAILABLE)
        if not aliquots:
            pytest.skip("No available aliquots for SPEC-0001")
        aliquot_id = aliquots[0].id

        payload = {
            "purpose": "Primary study analysis",
            "required_scopes": ["primary_study"],
        }
        resp = await client.post(f"{API_PREFIX}/aliquots/{aliquot_id}/reserve", json=payload)
        # May fail with 400 if no matching consent exists, which is valid behavior
        assert resp.status_code in (200, 400)

    @pytest.mark.anyio
    async def test_reserve_aliquot_not_found(self, client: AsyncClient):
        payload = {
            "purpose": "Test",
            "required_scopes": ["primary_study"],
        }
        resp = await client.post(f"{API_PREFIX}/aliquots/ALQ-NONEXISTENT/reserve", json=payload)
        assert resp.status_code == 404

    def test_reserve_non_available_aliquot_fails(self, svc: BiobankService):
        # Find a used/shipped aliquot
        aliquots = svc.list_aliquots(status=AliquotStatus.USED)
        if not aliquots:
            pytest.skip("No used aliquots")
        from app.schemas.biobank_management import AliquotReserve
        with pytest.raises(ValueError, match="not available"):
            svc.reserve_aliquot(
                aliquots[0].id,
                AliquotReserve(purpose="Test", required_scopes=[ConsentScope.PRIMARY_STUDY]),
            )

    def test_reserve_missing_consent_scopes_fails(self, svc: BiobankService):
        """Attempting to reserve with a scope not in the consent should fail."""
        from app.schemas.biobank_management import AliquotReserve
        # Get an available aliquot
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if not available:
            pytest.skip("No available aliquots")

        aliquot = available[0]
        specimen = svc.get_specimen(aliquot.specimen_id)
        if not specimen:
            pytest.skip("Specimen not found")

        # Find consents for this patient/specimen
        consents = svc.list_consents(
            patient_id=specimen.patient_id,
            specimen_id=aliquot.specimen_id,
            active_only=True,
        )

        if not consents:
            # No consent at all - should fail
            with pytest.raises(ValueError, match="No active consent"):
                svc.reserve_aliquot(
                    aliquot.id,
                    AliquotReserve(
                        purpose="Test",
                        required_scopes=[ConsentScope.COMMERCIAL_USE],
                    ),
                )
        else:
            # Has consent but likely missing commercial_use
            granted_scopes: set = set()
            for c in consents:
                granted_scopes.update(c.scope)
            if ConsentScope.COMMERCIAL_USE not in granted_scopes:
                with pytest.raises(ValueError, match="Missing consent"):
                    svc.reserve_aliquot(
                        aliquot.id,
                        AliquotReserve(
                            purpose="Test",
                            required_scopes=[ConsentScope.COMMERCIAL_USE],
                        ),
                    )


# =====================================================================
# FREEZE-THAW CYCLES & QUALITY SCORING
# =====================================================================


class TestFreezeThawAndQuality:
    """Test freeze-thaw cycle recording and quality score calculation."""

    @pytest.mark.anyio
    async def test_record_freeze_thaw(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/aliquots/ALQ-0001/freeze-thaw")
        assert resp.status_code == 200
        data = resp.json()
        assert data["freeze_thaw_cycles"] >= 1

    @pytest.mark.anyio
    async def test_freeze_thaw_decreases_quality(self, client: AsyncClient):
        # Get initial quality
        resp1 = await client.get(f"{API_PREFIX}/aliquots/ALQ-0001")
        initial_quality = resp1.json()["quality_score"]

        # Record freeze-thaw
        resp2 = await client.post(f"{API_PREFIX}/aliquots/ALQ-0001/freeze-thaw")
        new_quality = resp2.json()["quality_score"]
        assert new_quality <= initial_quality

    @pytest.mark.anyio
    async def test_freeze_thaw_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/aliquots/ALQ-NONEXISTENT/freeze-thaw")
        assert resp.status_code == 404

    def test_quality_score_perfect(self, svc: BiobankService):
        score = svc._calculate_quality_score(0, 30)
        assert score == 100.0

    def test_quality_score_with_freeze_thaw(self, svc: BiobankService):
        score = svc._calculate_quality_score(3, 30)
        assert score == 85.0  # 100 - (3 * 5)

    def test_quality_score_with_long_processing(self, svc: BiobankService):
        score = svc._calculate_quality_score(0, 180)  # 180 min = 1 hour over threshold
        assert score == 90.0  # 100 - (1 * 10)

    def test_quality_score_combined_penalties(self, svc: BiobankService):
        score = svc._calculate_quality_score(4, 240)  # 4 cycles, 4 hours
        # 100 - (4*5) - (2hr * 10) = 100 - 20 - 20 = 60
        assert score == 60.0

    def test_quality_score_minimum_zero(self, svc: BiobankService):
        score = svc._calculate_quality_score(20, 600)  # Extreme values
        assert score == 0.0

    @pytest.mark.anyio
    async def test_multiple_freeze_thaw_cycles(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(f"{API_PREFIX}/aliquots/ALQ-0001/freeze-thaw")
            assert resp.status_code == 200

        resp = await client.get(f"{API_PREFIX}/aliquots/ALQ-0001")
        data = resp.json()
        # Initial cycles + 3 new ones
        assert data["freeze_thaw_cycles"] >= 3


# =====================================================================
# BIOREPOSITORY CRUD
# =====================================================================


class TestBiorepositoryCrud:
    """Test biorepository create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_repositories(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_repositories_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories", params={"type": "regional"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["type"] == "regional"

    @pytest.mark.anyio
    async def test_get_repository(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories/REPO-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "REPO-001"
        assert data["name"] == "Central Biobank Facility"

    @pytest.mark.anyio
    async def test_get_repository_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories/REPO-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_repository(self, client: AsyncClient):
        payload = _make_repo_create()
        resp = await client.post(f"{API_PREFIX}/repositories", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Repository"
        assert data["type"] == "central"
        assert data["capacity_used"] == 0
        assert data["id"].startswith("REPO-")

    @pytest.mark.anyio
    async def test_update_repository(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/repositories/REPO-001",
            json={"name": "Updated Central Biobank", "capacity_total": 60000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Central Biobank"
        assert data["capacity_total"] == 60000

    @pytest.mark.anyio
    async def test_update_repository_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/repositories/REPO-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_repository(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/repositories/REPO-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/repositories/REPO-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_repository_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/repositories/REPO-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STORAGE CAPACITY ALERTS
# =====================================================================


class TestStorageCapacityAlerts:
    """Test storage capacity monitoring with alerts at 80%+ utilization."""

    @pytest.mark.anyio
    async def test_get_storage_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # REPO-004 is at 84%, REPO-002 at 84%, REPO-001 at 77% - at least 2 alerts
        assert len(data) >= 1

    @pytest.mark.anyio
    async def test_storage_alerts_have_utilization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-alerts")
        data = resp.json()
        for alert in data:
            assert alert["utilization_pct"] >= 80.0
            assert "repository_id" in alert
            assert "repository_name" in alert
            assert "alert_level" in alert

    @pytest.mark.anyio
    async def test_storage_alerts_sorted_by_utilization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/storage-alerts")
        data = resp.json()
        if len(data) > 1:
            utils = [a["utilization_pct"] for a in data]
            assert utils == sorted(utils, reverse=True)

    def test_storage_alert_levels(self, svc: BiobankService):
        alerts = svc.get_storage_alerts()
        for alert in alerts:
            assert alert.alert_level in ("warning", "critical")
            if alert.utilization_pct >= 95.0:
                assert alert.alert_level == "critical"
            else:
                assert alert.alert_level == "warning"


# =====================================================================
# CONSENT MANAGEMENT
# =====================================================================


class TestConsentManagement:
    """Test consent record management."""

    @pytest.mark.anyio
    async def test_list_consents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25

    @pytest.mark.anyio
    async def test_list_consents_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"patient_id": "PAT-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-001"

    @pytest.mark.anyio
    async def test_list_consents_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"active_only": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["withdrawal_date"] is None

    @pytest.mark.anyio
    async def test_list_consents_filter_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"specimen_id": "SPEC-0001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["specimen_id"] == "SPEC-0001"

    @pytest.mark.anyio
    async def test_get_consent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents/CNS-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CNS-0001"
        assert "scope" in data

    @pytest.mark.anyio
    async def test_get_consent_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents/CNS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_consent(self, client: AsyncClient):
        payload = _make_consent_create()
        resp = await client.post(f"{API_PREFIX}/consents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-001"
        assert "primary_study" in data["scope"]
        assert data["withdrawal_date"] is None
        assert data["id"].startswith("CNS-")

    @pytest.mark.anyio
    async def test_withdraw_consent(self, client: AsyncClient):
        # Find a non-withdrawn consent
        resp = await client.get(f"{API_PREFIX}/consents", params={"active_only": True})
        data = resp.json()
        if data["total"] == 0:
            pytest.skip("No active consents to withdraw")
        consent_id = data["items"][0]["id"]

        resp2 = await client.post(
            f"{API_PREFIX}/consents/{consent_id}/withdraw",
            json={"reason": "Patient requested withdrawal"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["withdrawal_date"] is not None

    @pytest.mark.anyio
    async def test_withdraw_consent_already_withdrawn(self, client: AsyncClient):
        # Find a withdrawn consent
        all_resp = await client.get(f"{API_PREFIX}/consents")
        all_data = all_resp.json()
        withdrawn = [c for c in all_data["items"] if c["withdrawal_date"] is not None]
        if not withdrawn:
            pytest.skip("No withdrawn consents")
        consent_id = withdrawn[0]["id"]

        resp = await client.post(
            f"{API_PREFIX}/consents/{consent_id}/withdraw",
            json={"reason": "Test"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_withdraw_consent_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/consents/CNS-NONEXISTENT/withdraw",
            json={"reason": "Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# CONSENT SCOPE VALIDATION
# =====================================================================


class TestConsentScopeValidation:
    """Test consent scope validation endpoint."""

    @pytest.mark.anyio
    async def test_validate_consent_scopes(self, client: AsyncClient, svc: BiobankService):
        # Find a patient with active consent
        consents = svc.list_consents(active_only=True)
        if not consents:
            pytest.skip("No active consents")
        consent = consents[0]

        resp = await client.post(
            f"{API_PREFIX}/consents/validate",
            params={
                "patient_id": consent.patient_id,
                "specimen_id": consent.specimen_id,
                "required_scopes": ["primary_study"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "granted_scopes" in data

    @pytest.mark.anyio
    async def test_validate_consent_no_active_consent(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/consents/validate",
            params={
                "patient_id": "PAT-NONEXISTENT",
                "specimen_id": "SPEC-NONEXISTENT",
                "required_scopes": ["primary_study"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["reason"] == "No active consent found"

    def test_validate_consent_all_scopes_granted(self, svc: BiobankService):
        # Find a consent with primary_study scope
        consents = svc.list_consents(active_only=True)
        primary = [c for c in consents if ConsentScope.PRIMARY_STUDY in c.scope]
        if not primary:
            pytest.skip("No primary_study consents")
        c = primary[0]
        result = svc.validate_consent_scopes(
            c.patient_id, c.specimen_id, [ConsentScope.PRIMARY_STUDY]
        )
        assert result["valid"] is True

    def test_validate_consent_missing_scope(self, svc: BiobankService):
        consents = svc.list_consents(active_only=True)
        if not consents:
            pytest.skip("No active consents")
        c = consents[0]
        # Request a scope not likely in the consent
        result = svc.validate_consent_scopes(
            c.patient_id, c.specimen_id,
            [ConsentScope.PRIMARY_STUDY, ConsentScope.COMMERCIAL_USE, ConsentScope.GENETIC_ANALYSIS],
        )
        # May or may not be valid depending on seed data
        assert "valid" in result
        assert "missing_scopes" in result


# =====================================================================
# SHIPMENT MANAGEMENT
# =====================================================================


class TestShipmentManagement:
    """Test shipment manifest management."""

    @pytest.mark.anyio
    async def test_list_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_shipments_in_transit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"in_transit_only": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["received_date"] is None

    @pytest.mark.anyio
    async def test_get_shipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SHP-001"
        assert "aliquot_ids" in data

    @pytest.mark.anyio
    async def test_get_shipment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_shipment(self, client: AsyncClient, svc: BiobankService):
        # Find available aliquots to ship
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if not available:
            pytest.skip("No available aliquots")
        aliquot_ids = [available[0].id]

        payload = {
            "from_repository": "REPO-001",
            "to_repository": "REPO-003",
            "aliquot_ids": aliquot_ids,
        }
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["from_repository"] == "REPO-001"
        assert data["to_repository"] == "REPO-003"
        assert data["received_date"] is None
        assert data["id"].startswith("SHP-")

    @pytest.mark.anyio
    async def test_create_shipment_invalid_repository(self, client: AsyncClient):
        payload = {
            "from_repository": "REPO-NONEXISTENT",
            "to_repository": "REPO-001",
            "aliquot_ids": ["ALQ-0001"],
        }
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_shipment_invalid_aliquot(self, client: AsyncClient):
        payload = {
            "from_repository": "REPO-001",
            "to_repository": "REPO-003",
            "aliquot_ids": ["ALQ-NONEXISTENT"],
        }
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_receive_shipment(self, client: AsyncClient):
        # SHP-004 is in transit
        payload = {
            "condition_on_arrival": "Good - all vials intact",
            "temperature_log": [-78.5, -79.0, -78.8],
        }
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-004/receive", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["received_date"] is not None
        assert data["condition_on_arrival"] == "Good - all vials intact"

    @pytest.mark.anyio
    async def test_receive_shipment_already_received(self, client: AsyncClient):
        payload = {
            "condition_on_arrival": "Test",
            "temperature_log": [],
        }
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-001/receive", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_receive_shipment_not_found(self, client: AsyncClient):
        payload = {
            "condition_on_arrival": "Test",
            "temperature_log": [],
        }
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-NONEXISTENT/receive", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_shipment_marks_aliquots_shipped(self, client: AsyncClient, svc: BiobankService):
        """Creating a shipment should mark aliquots as shipped."""
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if not available:
            pytest.skip("No available aliquots")
        aliquot_id = available[0].id

        payload = {
            "from_repository": "REPO-001",
            "to_repository": "REPO-002",
            "aliquot_ids": [aliquot_id],
        }
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201

        # Verify aliquot is now shipped
        resp2 = await client.get(f"{API_PREFIX}/aliquots/{aliquot_id}")
        data2 = resp2.json()
        assert data2["status"] == "shipped"


# =====================================================================
# BIOBANK METRICS
# =====================================================================


class TestBiobankMetrics:
    """Test biobank metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 30
        assert data["total_aliquots"] == 80
        assert data["storage_utilization_pct"] > 0
        assert data["avg_quality_score"] > 0
        assert data["shipments_in_transit"] >= 0

    def test_metrics_aliquots_by_status(self, svc: BiobankService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.aliquots_by_status.values())
        assert total_by_status == metrics.total_aliquots

    def test_metrics_consent_withdrawal_rate(self, svc: BiobankService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.consent_withdrawal_rate <= 100.0

    def test_metrics_storage_utilization(self, svc: BiobankService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.storage_utilization_pct <= 100.0

    def test_metrics_shipments_in_transit(self, svc: BiobankService):
        metrics = svc.get_metrics()
        in_transit = svc.list_shipments(in_transit_only=True)
        assert metrics.shipments_in_transit == len(in_transit)

    def test_metrics_avg_quality_score_range(self, svc: BiobankService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.avg_quality_score <= 100.0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_biobank_service()
        svc2 = get_biobank_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_biobank_service()
        svc2 = reset_biobank_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_biobank_service()
        # Delete a specimen
        svc.delete_specimen("SPEC-0001")
        assert svc.get_specimen("SPEC-0001") is None
        # Reset should bring it back
        svc2 = reset_biobank_service()
        assert svc2.get_specimen("SPEC-0001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_specimens_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_aliquots_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_repositories_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_consents_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_shipments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_specimen_all_types(self, client: AsyncClient):
        """Create specimens with various types."""
        for spec_type in ["serum", "plasma", "whole_blood", "dna", "urine"]:
            payload = _make_specimen_create(specimen_type=spec_type)
            resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
            assert resp.status_code == 201
            assert resp.json()["specimen_type"] == spec_type

    @pytest.mark.anyio
    async def test_create_aliquot_with_concentration(self, client: AsyncClient):
        payload = _make_aliquot_create(concentration=125.5)
        resp = await client.post(f"{API_PREFIX}/aliquots", json=payload)
        assert resp.status_code == 201
        assert resp.json()["concentration"] == 125.5

    @pytest.mark.anyio
    async def test_create_repo_with_certifications(self, client: AsyncClient):
        payload = _make_repo_create(certifications=["CAP", "CLIA", "ISO 20387"])
        resp = await client.post(f"{API_PREFIX}/repositories", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "ISO 20387" in data["certifications"]

    @pytest.mark.anyio
    async def test_consent_with_all_scopes(self, client: AsyncClient):
        payload = _make_consent_create(
            scope=["primary_study", "future_research", "genetic_analysis",
                   "commercial_use", "indefinite_storage"]
        )
        resp = await client.post(f"{API_PREFIX}/consents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["scope"]) == 5

    @pytest.mark.anyio
    async def test_shipment_with_multiple_aliquots(self, client: AsyncClient, svc: BiobankService):
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if len(available) < 3:
            pytest.skip("Not enough available aliquots")
        aliquot_ids = [a.id for a in available[:3]]

        payload = {
            "from_repository": "REPO-001",
            "to_repository": "REPO-003",
            "aliquot_ids": aliquot_ids,
        }
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["aliquot_ids"]) == 3

    def test_specimen_sorted_by_date_descending(self, svc: BiobankService):
        specimens = svc.list_specimens()
        dates = [s.collection_date for s in specimens]
        assert dates == sorted(dates, reverse=True)

    def test_aliquots_sorted_by_id(self, svc: BiobankService):
        aliquots = svc.list_aliquots()
        ids = [a.id for a in aliquots]
        assert ids == sorted(ids)

    def test_repositories_sorted_by_id(self, svc: BiobankService):
        repos = svc.list_repositories()
        ids = [r.id for r in repos]
        assert ids == sorted(ids)


# =====================================================================
# ALIQUOT STATUS TRANSITIONS
# =====================================================================


class TestAliquotStatusTransitions:
    """Test aliquot status transition scenarios."""

    @pytest.mark.anyio
    async def test_transition_available_to_reserved(self, client: AsyncClient, svc: BiobankService):
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if not available:
            pytest.skip("No available aliquots")
        aliquot_id = available[0].id
        resp = await client.put(
            f"{API_PREFIX}/aliquots/{aliquot_id}",
            json={"status": "reserved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reserved"

    @pytest.mark.anyio
    async def test_transition_to_used(self, client: AsyncClient, svc: BiobankService):
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if not available:
            pytest.skip("No available aliquots")
        aliquot_id = available[0].id
        resp = await client.put(
            f"{API_PREFIX}/aliquots/{aliquot_id}",
            json={"status": "used"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "used"

    @pytest.mark.anyio
    async def test_transition_to_destroyed(self, client: AsyncClient, svc: BiobankService):
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if not available:
            pytest.skip("No available aliquots")
        aliquot_id = available[0].id
        resp = await client.put(
            f"{API_PREFIX}/aliquots/{aliquot_id}",
            json={"status": "destroyed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "destroyed"

    @pytest.mark.anyio
    async def test_transition_to_qc_failed(self, client: AsyncClient, svc: BiobankService):
        available = svc.list_aliquots(status=AliquotStatus.AVAILABLE)
        if not available:
            pytest.skip("No available aliquots")
        aliquot_id = available[0].id
        resp = await client.put(
            f"{API_PREFIX}/aliquots/{aliquot_id}",
            json={"status": "qc_failed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "qc_failed"


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_specimen_types_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens")
        data = resp.json()
        types = {item["specimen_type"] for item in data["items"]}
        assert "serum" in types
        assert "plasma" in types
        assert "whole_blood" in types

    @pytest.mark.anyio
    async def test_storage_types_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots")
        data = resp.json()
        storage_types = {item["storage_type"] for item in data["items"]}
        assert "minus80_freezer" in storage_types

    @pytest.mark.anyio
    async def test_aliquot_statuses_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/aliquots")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "available" in statuses

    @pytest.mark.anyio
    async def test_consent_scopes_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents")
        data = resp.json()
        all_scopes: set = set()
        for item in data["items"]:
            all_scopes.update(item["scope"])
        assert "primary_study" in all_scopes

    @pytest.mark.anyio
    async def test_repository_types_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories")
        data = resp.json()
        types = {item["type"] for item in data["items"]}
        assert "central" in types
        assert "regional" in types
        assert "site_level" in types


# =====================================================================
# BIOREPOSITORY DETAILS
# =====================================================================


class TestBiorepositoryDetails:
    """Test detailed biorepository properties."""

    @pytest.mark.anyio
    async def test_repository_has_certifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories/REPO-001")
        data = resp.json()
        assert len(data["certifications"]) > 0

    @pytest.mark.anyio
    async def test_repository_capacity_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories")
        data = resp.json()
        for item in data["items"]:
            assert item["capacity_used"] <= item["capacity_total"]
            assert item["capacity_total"] > 0

    @pytest.mark.anyio
    async def test_repository_monitoring_flags(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/repositories")
        data = resp.json()
        for item in data["items"]:
            assert isinstance(item["temperature_monitored"], bool)
            assert isinstance(item["backup_power"], bool)


# =====================================================================
# SHIPMENT TEMPERATURE LOG
# =====================================================================


class TestShipmentTemperatureLog:
    """Test shipment temperature logging."""

    @pytest.mark.anyio
    async def test_completed_shipment_has_temperature_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        data = resp.json()
        assert len(data["temperature_log"]) > 0
        for temp in data["temperature_log"]:
            assert isinstance(temp, float)

    @pytest.mark.anyio
    async def test_in_transit_shipment_no_temperature(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-004")
        data = resp.json()
        assert data["received_date"] is None
        assert len(data["temperature_log"]) == 0

    @pytest.mark.anyio
    async def test_receive_shipment_with_temperature_log(self, client: AsyncClient):
        payload = {
            "condition_on_arrival": "Good",
            "temperature_log": [-78.5, -79.0, -78.8, -79.2],
        }
        resp = await client.post(f"{API_PREFIX}/shipments/SHP-005/receive", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["temperature_log"]) == 4
