"""Tests for CDISC Standards Management (CDISC-STD).

Covers:
- Seed data verification (SDTM domains, ADaM datasets, controlled terms, define XMLs, conformance results)
- SDTM Domain CRUD (create, read, update, delete, list, filter by trial)
- ADaM Dataset CRUD (create, read, update, delete, list, filter by trial)
- Controlled Term CRUD (create, read, delete, list, filter by trial)
- Define XML CRUD (create, read, update, delete, list, filter by trial)
- Conformance Result CRUD (create, read, update, delete, list, filter by trial)
- Metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.cdisc_standards_service import (
    CDISCStandardsService,
    get_cdisc_standards_service,
    reset_cdisc_standards_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/cdisc-standards"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_cdisc_standards_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CDISCStandardsService:
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


def _make_sdtm_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "domain_code": "MH",
        "domain_name": "Medical History",
        "domain_class": "events",
        "sdtm_version": "3.4",
        "description": "Medical history domain for test",
        "key_variables": ["STUDYID", "USUBJID", "MHSEQ"],
        "programmer": "Test Programmer",
    }
    defaults.update(overrides)
    return defaults


def _make_adam_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "dataset_name": "ADCM",
        "dataset_label": "Concomitant Medication Analysis Dataset",
        "adam_version": "1.3",
        "source_domains": ["CM", "ADSL"],
        "programmer": "Test Programmer",
        "analysis_purpose": "Concomitant medication analysis",
    }
    defaults.update(overrides)
    return defaults


def _make_ct_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "codelist_code": "TEST_CL",
        "codelist_name": "Test Codelist",
        "term_code": "TEST_001",
        "term_value": "TEST",
        "decoded_value": "Test Value",
        "ct_version": "2024-03-29",
        "standard": "sdtm",
        "extensible": True,
    }
    defaults.update(overrides)
    return defaults


def _make_define_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "standard": "sdtm",
        "version": "2.1.0",
        "file_name": "define-test.xml",
        "author": "Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_conformance_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "standard": "sdtm",
        "validation_tool": "Pinnacle 21 Enterprise",
        "dataset_name": "DM",
        "rule_id": "SD9999",
        "severity": "error",
        "message": "Test validation error",
        "variable": "TESTVAR",
        "record_count": 5,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_sdtm_domains_count(self, svc: CDISCStandardsService):
        domains = svc.list_sdtm_domains()
        assert len(domains) == 12

    def test_seed_adam_datasets_count(self, svc: CDISCStandardsService):
        datasets = svc.list_adam_datasets()
        assert len(datasets) == 10

    def test_seed_controlled_terms_count(self, svc: CDISCStandardsService):
        terms = svc.list_controlled_terms()
        assert len(terms) == 12

    def test_seed_define_xmls_count(self, svc: CDISCStandardsService):
        defines = svc.list_define_xmls()
        assert len(defines) == 10

    def test_seed_conformance_results_count(self, svc: CDISCStandardsService):
        results = svc.list_conformance_results()
        assert len(results) == 15

    def test_seed_sdtm_domains_per_trial(self, svc: CDISCStandardsService):
        eylea = svc.list_sdtm_domains(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_sdtm_domains(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_sdtm_domains(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_adam_datasets_per_trial(self, svc: CDISCStandardsService):
        eylea = svc.list_adam_datasets(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_adam_datasets(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_adam_datasets(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 3
        assert len(libtayo) == 3

    def test_seed_conformance_results_per_trial(self, svc: CDISCStandardsService):
        eylea = svc.list_conformance_results(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_conformance_results(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_conformance_results(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 5
        assert len(dupixent) == 5
        assert len(libtayo) == 5


# =====================================================================
# SDTM DOMAIN CRUD
# =====================================================================


class TestSDTMDomainCrud:
    """Test SDTM domain create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_sdtm_domains(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdtm-domains")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_sdtm_domains_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdtm-domains", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_sdtm_domain(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdtm-domains/SDTM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDTM-001"
        assert data["domain_code"] == "DM"

    @pytest.mark.anyio
    async def test_get_sdtm_domain_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdtm-domains/SDTM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sdtm_domain(self, client: AsyncClient):
        payload = _make_sdtm_create()
        resp = await client.post(f"{API_PREFIX}/sdtm-domains", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["domain_code"] == "MH"
        assert data["id"].startswith("SDTM-")

    @pytest.mark.anyio
    async def test_update_sdtm_domain(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdtm-domains/SDTM-003",
            json={"status": "validated", "mapped_variables": 40, "reviewer": "Jane Doe"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "validated"
        assert data["mapped_variables"] == 40
        assert data["reviewer"] == "Jane Doe"

    @pytest.mark.anyio
    async def test_update_sdtm_domain_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sdtm-domains/SDTM-NONEXISTENT",
            json={"status": "validated"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdtm_domain(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sdtm-domains/SDTM-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sdtm-domains/SDTM-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sdtm_domain_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sdtm-domains/SDTM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ADAM DATASET CRUD
# =====================================================================


class TestADaMDatasetCrud:
    """Test ADaM dataset create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_adam_datasets(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adam-datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_adam_datasets_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adam-datasets", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_adam_dataset(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adam-datasets/ADAM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ADAM-001"
        assert data["dataset_name"] == "ADSL"

    @pytest.mark.anyio
    async def test_get_adam_dataset_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adam-datasets/ADAM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adam_dataset(self, client: AsyncClient):
        payload = _make_adam_create()
        resp = await client.post(f"{API_PREFIX}/adam-datasets", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["dataset_name"] == "ADCM"
        assert data["id"].startswith("ADAM-")

    @pytest.mark.anyio
    async def test_update_adam_dataset(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adam-datasets/ADAM-003",
            json={"status": "validated", "derived_variables": 30, "reviewer": "Jane Doe"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "validated"
        assert data["derived_variables"] == 30

    @pytest.mark.anyio
    async def test_update_adam_dataset_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adam-datasets/ADAM-NONEXISTENT",
            json={"status": "validated"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adam_dataset(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adam-datasets/ADAM-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/adam-datasets/ADAM-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adam_dataset_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adam-datasets/ADAM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CONTROLLED TERM CRUD
# =====================================================================


class TestControlledTermCrud:
    """Test controlled term create, read, delete operations."""

    @pytest.mark.anyio
    async def test_list_controlled_terms(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/controlled-terms")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_controlled_terms_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/controlled-terms", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_controlled_term(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/controlled-terms/CT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CT-001"
        assert data["term_value"] == "F"

    @pytest.mark.anyio
    async def test_get_controlled_term_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/controlled-terms/CT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_controlled_term(self, client: AsyncClient):
        payload = _make_ct_create()
        resp = await client.post(f"{API_PREFIX}/controlled-terms", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["term_value"] == "TEST"
        assert data["id"].startswith("CT-")

    @pytest.mark.anyio
    async def test_delete_controlled_term(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/controlled-terms/CT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/controlled-terms/CT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_controlled_term_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/controlled-terms/CT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DEFINE XML CRUD
# =====================================================================


class TestDefineXMLCrud:
    """Test Define XML create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_define_xmls(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/define-xmls")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_define_xmls_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/define-xmls", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_define_xml(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/define-xmls/DEF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEF-001"
        assert data["status"] == "final"

    @pytest.mark.anyio
    async def test_get_define_xml_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/define-xmls/DEF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_define_xml(self, client: AsyncClient):
        payload = _make_define_create()
        resp = await client.post(f"{API_PREFIX}/define-xmls", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["file_name"] == "define-test.xml"
        assert data["id"].startswith("DEF-")

    @pytest.mark.anyio
    async def test_update_define_xml(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/define-xmls/DEF-002",
            json={"status": "final", "validated": True, "validation_errors": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "final"
        assert data["validated"] is True
        assert data["validation_errors"] == 0

    @pytest.mark.anyio
    async def test_update_define_xml_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/define-xmls/DEF-NONEXISTENT",
            json={"status": "final"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_define_xml(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/define-xmls/DEF-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/define-xmls/DEF-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_define_xml_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/define-xmls/DEF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CONFORMANCE RESULT CRUD
# =====================================================================


class TestConformanceResultCrud:
    """Test conformance result create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_conformance_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conformance-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_conformance_results_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conformance-results", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_conformance_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conformance-results/CFR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CFR-001"
        assert data["rule_id"] == "SD0020"

    @pytest.mark.anyio
    async def test_get_conformance_result_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conformance-results/CFR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_conformance_result(self, client: AsyncClient):
        payload = _make_conformance_create()
        resp = await client.post(f"{API_PREFIX}/conformance-results", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_id"] == "SD9999"
        assert data["id"].startswith("CFR-")

    @pytest.mark.anyio
    async def test_update_conformance_result(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/conformance-results/CFR-002",
            json={"status": "resolved", "resolution": "Fixed data", "resolved_by": "John Smith"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolution"] == "Fixed data"
        assert data["resolved_by"] == "John Smith"

    @pytest.mark.anyio
    async def test_update_conformance_result_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/conformance-results/CFR-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_conformance_result(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/conformance-results/CFR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/conformance-results/CFR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_conformance_result_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/conformance-results/CFR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestCDISCMetrics:
    """Test CDISC metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sdtm_domains"] == 12
        assert data["total_adam_datasets"] == 10
        assert data["total_controlled_terms"] == 12
        assert data["total_define_xmls"] == 10
        assert data["total_conformance_results"] == 15
        assert 0.0 <= data["sdtm_mapping_pct"] <= 100.0
        assert data["open_errors"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sdtm_domains"] == 4
        assert data["total_adam_datasets"] == 4
        assert data["total_conformance_results"] == 5

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sdtm_domains"] == 0
        assert data["total_adam_datasets"] == 0
        assert data["sdtm_mapping_pct"] == 0.0

    def test_metrics_domains_by_class(self, svc: CDISCStandardsService):
        metrics = svc.get_metrics()
        total_by_class = sum(metrics.domains_by_class.values())
        assert total_by_class == metrics.total_sdtm_domains

    def test_metrics_domains_by_status(self, svc: CDISCStandardsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.domains_by_status.values())
        assert total_by_status == metrics.total_sdtm_domains

    def test_metrics_adam_by_status(self, svc: CDISCStandardsService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.adam_by_status.values())
        assert total_by_status == metrics.total_adam_datasets

    def test_metrics_results_by_severity(self, svc: CDISCStandardsService):
        metrics = svc.get_metrics()
        total_by_severity = sum(metrics.results_by_severity.values())
        assert total_by_severity == metrics.total_conformance_results

    def test_metrics_custom_terms(self, svc: CDISCStandardsService):
        metrics = svc.get_metrics()
        custom = [t for t in svc.list_controlled_terms() if t.custom]
        assert metrics.custom_terms == len(custom)

    def test_metrics_validated_defines(self, svc: CDISCStandardsService):
        metrics = svc.get_metrics()
        validated = [d for d in svc.list_define_xmls() if d.validated]
        assert metrics.validated_define_xmls == len(validated)

    def test_metrics_open_errors(self, svc: CDISCStandardsService):
        metrics = svc.get_metrics()
        from app.schemas.cdisc_standards import ValidationSeverity
        open_errors = [
            r for r in svc.list_conformance_results()
            if r.severity == ValidationSeverity.ERROR and r.status == "open"
        ]
        assert metrics.open_errors == len(open_errors)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_cdisc_standards_service()
        svc2 = get_cdisc_standards_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_cdisc_standards_service()
        svc2 = reset_cdisc_standards_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_cdisc_standards_service()
        svc.delete_sdtm_domain("SDTM-001")
        assert svc.get_sdtm_domain("SDTM-001") is None
        svc2 = reset_cdisc_standards_service()
        assert svc2.get_sdtm_domain("SDTM-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_sdtm_domains_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdtm-domains")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_adam_datasets_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adam-datasets")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_controlled_terms_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/controlled-terms")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_define_xmls_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/define-xmls")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_conformance_results_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conformance-results")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_sdtm_domain_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdtm-domains/SDTM-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "domain_code" in data
        assert "domain_name" in data
        assert "domain_class" in data
        assert "sdtm_version" in data
        assert "key_variables" in data
        assert "total_variables" in data
        assert "mapped_variables" in data
        assert "status" in data
        assert "programmer" in data

    @pytest.mark.anyio
    async def test_adam_dataset_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adam-datasets/ADAM-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "dataset_name" in data
        assert "dataset_label" in data
        assert "adam_version" in data
        assert "source_domains" in data
        assert "total_variables" in data
        assert "derived_variables" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_conformance_result_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conformance-results/CFR-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "standard" in data
        assert "validation_tool" in data
        assert "dataset_name" in data
        assert "rule_id" in data
        assert "severity" in data
        assert "message" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_sdtm_domains" in data
        assert "domains_by_class" in data
        assert "domains_by_status" in data
        assert "sdtm_mapping_pct" in data
        assert "total_adam_datasets" in data
        assert "adam_by_status" in data
        assert "total_controlled_terms" in data
        assert "custom_terms" in data
        assert "total_define_xmls" in data
        assert "validated_define_xmls" in data
        assert "total_conformance_results" in data
        assert "results_by_severity" in data
        assert "open_errors" in data

    @pytest.mark.anyio
    async def test_create_sdtm_domain_with_all_classes(self, client: AsyncClient):
        for dc in ["events", "findings", "interventions", "special_purpose", "trial_design"]:
            payload = _make_sdtm_create(domain_class=dc, domain_code=f"X{dc[:2].upper()}")
            resp = await client.post(f"{API_PREFIX}/sdtm-domains", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["domain_class"] == dc

    @pytest.mark.anyio
    async def test_controlled_terms_no_trial_filter(self, client: AsyncClient):
        """Controlled terms with trial_id=None should not appear in trial-specific filters."""
        resp = await client.get(f"{API_PREFIX}/controlled-terms", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_sdtm_domain_statuses_present(self, svc: CDISCStandardsService):
        domains = svc.list_sdtm_domains()
        statuses = {d.status.value for d in domains}
        assert "validated" in statuses
        assert "mapped" in statuses
        assert "in_progress" in statuses
        assert "approved" in statuses
        assert "not_started" in statuses

    def test_conformance_severities_present(self, svc: CDISCStandardsService):
        results = svc.list_conformance_results()
        severities = {r.severity.value for r in results}
        assert "error" in severities
        assert "warning" in severities
        assert "notice" in severities
        assert "info" in severities
