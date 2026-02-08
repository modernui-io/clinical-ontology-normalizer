"""Tests for EDC/CTMS Integration Roadmap (Partnership-2).

Covers:
- Integration specification listing and retrieval
- System-specific integration details and patterns
- Readiness assessment per system with capability breakdown
- Phased integration roadmap structure and content
- Effort estimation accuracy
- Data mapping templates and field coverage
- Integration summary with aggregate metrics
- API endpoint responses (valid and invalid)
- Edge cases and error handling
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.integration_roadmap import (
    AuthMethod,
    CapabilityReadiness,
    DataFlowDirection,
    DataFormat,
    DataMappingTemplate,
    EffortEstimate,
    FieldMapping,
    FieldMappingDirection,
    IntegrationCategory,
    IntegrationListResponse,
    IntegrationPattern,
    IntegrationRoadmap,
    IntegrationSpec,
    IntegrationSummary,
    IntegrationSystem,
    ReadinessAssessment,
    ReadinessStatus,
    RoadmapMilestone,
    RoadmapPhase,
    RoadmapPhaseDetail,
    SyncMethod,
)
from app.services.integration_roadmap_service import (
    IntegrationRoadmapService,
    get_integration_roadmap_service,
    reset_integration_roadmap_service,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def service() -> IntegrationRoadmapService:
    """Create a fresh IntegrationRoadmapService."""
    return IntegrationRoadmapService()


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before each test."""
    reset_integration_roadmap_service()
    yield
    reset_integration_roadmap_service()


# ===========================================================================
# Integration Listing Tests
# ===========================================================================


class TestIntegrationListing:
    """Test integration listing and retrieval."""

    def test_list_integrations_returns_all_systems(self, service: IntegrationRoadmapService):
        """All 6 target systems should be present."""
        result = service.list_integrations()
        assert isinstance(result, IntegrationListResponse)
        assert result.total == 6

    def test_list_integrations_contains_expected_systems(self, service: IntegrationRoadmapService):
        """Verify all expected system identifiers are present."""
        result = service.list_integrations()
        system_ids = {spec.system for spec in result.integrations}
        expected = {
            IntegrationSystem.MEDIDATA_RAVE,
            IntegrationSystem.VEEVA_VAULT_CTMS,
            IntegrationSystem.ORACLE_SIEBEL_CTMS,
            IntegrationSystem.REDCAP,
            IntegrationSystem.FLATIRON_ONCOEMR,
            IntegrationSystem.EPIC,
        }
        assert system_ids == expected

    def test_get_system_ids(self, service: IntegrationRoadmapService):
        """get_system_ids returns all valid system string identifiers."""
        ids = service.get_system_ids()
        assert len(ids) == 6
        assert "redcap" in ids
        assert "epic" in ids
        assert "medidata_rave" in ids

    def test_get_integration_valid_system(self, service: IntegrationRoadmapService):
        """Retrieving a valid system returns its specification."""
        result = service.get_integration("redcap")
        assert result is not None
        assert isinstance(result, IntegrationSpec)
        assert result.system == IntegrationSystem.REDCAP
        assert result.display_name == "REDCap"
        assert result.vendor == "Vanderbilt University"

    def test_get_integration_invalid_system(self, service: IntegrationRoadmapService):
        """Retrieving an invalid system returns None."""
        result = service.get_integration("nonexistent_system")
        assert result is None

    def test_integration_spec_has_pattern(self, service: IntegrationRoadmapService):
        """Each integration spec should have a valid pattern."""
        result = service.list_integrations()
        for spec in result.integrations:
            assert isinstance(spec.pattern, IntegrationPattern)
            assert isinstance(spec.pattern.data_flow, DataFlowDirection)
            assert len(spec.pattern.auth_methods) > 0
            assert len(spec.pattern.data_formats) > 0
            assert len(spec.pattern.sync_methods) > 0
            assert spec.pattern.api_type != ""

    def test_integration_spec_has_data_domains(self, service: IntegrationRoadmapService):
        """Each integration spec should have at least one data domain."""
        result = service.list_integrations()
        for spec in result.integrations:
            assert len(spec.data_domains) >= 1


# ===========================================================================
# System-Specific Detail Tests
# ===========================================================================


class TestSystemDetails:
    """Test system-specific integration details."""

    def test_medidata_rave_is_edc(self, service: IntegrationRoadmapService):
        """Medidata Rave should be categorized as EDC."""
        spec = service.get_integration("medidata_rave")
        assert spec is not None
        assert spec.category == IntegrationCategory.EDC
        assert DataFormat.CDISC_ODM in spec.pattern.data_formats

    def test_veeva_vault_is_ctms(self, service: IntegrationRoadmapService):
        """Veeva Vault should be categorized as CTMS."""
        spec = service.get_integration("veeva_vault_ctms")
        assert spec is not None
        assert spec.category == IntegrationCategory.CTMS
        assert spec.pattern.data_flow == DataFlowDirection.BIDIRECTIONAL

    def test_oracle_siebel_is_ctms(self, service: IntegrationRoadmapService):
        """Oracle Siebel should be categorized as CTMS."""
        spec = service.get_integration("oracle_siebel_ctms")
        assert spec is not None
        assert spec.category == IntegrationCategory.CTMS
        assert "SOAP" in spec.pattern.api_type

    def test_redcap_is_edc(self, service: IntegrationRoadmapService):
        """REDCap should be categorized as EDC with API key auth."""
        spec = service.get_integration("redcap")
        assert spec is not None
        assert spec.category == IntegrationCategory.EDC
        assert AuthMethod.API_KEY in spec.pattern.auth_methods

    def test_flatiron_is_emr(self, service: IntegrationRoadmapService):
        """Flatiron OncoEMR should be categorized as EMR with FHIR."""
        spec = service.get_integration("flatiron_oncoemr")
        assert spec is not None
        assert spec.category == IntegrationCategory.EMR
        assert DataFormat.FHIR_R4 in spec.pattern.data_formats
        assert spec.pattern.data_flow == DataFlowDirection.INBOUND

    def test_epic_is_ehr(self, service: IntegrationRoadmapService):
        """Epic should be categorized as EHR with SMART on FHIR."""
        spec = service.get_integration("epic")
        assert spec is not None
        assert spec.category == IntegrationCategory.EHR
        assert "SMART" in spec.pattern.api_type
        assert DataFormat.FHIR_R4 in spec.pattern.data_formats

    def test_epic_supports_hl7v2(self, service: IntegrationRoadmapService):
        """Epic should support HL7v2 data format."""
        spec = service.get_integration("epic")
        assert spec is not None
        assert DataFormat.HL7V2 in spec.pattern.data_formats

    def test_oracle_siebel_uses_certificate_auth(self, service: IntegrationRoadmapService):
        """Oracle Siebel should support certificate-based auth."""
        spec = service.get_integration("oracle_siebel_ctms")
        assert spec is not None
        assert AuthMethod.CERTIFICATE in spec.pattern.auth_methods


# ===========================================================================
# Readiness Assessment Tests
# ===========================================================================


class TestReadinessAssessment:
    """Test integration readiness assessment."""

    def test_readiness_returns_assessment(self, service: IntegrationRoadmapService):
        """Readiness assessment should return valid assessment."""
        result = service.assess_readiness("redcap")
        assert result is not None
        assert isinstance(result, ReadinessAssessment)
        assert result.system == IntegrationSystem.REDCAP

    def test_readiness_invalid_system(self, service: IntegrationRoadmapService):
        """Readiness assessment for invalid system returns None."""
        result = service.assess_readiness("invalid")
        assert result is None

    def test_readiness_has_capabilities(self, service: IntegrationRoadmapService):
        """Readiness assessment should include capability breakdown."""
        result = service.assess_readiness("epic")
        assert result is not None
        assert len(result.capabilities) > 0
        for cap in result.capabilities:
            assert isinstance(cap, CapabilityReadiness)
            assert cap.capability != ""
            assert 0.0 <= cap.coverage_pct <= 100.0

    def test_readiness_overall_percentage(self, service: IntegrationRoadmapService):
        """Overall readiness should be between 0 and 100."""
        for system_id in service.get_system_ids():
            result = service.assess_readiness(system_id)
            assert result is not None
            assert 0.0 <= result.overall_readiness_pct <= 100.0

    def test_redcap_highest_readiness(self, service: IntegrationRoadmapService):
        """REDCap should have high readiness (FHIR-native, low effort)."""
        redcap = service.assess_readiness("redcap")
        oracle = service.assess_readiness("oracle_siebel_ctms")
        assert redcap is not None
        assert oracle is not None
        assert redcap.overall_readiness_pct > oracle.overall_readiness_pct

    def test_oracle_siebel_has_blockers(self, service: IntegrationRoadmapService):
        """Oracle Siebel should have blockers (SOAP, cert auth)."""
        result = service.assess_readiness("oracle_siebel_ctms")
        assert result is not None
        assert len(result.blockers) > 0
        blocker_text = " ".join(result.blockers).lower()
        assert "soap" in blocker_text or "certificate" in blocker_text or "mtls" in blocker_text

    def test_readiness_recommended_phase(self, service: IntegrationRoadmapService):
        """Each system should have a recommended phase."""
        phase_map = {
            "redcap": RoadmapPhase.PHASE_1,
            "epic": RoadmapPhase.PHASE_1,
            "medidata_rave": RoadmapPhase.PHASE_2,
            "veeva_vault_ctms": RoadmapPhase.PHASE_3,
            "flatiron_oncoemr": RoadmapPhase.PHASE_3,
            "oracle_siebel_ctms": RoadmapPhase.PHASE_4,
        }
        for system_id, expected_phase in phase_map.items():
            result = service.assess_readiness(system_id)
            assert result is not None
            assert result.recommended_phase == expected_phase

    def test_later_phases_have_prerequisites(self, service: IntegrationRoadmapService):
        """Systems in later phases should have prerequisites."""
        result = service.assess_readiness("medidata_rave")
        assert result is not None
        assert len(result.prerequisites) > 0


# ===========================================================================
# Roadmap Tests
# ===========================================================================


class TestRoadmap:
    """Test phased integration roadmap."""

    def test_roadmap_has_four_phases(self, service: IntegrationRoadmapService):
        """Roadmap should contain exactly 4 phases."""
        roadmap = service.get_roadmap()
        assert isinstance(roadmap, IntegrationRoadmap)
        assert len(roadmap.phases) == 4

    def test_roadmap_phase_order(self, service: IntegrationRoadmapService):
        """Phases should be in order from 1 to 4."""
        roadmap = service.get_roadmap()
        phases = [p.phase for p in roadmap.phases]
        assert phases == [
            RoadmapPhase.PHASE_1,
            RoadmapPhase.PHASE_2,
            RoadmapPhase.PHASE_3,
            RoadmapPhase.PHASE_4,
        ]

    def test_phase_1_contains_redcap_and_epic(self, service: IntegrationRoadmapService):
        """Phase 1 should contain REDCap and Epic."""
        roadmap = service.get_roadmap()
        phase_1 = roadmap.phases[0]
        assert IntegrationSystem.REDCAP in phase_1.systems
        assert IntegrationSystem.EPIC in phase_1.systems

    def test_phase_4_contains_oracle_siebel(self, service: IntegrationRoadmapService):
        """Phase 4 should contain Oracle Siebel (legacy adapter)."""
        roadmap = service.get_roadmap()
        phase_4 = roadmap.phases[3]
        assert IntegrationSystem.ORACLE_SIEBEL_CTMS in phase_4.systems

    def test_roadmap_has_milestones(self, service: IntegrationRoadmapService):
        """Each phase should have at least one milestone."""
        roadmap = service.get_roadmap()
        for phase in roadmap.phases:
            assert len(phase.milestones) >= 1
            for ms in phase.milestones:
                assert isinstance(ms, RoadmapMilestone)
                assert ms.name != ""
                assert ms.target_week > 0

    def test_roadmap_effort_estimates(self, service: IntegrationRoadmapService):
        """Each phase should have effort estimates matching its systems."""
        roadmap = service.get_roadmap()
        for phase in roadmap.phases:
            assert len(phase.effort_estimates) == len(phase.systems)
            for est in phase.effort_estimates:
                assert isinstance(est, EffortEstimate)
                assert est.total_weeks > 0
                assert est.engineering_headcount > 0
                assert est.engineer_weeks > 0

    def test_roadmap_total_systems(self, service: IntegrationRoadmapService):
        """Roadmap total_systems should equal 6."""
        roadmap = service.get_roadmap()
        assert roadmap.total_systems == 6

    def test_roadmap_total_weeks_positive(self, service: IntegrationRoadmapService):
        """Total weeks should be positive."""
        roadmap = service.get_roadmap()
        assert roadmap.total_weeks > 0
        assert roadmap.total_engineer_weeks > 0

    def test_effort_has_tasks_and_risks(self, service: IntegrationRoadmapService):
        """Effort estimates should include tasks and risks."""
        roadmap = service.get_roadmap()
        for phase in roadmap.phases:
            for est in phase.effort_estimates:
                assert len(est.tasks) >= 1
                assert len(est.risks) >= 1


# ===========================================================================
# Data Mapping Tests
# ===========================================================================


class TestDataMapping:
    """Test data mapping templates."""

    def test_data_mapping_valid_system(self, service: IntegrationRoadmapService):
        """Data mapping for a valid system returns templates."""
        result = service.get_data_mapping("redcap")
        assert result is not None
        assert len(result) >= 1
        for template in result:
            assert isinstance(template, DataMappingTemplate)
            assert template.system == IntegrationSystem.REDCAP

    def test_data_mapping_invalid_system(self, service: IntegrationRoadmapService):
        """Data mapping for invalid system returns None."""
        result = service.get_data_mapping("invalid")
        assert result is None

    def test_data_mapping_has_field_mappings(self, service: IntegrationRoadmapService):
        """Data mapping templates should have field mappings."""
        for system_id in service.get_system_ids():
            result = service.get_data_mapping(system_id)
            assert result is not None
            for template in result:
                assert len(template.field_mappings) >= 1
                for fm in template.field_mappings:
                    assert isinstance(fm, FieldMapping)
                    assert fm.platform_field != ""
                    assert fm.target_field != ""

    def test_data_mapping_coverage(self, service: IntegrationRoadmapService):
        """Data mapping coverage should be between 0 and 100."""
        for system_id in service.get_system_ids():
            result = service.get_data_mapping(system_id)
            assert result is not None
            for template in result:
                assert 0.0 <= template.mapping_coverage_pct <= 100.0

    def test_epic_fhir_to_fhir_mapping(self, service: IntegrationRoadmapService):
        """Epic mapping should be FHIR R4 to FHIR R4."""
        result = service.get_data_mapping("epic")
        assert result is not None
        for template in result:
            assert template.source_format == DataFormat.FHIR_R4
            assert template.target_format == DataFormat.FHIR_R4

    def test_medidata_fhir_to_cdisc_mapping(self, service: IntegrationRoadmapService):
        """Medidata mapping should be FHIR R4 to CDISC ODM."""
        result = service.get_data_mapping("medidata_rave")
        assert result is not None
        for template in result:
            assert template.source_format == DataFormat.FHIR_R4
            assert template.target_format == DataFormat.CDISC_ODM


# ===========================================================================
# Summary Tests
# ===========================================================================


class TestSummary:
    """Test overall integration summary."""

    def test_summary_returns_valid_response(self, service: IntegrationRoadmapService):
        """Summary should return a valid IntegrationSummary."""
        result = service.get_summary()
        assert isinstance(result, IntegrationSummary)
        assert result.total_systems == 6

    def test_summary_systems_by_category(self, service: IntegrationRoadmapService):
        """Summary should categorize systems correctly."""
        result = service.get_summary()
        assert "EDC" in result.systems_by_category
        assert "CTMS" in result.systems_by_category
        assert "EHR" in result.systems_by_category
        assert "EMR" in result.systems_by_category
        total = sum(result.systems_by_category.values())
        assert total == 6

    def test_summary_systems_by_phase(self, service: IntegrationRoadmapService):
        """Summary should group systems by phase."""
        result = service.get_summary()
        assert len(result.systems_by_phase) == 4

    def test_summary_average_readiness(self, service: IntegrationRoadmapService):
        """Average readiness should be between 0 and 100."""
        result = service.get_summary()
        assert 0.0 <= result.average_readiness_pct <= 100.0

    def test_summary_highest_and_lowest_readiness(self, service: IntegrationRoadmapService):
        """Summary should identify highest and lowest readiness systems."""
        result = service.get_summary()
        assert result.highest_readiness_system is not None
        assert result.lowest_readiness_system is not None
        assert result.highest_readiness_system != result.lowest_readiness_system

    def test_summary_implemented_capabilities(self, service: IntegrationRoadmapService):
        """Summary should list implemented capabilities."""
        result = service.get_summary()
        assert len(result.implemented_capabilities) > 0
        assert "fhir_r4_compliance" in result.implemented_capabilities

    def test_summary_gaps_identified(self, service: IntegrationRoadmapService):
        """Summary should identify gaps requiring development."""
        result = service.get_summary()
        assert len(result.gaps_requiring_development) > 0
        assert "cdisc_odm_support" in result.gaps_requiring_development

    def test_summary_effort_totals(self, service: IntegrationRoadmapService):
        """Summary should have positive effort totals."""
        result = service.get_summary()
        assert result.total_effort_weeks > 0
        assert result.total_calendar_weeks > 0


# ===========================================================================
# Singleton Tests
# ===========================================================================


class TestSingleton:
    """Test singleton management."""

    def test_singleton_returns_same_instance(self):
        """get_integration_roadmap_service should return same instance."""
        svc1 = get_integration_roadmap_service()
        svc2 = get_integration_roadmap_service()
        assert svc1 is svc2

    def test_reset_clears_singleton(self):
        """reset_integration_roadmap_service should clear the instance."""
        svc1 = get_integration_roadmap_service()
        reset_integration_roadmap_service()
        svc2 = get_integration_roadmap_service()
        assert svc1 is not svc2


# ===========================================================================
# API Endpoint Tests
# ===========================================================================


class TestAPIEndpoints:
    """Test API endpoint responses."""

    @pytest.mark.anyio
    async def test_list_integrations_endpoint(self):
        """GET /partnerships/integrations returns all systems."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/partnerships/integrations")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 6
            assert len(data["integrations"]) == 6

    @pytest.mark.anyio
    async def test_get_integration_endpoint(self):
        """GET /partnerships/integrations/{system} returns system detail."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/partnerships/integrations/epic")
            assert resp.status_code == 200
            data = resp.json()
            assert data["system"] == "epic"
            assert data["display_name"] == "Epic"

    @pytest.mark.anyio
    async def test_get_integration_not_found(self):
        """GET /partnerships/integrations/{invalid} returns 404."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/partnerships/integrations/bogus")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_readiness_endpoint(self):
        """GET /partnerships/integrations/{system}/readiness returns assessment."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/integrations/redcap/readiness"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["system"] == "redcap"
            assert "overall_readiness_pct" in data
            assert "capabilities" in data

    @pytest.mark.anyio
    async def test_get_readiness_not_found(self):
        """GET /partnerships/integrations/{invalid}/readiness returns 404."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/integrations/invalid/readiness"
            )
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_roadmap_endpoint(self):
        """GET /partnerships/integrations/roadmap returns phased roadmap."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/integrations/roadmap"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_systems"] == 6
            assert len(data["phases"]) == 4

    @pytest.mark.anyio
    async def test_get_data_mapping_endpoint(self):
        """GET /partnerships/integrations/{system}/data-mapping returns templates."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/integrations/epic/data-mapping"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1

    @pytest.mark.anyio
    async def test_get_data_mapping_not_found(self):
        """GET /partnerships/integrations/{invalid}/data-mapping returns 404."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/integrations/bogus/data-mapping"
            )
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_summary_endpoint(self):
        """GET /partnerships/integrations/summary returns summary."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/integrations/summary"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_systems"] == 6
            assert "systems_by_category" in data
            assert "average_readiness_pct" in data
