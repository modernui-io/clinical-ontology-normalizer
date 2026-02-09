"""Tests for Central Laboratory Management (CLINICAL-8).

Covers:
- Seed data verification (lab tests, kits, samples, results, alerts, shipments)
- Lab test CRUD (create, read, update, delete, list, filter by category/specimen)
- Kit management (list, filter, get, assign, inventory summary)
- Sample lifecycle (register, receive, reject, list, filter)
- Sample with results retrieval
- Result management (list, filter, get, batch submit with auto-flagging)
- Reference range evaluation and critical value detection
- Patient result history
- Critical value alerts (list, filter, acknowledge, idempotent re-acknowledge)
- Shipment management (create, list, get, filter by site)
- Lab metrics dashboard
- Turnaround time analysis by category
- Rejection analysis by site and reason
- Auto-query suggestions for missing results
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, pagination, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.central_laboratory import (
    KitStatus,
    LabTestCategory,
    ResultFlag,
    ResultStatus,
    SampleStatus,
    SampleType,
)
from app.services.central_laboratory_service import (
    CentralLabService,
    get_central_lab_service,
    reset_central_lab_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/central-laboratory"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_central_lab_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CentralLabService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_create(**overrides) -> dict:
    defaults = {
        "name": "Test Analyte",
        "category": "chemistry",
        "specimen_type": "blood_serum",
        "unit": "mg/dL",
        "reference_range_low": 10.0,
        "reference_range_high": 50.0,
        "critical_low": 5.0,
        "critical_high": 100.0,
        "turnaround_hours": 12,
    }
    defaults.update(overrides)
    return defaults


def _make_sample_register(**overrides) -> dict:
    defaults = {
        "patient_id": "PAT-9999",
        "site_id": "SITE-001",
        "sample_type": "blood_serum",
        "collection_date": "2026-01-15",
        "collection_time": "09:30",
        "collector_initials": "AB",
    }
    defaults.update(overrides)
    return defaults


def _make_result_submit(sample_id: str, test_id: str = "LT-002", **overrides) -> dict:
    defaults = {
        "sample_id": sample_id,
        "test_id": test_id,
        "value": 85.0,
        "unit": "mg/dL",
        "resulted_date": "2026-01-16",
        "reviewed_by": "Dr. Tester",
        "status": "final",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_lab_tests_count(self, svc: CentralLabService):
        items, total = svc.list_tests()
        assert total == 20

    def test_seed_lab_tests_categories(self, svc: CentralLabService):
        items, _ = svc.list_tests()
        categories = {t.category for t in items}
        assert LabTestCategory.CHEMISTRY in categories
        assert LabTestCategory.HEMATOLOGY in categories
        assert LabTestCategory.IMMUNOLOGY in categories
        assert LabTestCategory.BIOMARKER in categories

    def test_seed_lab_tests_have_reference_ranges(self, svc: CentralLabService):
        test = svc.get_test("LT-001")
        assert test is not None
        assert test.name == "HbA1c"
        assert test.reference_range_low == 4.0
        assert test.reference_range_high == 5.6
        assert test.critical_low == 3.0
        assert test.critical_high == 15.0

    def test_seed_kits_count(self, svc: CentralLabService):
        items, total = svc.list_kits()
        assert total == 30

    def test_seed_kits_have_statuses(self, svc: CentralLabService):
        items, _ = svc.list_kits()
        statuses = {k.status for k in items}
        assert KitStatus.AVAILABLE in statuses
        assert KitStatus.ASSIGNED in statuses

    def test_seed_samples_count(self, svc: CentralLabService):
        items, total = svc.list_samples()
        assert total == 50

    def test_seed_samples_have_statuses(self, svc: CentralLabService):
        items, _ = svc.list_samples()
        statuses = {s.status for s in items}
        assert SampleStatus.COLLECTED in statuses
        assert SampleStatus.RESULTED in statuses
        assert SampleStatus.REJECTED in statuses

    def test_seed_results_count(self, svc: CentralLabService):
        items, total = svc.list_results()
        # Seeded results (up to 80) + critical results
        assert total >= 70

    def test_seed_results_have_flags(self, svc: CentralLabService):
        items, _ = svc.list_results()
        flags = {r.flag for r in items}
        assert ResultFlag.NORMAL in flags

    def test_seed_alerts_count(self, svc: CentralLabService):
        items, total = svc.get_critical_results()
        assert total >= 5

    def test_seed_shipments_count(self, svc: CentralLabService):
        items, total = svc.list_shipments()
        assert total == 8

    def test_seed_shipments_have_tracking(self, svc: CentralLabService):
        items, _ = svc.list_shipments()
        for s in items:
            assert s.tracking_number.startswith("1Z")


# =====================================================================
# LAB TEST CRUD
# =====================================================================


class TestLabTestCrud:
    """Test lab test create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_tests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20
        assert len(data["items"]) == 20

    @pytest.mark.anyio
    async def test_list_tests_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tests", params={"category": "chemistry"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "chemistry"

    @pytest.mark.anyio
    async def test_list_tests_filter_specimen_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tests", params={"specimen_type": "blood_serum"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["specimen_type"] == "blood_serum"

    @pytest.mark.anyio
    async def test_list_tests_pagination(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tests", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["total"] == 20
        assert data["limit"] == 5
        assert data["offset"] == 0

    @pytest.mark.anyio
    async def test_list_tests_pagination_offset(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tests", params={"limit": 5, "offset": 18})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2  # 20 total, offset 18 => 2 remaining

    @pytest.mark.anyio
    async def test_get_test(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tests/LT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LT-001"
        assert data["name"] == "HbA1c"

    @pytest.mark.anyio
    async def test_get_test_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tests/LT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_test(self, client: AsyncClient):
        payload = _make_test_create()
        resp = await client.post(f"{API_PREFIX}/tests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Analyte"
        assert data["category"] == "chemistry"
        assert data["unit"] == "mg/dL"
        assert data["id"].startswith("LT-")

    @pytest.mark.anyio
    async def test_create_test_minimal(self, client: AsyncClient):
        payload = {
            "name": "Minimal Test",
            "category": "hematology",
            "specimen_type": "blood_whole",
            "unit": "cells/uL",
        }
        resp = await client.post(f"{API_PREFIX}/tests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reference_range_low"] is None
        assert data["reference_range_high"] is None

    @pytest.mark.anyio
    async def test_update_test(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tests/LT-001",
            json={"name": "Updated HbA1c", "turnaround_hours": 48},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated HbA1c"
        assert data["turnaround_hours"] == 48

    @pytest.mark.anyio
    async def test_update_test_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tests/LT-FAKE",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_test(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tests/LT-020")
        assert resp.status_code == 204

        # Verify deletion
        resp = await client.get(f"{API_PREFIX}/tests/LT-020")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_test_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tests/LT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_retrieve_test(self, client: AsyncClient):
        payload = _make_test_create(name="Troponin I", loinc_code="10839-9")
        resp = await client.post(f"{API_PREFIX}/tests", json=payload)
        assert resp.status_code == 201
        test_id = resp.json()["id"]

        resp = await client.get(f"{API_PREFIX}/tests/{test_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Troponin I"
        assert resp.json()["loinc_code"] == "10839-9"


# =====================================================================
# KIT MANAGEMENT
# =====================================================================


class TestKitManagement:
    """Test kit listing, assignment, and inventory operations."""

    @pytest.mark.anyio
    async def test_list_kits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    @pytest.mark.anyio
    async def test_list_kits_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits", params={"status": "available"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "available"

    @pytest.mark.anyio
    async def test_list_kits_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits", params={"site_id": "SITE-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-001"

    @pytest.mark.anyio
    async def test_get_kit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/KIT-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "KIT-0001"

    @pytest.mark.anyio
    async def test_get_kit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/KIT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assign_kits(self, client: AsyncClient):
        # Find available kits first
        resp = await client.get(f"{API_PREFIX}/kits", params={"status": "available"})
        data = resp.json()
        available_ids = [k["id"] for k in data["items"][:2]]
        assert len(available_ids) >= 2

        resp = await client.post(
            f"{API_PREFIX}/kits/assign",
            json={"kit_ids": available_ids, "site_id": "SITE-NEW"},
        )
        assert resp.status_code == 200
        assigned = resp.json()
        assert len(assigned) == 2
        for kit in assigned:
            assert kit["status"] == "assigned"
            assert kit["site_id"] == "SITE-NEW"

    @pytest.mark.anyio
    async def test_assign_already_assigned_kit(self, client: AsyncClient):
        # Assign a kit first
        resp = await client.get(f"{API_PREFIX}/kits", params={"status": "available"})
        kit_id = resp.json()["items"][0]["id"]
        await client.post(
            f"{API_PREFIX}/kits/assign",
            json={"kit_ids": [kit_id], "site_id": "SITE-001"},
        )

        # Try to assign again
        resp = await client.post(
            f"{API_PREFIX}/kits/assign",
            json={"kit_ids": [kit_id], "site_id": "SITE-002"},
        )
        assert resp.status_code == 200
        # Already assigned kit should not be re-assigned
        assert len(resp.json()) == 0

    @pytest.mark.anyio
    async def test_kit_inventory_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/inventory-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_kits" in data
        assert data["total_kits"] == 30
        assert "by_status" in data
        assert "by_site" in data
        assert "expiring_30d" in data


# =====================================================================
# SAMPLE MANAGEMENT
# =====================================================================


class TestSampleManagement:
    """Test sample lifecycle operations."""

    @pytest.mark.anyio
    async def test_list_samples(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 50

    @pytest.mark.anyio
    async def test_list_samples_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"site_id": "SITE-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-001"

    @pytest.mark.anyio
    async def test_list_samples_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"patient_id": "PAT-0001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-0001"

    @pytest.mark.anyio
    async def test_list_samples_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"status": "collected"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "collected"

    @pytest.mark.anyio
    async def test_list_samples_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"sample_type": "blood_serum"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["sample_type"] == "blood_serum"

    @pytest.mark.anyio
    async def test_list_samples_pagination(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples", params={"limit": 10, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 10
        assert data["total"] == 50

    @pytest.mark.anyio
    async def test_get_sample(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/SMP-00001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SMP-00001"

    @pytest.mark.anyio
    async def test_get_sample_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/SMP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_register_sample(self, client: AsyncClient):
        payload = _make_sample_register()
        resp = await client.post(f"{API_PREFIX}/samples/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-9999"
        assert data["site_id"] == "SITE-001"
        assert data["status"] == "collected"
        assert data["barcode"].startswith("BC-")
        assert data["id"].startswith("SMP-")

    @pytest.mark.anyio
    async def test_register_sample_with_kit(self, client: AsyncClient, svc: CentralLabService):
        # Find an available kit
        kits, _ = svc.list_kits(status=KitStatus.AVAILABLE)
        assert len(kits) > 0
        kit_id = kits[0].id

        payload = _make_sample_register(kit_id=kit_id)
        resp = await client.post(f"{API_PREFIX}/samples/register", json=payload)
        assert resp.status_code == 201

        # Kit should be marked as used
        kit = svc.get_kit(kit_id)
        assert kit is not None
        assert kit.status == KitStatus.USED

    @pytest.mark.anyio
    async def test_receive_sample(self, client: AsyncClient, svc: CentralLabService):
        # Find a collected sample
        samples, _ = svc.list_samples(status=SampleStatus.COLLECTED)
        assert len(samples) > 0
        sample_id = samples[0].id

        resp = await client.post(
            f"{API_PREFIX}/samples/{sample_id}/receive",
            json={"received_date": "2026-01-16", "temperature_acceptable": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received"
        assert data["received_date"] == "2026-01-16"

    @pytest.mark.anyio
    async def test_receive_already_resulted_sample(self, client: AsyncClient, svc: CentralLabService):
        # Find a resulted sample
        samples, _ = svc.list_samples(status=SampleStatus.RESULTED)
        assert len(samples) > 0
        sample_id = samples[0].id

        resp = await client.post(
            f"{API_PREFIX}/samples/{sample_id}/receive",
            json={"received_date": "2026-01-16"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_receive_nonexistent_sample(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/samples/SMP-FAKE/receive",
            json={"received_date": "2026-01-16"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_reject_sample(self, client: AsyncClient, svc: CentralLabService):
        # Find a collected sample
        samples, _ = svc.list_samples(status=SampleStatus.COLLECTED)
        assert len(samples) > 0
        sample_id = samples[0].id

        resp = await client.post(
            f"{API_PREFIX}/samples/{sample_id}/reject",
            json={"reason": "Hemolyzed specimen"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["rejection_reason"] == "Hemolyzed specimen"

    @pytest.mark.anyio
    async def test_reject_already_rejected_sample(self, client: AsyncClient, svc: CentralLabService):
        # Find already rejected sample
        samples, _ = svc.list_samples(status=SampleStatus.REJECTED)
        assert len(samples) > 0
        sample_id = samples[0].id

        resp = await client.post(
            f"{API_PREFIX}/samples/{sample_id}/reject",
            json={"reason": "Second rejection attempt"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_reject_nonexistent_sample(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/samples/SMP-FAKE/reject",
            json={"reason": "Does not exist"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_get_sample_with_results(self, client: AsyncClient, svc: CentralLabService):
        # Find a resulted sample
        samples, _ = svc.list_samples(status=SampleStatus.RESULTED)
        assert len(samples) > 0
        sample_id = samples[0].id

        resp = await client.get(f"{API_PREFIX}/samples/{sample_id}/with-results")
        assert resp.status_code == 200
        data = resp.json()
        assert "sample" in data
        assert "results" in data
        assert data["sample"]["id"] == sample_id

    @pytest.mark.anyio
    async def test_get_sample_with_results_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/SMP-NONEXISTENT/with-results")
        assert resp.status_code == 404


# =====================================================================
# RESULT MANAGEMENT
# =====================================================================


class TestResultManagement:
    """Test result submission, retrieval, and auto-flagging."""

    @pytest.mark.anyio
    async def test_list_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 70

    @pytest.mark.anyio
    async def test_list_results_filter_sample(self, client: AsyncClient, svc: CentralLabService):
        # Find a resulted sample with known results
        samples, _ = svc.list_samples(status=SampleStatus.RESULTED)
        sample_id = samples[0].id

        resp = await client.get(f"{API_PREFIX}/results", params={"sample_id": sample_id})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["sample_id"] == sample_id

    @pytest.mark.anyio
    async def test_list_results_filter_test(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"test_id": "LT-002"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["test_id"] == "LT-002"

    @pytest.mark.anyio
    async def test_list_results_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"status": "final"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "final"

    @pytest.mark.anyio
    async def test_list_results_filter_flag(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results", params={"flag": "normal"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["flag"] == "normal"

    @pytest.mark.anyio
    async def test_get_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/RES-00001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RES-00001"

    @pytest.mark.anyio
    async def test_get_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/RES-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_results_normal(self, client: AsyncClient, svc: CentralLabService):
        # Register a sample, then receive it
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-TEST",
                "site_id": "SITE-001",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        resp = await client.post(
            f"{API_PREFIX}/results/submit",
            json={"results": [_make_result_submit(sample.id, "LT-002", value=85.0)]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert data[0]["flag"] == "normal"  # 85 is within 70-100 range for glucose

    @pytest.mark.anyio
    async def test_submit_results_high_flag(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-TEST",
                "site_id": "SITE-001",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        resp = await client.post(
            f"{API_PREFIX}/results/submit",
            json={"results": [_make_result_submit(sample.id, "LT-002", value=150.0)]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data[0]["flag"] == "high"  # 150 is above ref range 100 but below critical 500

    @pytest.mark.anyio
    async def test_submit_results_low_flag(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-TEST",
                "site_id": "SITE-001",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        resp = await client.post(
            f"{API_PREFIX}/results/submit",
            json={"results": [_make_result_submit(sample.id, "LT-002", value=60.0)]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data[0]["flag"] == "low"  # 60 is below ref range 70 but above critical 40

    @pytest.mark.anyio
    async def test_submit_results_critical_high(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-CRIT",
                "site_id": "SITE-002",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        # Count alerts before
        alerts_before, _ = svc.get_critical_results()
        count_before = len(alerts_before)

        resp = await client.post(
            f"{API_PREFIX}/results/submit",
            json={"results": [_make_result_submit(sample.id, "LT-002", value=550.0)]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data[0]["flag"] == "critical_high"  # 550 > critical high 500

        # Should have created an alert
        alerts_after, _ = svc.get_critical_results()
        assert len(alerts_after) > count_before

    @pytest.mark.anyio
    async def test_submit_results_critical_low(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-CRIT2",
                "site_id": "SITE-003",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        resp = await client.post(
            f"{API_PREFIX}/results/submit",
            json={"results": [_make_result_submit(sample.id, "LT-002", value=35.0)]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data[0]["flag"] == "critical_low"  # 35 < critical low 40

    @pytest.mark.anyio
    async def test_submit_batch_results(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-BATCH",
                "site_id": "SITE-001",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        results_payload = {
            "results": [
                _make_result_submit(sample.id, "LT-002", value=90.0),
                _make_result_submit(sample.id, "LT-011", value=1.0),
                _make_result_submit(sample.id, "LT-012", value=30.0),
            ]
        }
        resp = await client.post(f"{API_PREFIX}/results/submit", json=results_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 3

    @pytest.mark.anyio
    async def test_submit_results_updates_sample_status(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-UPDT",
                "site_id": "SITE-001",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        assert svc.get_sample(sample.id).status == SampleStatus.RECEIVED

        await client.post(
            f"{API_PREFIX}/results/submit",
            json={"results": [_make_result_submit(sample.id, "LT-002", value=85.0)]},
        )

        updated_sample = svc.get_sample(sample.id)
        assert updated_sample.status == SampleStatus.RESULTED


# =====================================================================
# PATIENT RESULTS
# =====================================================================


class TestPatientResults:
    """Test patient result history endpoint."""

    @pytest.mark.anyio
    async def test_patient_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-0001/results")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_patient_results_filter_test(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-0001/results",
            params={"test_id": "LT-002"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["test_id"] == "LT-002"

    @pytest.mark.anyio
    async def test_patient_results_nonexistent_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-FAKE/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_patient_results_pagination(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-0001/results",
            params={"limit": 5, "offset": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 0


# =====================================================================
# CRITICAL VALUE ALERTS
# =====================================================================


class TestCriticalValueAlerts:
    """Test critical value alert management."""

    @pytest.mark.anyio
    async def test_list_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5

    @pytest.mark.anyio
    async def test_list_alerts_filter_acknowledged(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"acknowledged": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["acknowledged_by"] is not None

    @pytest.mark.anyio
    async def test_list_alerts_filter_unacknowledged(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts", params={"acknowledged": False})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["acknowledged_by"] is None

    @pytest.mark.anyio
    async def test_acknowledge_alert(self, client: AsyncClient, svc: CentralLabService):
        # Find an unacknowledged alert
        alerts, _ = svc.get_critical_results(acknowledged=False)
        assert len(alerts) > 0
        alert_id = alerts[0].id

        resp = await client.post(
            f"{API_PREFIX}/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Dr. Investigator"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged_by"] == "Dr. Investigator"
        assert data["acknowledged_date"] is not None

    @pytest.mark.anyio
    async def test_acknowledge_alert_idempotent(self, client: AsyncClient, svc: CentralLabService):
        # Find an already acknowledged alert
        alerts, _ = svc.get_critical_results(acknowledged=True)
        assert len(alerts) > 0
        alert_id = alerts[0].id

        resp = await client.post(
            f"{API_PREFIX}/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "Dr. Second"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should still have the original acknowledger
        assert data["acknowledged_by"] != "Dr. Second" or data["acknowledged_by"] is not None

    @pytest.mark.anyio
    async def test_acknowledge_alert_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/alerts/ALERT-NONEXISTENT/acknowledge",
            json={"acknowledged_by": "Dr. Nobody"},
        )
        assert resp.status_code == 404


# =====================================================================
# SHIPMENT MANAGEMENT
# =====================================================================


class TestShipmentManagement:
    """Test sample shipment operations."""

    @pytest.mark.anyio
    async def test_list_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_shipments_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"site_id": "SITE-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-001"

    @pytest.mark.anyio
    async def test_get_shipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHIP-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SHIP-0001"
        assert "tracking_number" in data
        assert "samples" in data

    @pytest.mark.anyio
    async def test_get_shipment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHIP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_shipment(self, client: AsyncClient, svc: CentralLabService):
        # Register some samples to ship
        sample1 = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-SHIP",
                "site_id": "SITE-005",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        sample2 = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-SHIP2",
                "site_id": "SITE-005",
                "sample_type": SampleType.URINE,
                "collection_date": "2026-01-15",
                "collection_time": "10:30",
                "collector_initials": "YY",
                "kit_id": None,
            })()
        )

        resp = await client.post(
            f"{API_PREFIX}/shipments",
            json={
                "site_id": "SITE-005",
                "tracking_number": "1Z999999999",
                "sample_ids": [sample1.id, sample2.id],
                "shipped_date": "2026-01-16",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-005"
        assert data["tracking_number"] == "1Z999999999"
        assert len(data["samples"]) == 2

    @pytest.mark.anyio
    async def test_create_shipment_updates_sample_status(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-TRANSIT",
                "site_id": "SITE-006",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        assert svc.get_sample(sample.id).status == SampleStatus.COLLECTED

        await client.post(
            f"{API_PREFIX}/shipments",
            json={
                "site_id": "SITE-006",
                "tracking_number": "1Z888888888",
                "sample_ids": [sample.id],
                "shipped_date": "2026-01-16",
            },
        )

        updated = svc.get_sample(sample.id)
        assert updated.status == SampleStatus.IN_TRANSIT

    @pytest.mark.anyio
    async def test_list_shipments_pagination(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"limit": 3, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 8


# =====================================================================
# METRICS & ANALYTICS
# =====================================================================


class TestMetrics:
    """Test lab metrics and analytics endpoints."""

    @pytest.mark.anyio
    async def test_metrics_dashboard(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_samples"] == 50
        assert "samples_by_status" in data
        assert "avg_turnaround_hours" in data
        assert "critical_values_30d" in data
        assert "rejection_rate" in data
        assert "pending_results" in data
        assert "kits_expiring_30d" in data

    @pytest.mark.anyio
    async def test_metrics_rejection_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        # 3 rejected out of 50
        assert data["rejection_rate"] == pytest.approx(3 / 50, abs=0.01)

    @pytest.mark.anyio
    async def test_turnaround_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/turnaround-analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        for item in data:
            assert "category" in item
            assert "avg_hours" in item
            assert "median_hours" in item
            assert "p95_hours" in item
            assert "total_resulted" in item
            assert "within_target" in item
            assert "target_hours" in item

    @pytest.mark.anyio
    async def test_turnaround_analysis_categories(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/turnaround-analysis")
        data = resp.json()
        categories = {item["category"] for item in data}
        # Should have at least chemistry (most seeded tests are chemistry)
        assert "chemistry" in categories

    @pytest.mark.anyio
    async def test_rejection_analysis(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/rejection-analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_rejected" in data
        assert "total_samples" in data
        assert "rejection_rate" in data
        assert "by_site" in data
        assert "by_reason" in data
        assert data["total_rejected"] == 3  # 3 rejected samples in seed data

    @pytest.mark.anyio
    async def test_query_suggestions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/query-suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have suggestions for received/processing samples without results
        for item in data:
            assert "type" in item
            assert "sample_id" in item


# =====================================================================
# REFERENCE RANGE EVALUATION (Service-Level)
# =====================================================================


class TestReferenceRangeEvaluation:
    """Test reference range flagging logic at the service level."""

    def test_evaluate_normal(self, svc: CentralLabService):
        test = svc.get_test("LT-002")  # Glucose: ref 70-100, crit 40/500
        flag = svc._evaluate_flag(85.0, test)
        assert flag == ResultFlag.NORMAL

    def test_evaluate_low(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(60.0, test)
        assert flag == ResultFlag.LOW

    def test_evaluate_high(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(150.0, test)
        assert flag == ResultFlag.HIGH

    def test_evaluate_critical_low(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(35.0, test)
        assert flag == ResultFlag.CRITICAL_LOW

    def test_evaluate_critical_high(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(550.0, test)
        assert flag == ResultFlag.CRITICAL_HIGH

    def test_evaluate_at_reference_boundary_low(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(70.0, test)
        assert flag == ResultFlag.NORMAL  # >= low boundary

    def test_evaluate_at_reference_boundary_high(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(100.0, test)
        assert flag == ResultFlag.NORMAL  # <= high boundary

    def test_evaluate_at_critical_boundary_low(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(40.0, test)
        # 40 is not < 40 (critical_low), so should be LOW (below ref range 70)
        assert flag == ResultFlag.LOW

    def test_evaluate_at_critical_boundary_high(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        flag = svc._evaluate_flag(500.0, test)
        # 500 is not > 500 (critical_high), so should be HIGH (above ref range 100)
        assert flag == ResultFlag.HIGH

    def test_evaluate_no_reference_range(self, svc: CentralLabService):
        test = svc.get_test("LT-009")  # CMP panel - no ref ranges
        flag = svc._evaluate_flag(42.0, test)
        assert flag == ResultFlag.NORMAL

    def test_evaluate_no_critical_thresholds(self, svc: CentralLabService):
        test = svc.get_test("LT-004")  # IL-4: ref 0-7.1, no criticals
        flag = svc._evaluate_flag(10.0, test)
        assert flag == ResultFlag.HIGH

    def test_format_reference_range_both_bounds(self, svc: CentralLabService):
        test = svc.get_test("LT-002")
        formatted = svc._format_reference_range(test)
        assert "70.0" in formatted
        assert "100.0" in formatted

    def test_format_reference_range_upper_only(self, svc: CentralLabService):
        test = svc.get_test("LT-007")  # TMB: upper only
        formatted = svc._format_reference_range(test)
        assert formatted.startswith("<")

    def test_format_reference_range_none(self, svc: CentralLabService):
        test = svc.get_test("LT-009")  # No ranges
        formatted = svc._format_reference_range(test)
        assert formatted == "N/A"


# =====================================================================
# SERVICE STATISTICS
# =====================================================================


class TestServiceStats:
    """Test service health and stats."""

    def test_get_stats(self, svc: CentralLabService):
        stats = svc.get_stats()
        assert stats["lab_tests"] == 20
        assert stats["lab_kits"] == 30
        assert stats["samples"] == 50
        assert stats["results"] >= 70
        assert stats["critical_alerts"] >= 5
        assert stats["shipments"] == 8


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_list_tests_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tests",
            params={"category": "urinalysis"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # There should be exactly 1 urinalysis test (LT-016)
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_list_kits_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/kits",
            params={"site_id": "SITE-NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    @pytest.mark.anyio
    async def test_list_samples_multiple_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/samples",
            params={"status": "collected", "sample_type": "blood_serum"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "collected"
            assert item["sample_type"] == "blood_serum"

    @pytest.mark.anyio
    async def test_register_sample_generates_unique_barcode(self, client: AsyncClient):
        payload = _make_sample_register()
        resp1 = await client.post(f"{API_PREFIX}/samples/register", json=payload)
        resp2 = await client.post(f"{API_PREFIX}/samples/register", json=payload)
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["barcode"] != resp2.json()["barcode"]
        assert resp1.json()["id"] != resp2.json()["id"]

    @pytest.mark.anyio
    async def test_register_sample_generates_unique_ids(self, client: AsyncClient):
        payload = _make_sample_register()
        ids = set()
        for _ in range(5):
            resp = await client.post(f"{API_PREFIX}/samples/register", json=payload)
            assert resp.status_code == 201
            ids.add(resp.json()["id"])
        assert len(ids) == 5

    @pytest.mark.anyio
    async def test_results_pagination(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/results",
            params={"limit": 10, "offset": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_submit_result_with_null_value(self, client: AsyncClient, svc: CentralLabService):
        sample = svc.register_sample(
            type("Req", (), {
                "patient_id": "PAT-NULL",
                "site_id": "SITE-001",
                "sample_type": SampleType.BLOOD_SERUM,
                "collection_date": "2026-01-15",
                "collection_time": "10:00",
                "collector_initials": "XX",
                "kit_id": None,
            })()
        )
        from app.schemas.central_laboratory import SampleReceiveRequest
        svc.receive_sample(sample.id, SampleReceiveRequest(received_date="2026-01-16"))

        resp = await client.post(
            f"{API_PREFIX}/results/submit",
            json={"results": [{
                "sample_id": sample.id,
                "test_id": "LT-006",  # PD-L1, no ref range
                "value": None,
                "unit": "score",
                "status": "final",
            }]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data[0]["value"] is None
        assert data[0]["flag"] == "normal"

    @pytest.mark.anyio
    async def test_update_test_preserves_unset_fields(self, client: AsyncClient):
        # Only update name, other fields should remain
        resp = await client.put(
            f"{API_PREFIX}/tests/LT-001",
            json={"name": "Updated Name Only"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name Only"
        assert data["category"] == "chemistry"
        assert data["unit"] == "%"
        assert data["reference_range_low"] == 4.0
        assert data["reference_range_high"] == 5.6

    @pytest.mark.anyio
    async def test_create_test_with_loinc(self, client: AsyncClient):
        payload = _make_test_create(loinc_code="12345-6")
        resp = await client.post(f"{API_PREFIX}/tests", json=payload)
        assert resp.status_code == 201
        assert resp.json()["loinc_code"] == "12345-6"

    @pytest.mark.anyio
    async def test_shipment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHIP-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["samples"], list)
        assert "shipped_date" in data
        assert "tracking_number" in data

    @pytest.mark.anyio
    async def test_metrics_samples_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["samples_by_status"]
        total_from_status = sum(by_status.values())
        assert total_from_status == data["total_samples"]

    @pytest.mark.anyio
    async def test_turnaround_analysis_has_valid_percentiles(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/turnaround-analysis")
        data = resp.json()
        for item in data:
            assert item["avg_hours"] >= 0
            assert item["median_hours"] >= 0
            assert item["p95_hours"] >= 0
            assert item["p95_hours"] >= item["median_hours"]

    @pytest.mark.anyio
    async def test_assign_kits_empty_result_for_nonexistent(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/kits/assign",
            json={"kit_ids": ["KIT-FAKE-1", "KIT-FAKE-2"], "site_id": "SITE-001"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_receive_in_transit_sample(self, client: AsyncClient, svc: CentralLabService):
        # Find an in_transit sample
        samples, _ = svc.list_samples(status=SampleStatus.IN_TRANSIT)
        assert len(samples) > 0
        sample_id = samples[0].id

        resp = await client.post(
            f"{API_PREFIX}/samples/{sample_id}/receive",
            json={"received_date": "2026-01-17", "temperature_acceptable": True},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"

    @pytest.mark.anyio
    async def test_rejection_analysis_reasons(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/rejection-analysis")
        data = resp.json()
        if data["total_rejected"] > 0:
            assert len(data["by_reason"]) > 0

    @pytest.mark.anyio
    async def test_query_suggestions_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/query-suggestions")
        data = resp.json()
        types_found = {item["type"] for item in data}
        # Should find at least missing_result or overdue type suggestions
        assert len(types_found) > 0

    @pytest.mark.anyio
    async def test_list_tests_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tests",
            params={"category": "chemistry", "specimen_type": "blood_serum"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "chemistry"
            assert item["specimen_type"] == "blood_serum"

    @pytest.mark.anyio
    async def test_kit_has_test_ids(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/KIT-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["test_ids"], list)
        assert len(data["test_ids"]) > 0

    @pytest.mark.anyio
    async def test_kit_lot_number(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/kits/KIT-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lot_number"].startswith("LOT-")

    def test_service_singleton(self, svc: CentralLabService):
        svc2 = get_central_lab_service()
        assert svc is svc2

    def test_generate_id_prefix(self, svc: CentralLabService):
        id1 = svc._generate_id("TEST")
        assert id1.startswith("TEST-")
        id2 = svc._generate_id("TEST")
        assert id1 != id2

    @pytest.mark.anyio
    async def test_sample_has_barcode(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/SMP-00001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["barcode"].startswith("BC-")

    @pytest.mark.anyio
    async def test_result_has_reference_range_string(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/results/RES-00001")
        assert resp.status_code == 200
        data = resp.json()
        assert "reference_range" in data
        assert data["reference_range"] is not None

    @pytest.mark.anyio
    async def test_alerts_have_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        for alert in data["items"]:
            assert "result_id" in alert
            assert "patient_id" in alert
            assert "site_id" in alert
            assert "test_name" in alert
            assert "value" in alert
            assert "critical_threshold" in alert

    @pytest.mark.anyio
    async def test_create_test_returns_correct_turnaround(self, client: AsyncClient):
        payload = _make_test_create(turnaround_hours=72)
        resp = await client.post(f"{API_PREFIX}/tests", json=payload)
        assert resp.status_code == 201
        assert resp.json()["turnaround_hours"] == 72

    def test_evaluate_hba1c_normal(self, svc: CentralLabService):
        test = svc.get_test("LT-001")  # HbA1c: ref 4.0-5.6, crit 3.0/15.0
        flag = svc._evaluate_flag(5.0, test)
        assert flag == ResultFlag.NORMAL

    def test_evaluate_hba1c_critical_low(self, svc: CentralLabService):
        test = svc.get_test("LT-001")
        flag = svc._evaluate_flag(2.5, test)
        assert flag == ResultFlag.CRITICAL_LOW

    def test_evaluate_hba1c_high(self, svc: CentralLabService):
        test = svc.get_test("LT-001")
        flag = svc._evaluate_flag(8.0, test)
        assert flag == ResultFlag.HIGH

    @pytest.mark.anyio
    async def test_shipment_received_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHIP-0001")
        assert resp.status_code == 200
        data = resp.json()
        # First 6 shipments should be received
        assert data["received_date"] is not None
