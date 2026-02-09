"""Tests for Medidata Rave EDC integration.

Tests cover:
    - CDISC ODM XML parsing
    - Schema validation
    - Service methods (demo mode)
    - API endpoint responses
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.medidata_rave import (
    RaveConnectionTestResponse,
    RaveEnrollmentSyncResponse,
    RaveIntegrationStatus,
    RaveScreeningPushRequest,
    RaveScreeningPushResponse,
    RaveStudyImportRequest,
    RaveStudyImportResponse,
    RaveStudyListResponse,
    RaveStudySummary,
    RaveSubjectListResponse,
    EnrollmentStatus,
    RaveEnvironment,
)
from app.services.cdisc_odm_parser import (
    build_clinical_data_odm,
    extract_eligibility_criteria,
    parse_study_definition,
)
from app.services.medidata_rave_service import (
    MedidataRaveService,
    get_medidata_rave_service,
)


# ==============================================================================
# ODM XML Fixtures
# ==============================================================================

SAMPLE_ODM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3"
     FileType="Snapshot"
     FileOID="TEST-001"
     CreationDateTime="2024-01-01T00:00:00">
  <Study OID="STUDY-001">
    <GlobalVariables>
      <StudyName>Test Oncology Study</StudyName>
      <StudyDescription>A phase 3 study for testing</StudyDescription>
      <ProtocolName>TEST-ONCO-301</ProtocolName>
    </GlobalVariables>
    <MetaDataVersion OID="1" Name="Version 1">
      <FormDef OID="IE_FORM" Name="Inclusion/Exclusion" Repeating="No">
        <ItemGroupRef ItemGroupOID="IE_INCLUSION" Mandatory="Yes"/>
        <ItemGroupRef ItemGroupOID="IE_EXCLUSION" Mandatory="Yes"/>
      </FormDef>
      <FormDef OID="DM_FORM" Name="Demographics" Repeating="No">
        <ItemGroupRef ItemGroupOID="DM_GROUP" Mandatory="Yes"/>
      </FormDef>
      <ItemGroupDef OID="IE_INCLUSION" Name="Inclusion Criteria" Repeating="No">
        <ItemRef ItemOID="INCL01" Mandatory="Yes"/>
        <ItemRef ItemOID="INCL02" Mandatory="Yes"/>
        <ItemRef ItemOID="INCL03" Mandatory="No"/>
      </ItemGroupDef>
      <ItemGroupDef OID="IE_EXCLUSION" Name="Exclusion Criteria" Repeating="No">
        <ItemRef ItemOID="EXCL01" Mandatory="Yes"/>
        <ItemRef ItemOID="EXCL02" Mandatory="Yes"/>
      </ItemGroupDef>
      <ItemGroupDef OID="DM_GROUP" Name="Demographics" Repeating="No">
        <ItemRef ItemOID="DM_AGE" Mandatory="Yes"/>
      </ItemGroupDef>
      <ItemDef OID="INCL01" Name="Age Criterion" DataType="integer">
        <Question><TranslatedText>Age >= 18 years</TranslatedText></Question>
      </ItemDef>
      <ItemDef OID="INCL02" Name="Diagnosis" DataType="text">
        <Question><TranslatedText>Confirmed histological diagnosis of NSCLC</TranslatedText></Question>
      </ItemDef>
      <ItemDef OID="INCL03" Name="ECOG" DataType="integer">
        <Question><TranslatedText>ECOG performance status 0-1</TranslatedText></Question>
      </ItemDef>
      <ItemDef OID="EXCL01" Name="Prior Treatment" DataType="text">
        <Question><TranslatedText>Prior anti-PD-1/PD-L1 therapy</TranslatedText></Question>
      </ItemDef>
      <ItemDef OID="EXCL02" Name="CNS Metastases" DataType="text">
        <Question><TranslatedText>Active CNS metastases</TranslatedText></Question>
      </ItemDef>
      <ItemDef OID="DM_AGE" Name="Age" DataType="integer">
        <Question><TranslatedText>Subject age in years</TranslatedText></Question>
      </ItemDef>
    </MetaDataVersion>
  </Study>
</ODM>"""

MINIMAL_ODM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3">
  <Study OID="MINIMAL">
    <GlobalVariables>
      <StudyName>Minimal Study</StudyName>
    </GlobalVariables>
  </Study>
</ODM>"""


# ==============================================================================
# CDISC ODM Parser Tests
# ==============================================================================


class TestCdiscOdmParser:
    """Tests for CDISC ODM XML parsing."""

    def test_parse_study_definition_basic(self):
        """Parse basic study metadata from ODM XML."""
        result = parse_study_definition(SAMPLE_ODM_XML)

        assert result["oid"] == "STUDY-001"
        assert result["name"] == "Test Oncology Study"
        assert result["description"] == "A phase 3 study for testing"
        assert result["protocol_name"] == "TEST-ONCO-301"

    def test_parse_study_forms(self):
        """Parse form definitions from ODM."""
        result = parse_study_definition(SAMPLE_ODM_XML)

        assert len(result["forms"]) == 2
        ie_form = next(f for f in result["forms"] if f["oid"] == "IE_FORM")
        assert ie_form["name"] == "Inclusion/Exclusion"
        assert len(ie_form["item_group_refs"]) == 2

    def test_parse_study_items(self):
        """Parse item definitions from ODM."""
        result = parse_study_definition(SAMPLE_ODM_XML)

        assert len(result["items"]) == 6
        incl01 = next(i for i in result["items"] if i["oid"] == "INCL01")
        assert incl01["data_type"] == "integer"
        assert incl01["question"] == "Age >= 18 years"

    def test_parse_item_groups(self):
        """Parse item group definitions from ODM."""
        result = parse_study_definition(SAMPLE_ODM_XML)

        assert len(result["item_groups"]) == 3
        incl_group = next(ig for ig in result["item_groups"] if ig["oid"] == "IE_INCLUSION")
        assert incl_group["name"] == "Inclusion Criteria"
        assert len(incl_group["item_refs"]) == 3

    def test_parse_minimal_odm(self):
        """Parse minimal ODM with just study name."""
        result = parse_study_definition(MINIMAL_ODM_XML)

        assert result["oid"] == "MINIMAL"
        assert result["name"] == "Minimal Study"
        assert result["forms"] == []
        assert result["items"] == []

    def test_extract_eligibility_criteria(self):
        """Extract eligibility criteria from ODM."""
        criteria = extract_eligibility_criteria(SAMPLE_ODM_XML)

        assert len(criteria) == 5  # 3 inclusion + 2 exclusion

        inclusion = [c for c in criteria if c["criterion_type"] == "inclusion"]
        exclusion = [c for c in criteria if c["criterion_type"] == "exclusion"]

        assert len(inclusion) == 3
        assert len(exclusion) == 2

        # Verify specific criteria
        age_criterion = next(c for c in criteria if c["oid"] == "INCL01")
        assert "Age >= 18" in age_criterion["description"]
        assert age_criterion["criterion_type"] == "inclusion"

        cns_criterion = next(c for c in criteria if c["oid"] == "EXCL02")
        assert "CNS" in cns_criterion["description"]
        assert cns_criterion["criterion_type"] == "exclusion"

    def test_extract_criteria_no_eligibility(self):
        """Handle ODM with no eligibility form."""
        # Remove eligibility items from minimal ODM
        criteria = extract_eligibility_criteria(MINIMAL_ODM_XML)
        assert criteria == []

    def test_build_clinical_data_odm(self):
        """Build clinical data ODM XML for Rave submission."""
        patient_data = {
            "subject_key": "SUBJ-001",
            "items": [
                {"oid": "INCL01", "value": "Yes"},
                {"oid": "EXCL01", "value": "No"},
            ],
        }

        odm_xml = build_clinical_data_odm(
            patient_data=patient_data,
            study_oid="STUDY-001",
            environment="Prod",
        )

        assert '<?xml version="1.0"' in odm_xml
        assert "STUDY-001" in odm_xml
        assert "SUBJ-001" in odm_xml
        assert 'ItemOID="INCL01"' in odm_xml
        assert 'Value="Yes"' in odm_xml
        assert "http://www.cdisc.org/ns/odm/v1.3" in odm_xml

    def test_build_odm_xml_escaping(self):
        """Verify XML special characters are escaped."""
        patient_data = {
            "subject_key": 'SUBJ-"001"',
            "items": [{"oid": "ITEM1", "value": "A & B < C"}],
        }

        odm_xml = build_clinical_data_odm(
            patient_data=patient_data,
            study_oid="STUDY-001",
        )

        assert "&amp;" in odm_xml
        assert "&lt;" in odm_xml
        assert "&quot;" in odm_xml


# ==============================================================================
# Schema Validation Tests
# ==============================================================================


class TestSchemas:
    """Test Pydantic schema validation."""

    def test_study_summary_schema(self):
        """Validate RaveStudySummary schema."""
        study = RaveStudySummary(
            oid="STUDY-001",
            name="Test Study",
            environment="Prod",
            protocol_number="PROTO-001",
            phase="Phase 3",
            sponsor="Sponsor Inc",
            subject_count=100,
        )
        assert study.oid == "STUDY-001"
        assert study.subject_count == 100

    def test_study_summary_minimal(self):
        """Validate RaveStudySummary with minimal fields."""
        study = RaveStudySummary(
            oid="S1",
            name="Minimal",
            environment="UAT",
        )
        assert study.protocol_number is None
        assert study.subject_count == 0

    def test_connection_test_response(self):
        """Validate RaveConnectionTestResponse schema."""
        resp = RaveConnectionTestResponse(
            connected=True,
            version="2024.1.0",
            studies_count=5,
            latency_ms=15.3,
            demo_mode=True,
        )
        assert resp.connected is True
        assert resp.demo_mode is True

    def test_import_response_schema(self):
        """Validate RaveStudyImportResponse schema."""
        resp = RaveStudyImportResponse(
            study_oid="STUDY-001",
            study_name="Test Study",
            criteria_count=10,
            forms_count=5,
            demo_mode=True,
        )
        assert resp.trial_id is None
        assert resp.criteria == []

    def test_screening_push_request(self):
        """Validate RaveScreeningPushRequest schema."""
        req = RaveScreeningPushRequest(
            trial_id="trial-001",
            patient_ids=["pat-001", "pat-002"],
            include_details=True,
        )
        assert len(req.patient_ids) == 2

    def test_enrollment_status_enum(self):
        """Validate enrollment status enum values."""
        assert EnrollmentStatus.ENROLLED == "Enrolled"
        assert EnrollmentStatus.SCREEN_FAILED == "Screen Failed"
        assert EnrollmentStatus.RANDOMIZED == "Randomized"

    def test_rave_environment_enum(self):
        """Validate Rave environment enum values."""
        assert RaveEnvironment.PROD == "Prod"
        assert RaveEnvironment.UAT == "UAT"

    def test_integration_status_defaults(self):
        """Validate RaveIntegrationStatus defaults."""
        status = RaveIntegrationStatus()
        assert status.configured is False
        assert status.demo_mode is False
        assert status.studies_imported == 0


# ==============================================================================
# Service Tests (Demo Mode)
# ==============================================================================


class TestMedidataRaveService:
    """Test MedidataRaveService in demo mode."""

    @pytest.mark.asyncio
    async def test_demo_mode_detection(self):
        """Service detects demo mode when no credentials configured."""
        service = MedidataRaveService(base_url="", username="", password="")
        assert service.demo_mode is True
        await service.close()

    @pytest.mark.asyncio
    async def test_configured_mode_detection(self):
        """Service detects configured mode with credentials."""
        service = MedidataRaveService(
            base_url="https://rave.example.com",
            username="user",
            password="pass",
        )
        assert service.demo_mode is False
        await service.close()

    @pytest.mark.asyncio
    async def test_test_connection_demo(self):
        """Test connection returns demo data."""
        service = MedidataRaveService(base_url="", username="", password="")
        result = await service.test_connection()

        assert result["connected"] is True
        assert result["demo_mode"] is True
        assert result["studies_count"] > 0
        assert result["latency_ms"] > 0
        await service.close()

    @pytest.mark.asyncio
    async def test_list_studies_demo(self):
        """List studies returns demo data."""
        service = MedidataRaveService(base_url="", username="", password="")
        studies = await service.list_studies()

        assert len(studies) > 0
        assert all("oid" in s for s in studies)
        assert all("name" in s for s in studies)
        # Should include Regeneron studies
        oids = [s["oid"] for s in studies]
        assert any("REGEN" in oid for oid in oids)
        await service.close()

    @pytest.mark.asyncio
    async def test_import_study_demo(self):
        """Import study returns demo criteria."""
        service = MedidataRaveService(base_url="", username="", password="")
        result = await service.import_study("REGEN-2024-ONCO-201", "Prod")

        assert result["demo_mode"] is True
        assert result["study_oid"] == "REGEN-2024-ONCO-201"
        assert result["criteria_count"] > 0
        assert len(result["criteria"]) == result["criteria_count"]

        # Verify criteria types
        inclusion = [c for c in result["criteria"] if c["criterion_type"] == "inclusion"]
        exclusion = [c for c in result["criteria"] if c["criterion_type"] == "exclusion"]
        assert len(inclusion) > 0
        assert len(exclusion) > 0
        await service.close()

    @pytest.mark.asyncio
    async def test_push_screening_demo(self):
        """Push screening result returns demo success."""
        service = MedidataRaveService(base_url="", username="", password="")
        result = await service.push_screening_result(
            trial_id="trial-001",
            patient_id="pat-001",
            eligibility_result={},
        )

        assert result["success"] is True
        assert result["rave_subject_key"] is not None
        assert result["error"] is None
        await service.close()

    @pytest.mark.asyncio
    async def test_sync_enrollment_demo(self):
        """Sync enrollment returns demo status updates."""
        service = MedidataRaveService(base_url="", username="", password="")
        result = await service.sync_enrollment_status("trial-001")

        assert result["demo_mode"] is True
        assert result["synced_count"] > 0
        assert len(result["status_updates"]) > 0

        statuses = {u["status"] for u in result["status_updates"]}
        assert "Enrolled" in statuses
        await service.close()

    @pytest.mark.asyncio
    async def test_get_study_subjects_demo(self):
        """Get subjects returns demo data."""
        service = MedidataRaveService(base_url="", username="", password="")
        subjects = await service.get_study_subjects("STUDY-001", "Prod")

        assert len(subjects) > 0
        assert all("subject_key" in s for s in subjects)
        await service.close()

    @pytest.mark.asyncio
    async def test_singleton_accessor(self):
        """Singleton accessor returns same instance."""
        svc1 = get_medidata_rave_service()
        svc2 = get_medidata_rave_service()
        assert svc1 is svc2

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Service works as async context manager."""
        async with MedidataRaveService(base_url="", username="", password="") as service:
            assert service.demo_mode is True
            result = await service.test_connection()
            assert result["connected"] is True


# ==============================================================================
# API Endpoint Tests
# ==============================================================================


class TestMedidataRaveAPI:
    """Test Medidata Rave API endpoints."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app."""
        from fastapi import FastAPI
        from app.api.medidata_rave import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    @pytest.fixture
    async def client(self, app):
        """Create test HTTP client."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_connection_test_endpoint(self, client):
        """POST /connection/test returns demo data."""
        resp = await client.post("/api/v1/medidata-rave/connection/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["demo_mode"] is True

    @pytest.mark.asyncio
    async def test_list_studies_endpoint(self, client):
        """GET /studies returns study list."""
        resp = await client.get("/api/v1/medidata-rave/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert "studies" in data
        assert len(data["studies"]) > 0
        assert data["total_count"] > 0

    @pytest.mark.asyncio
    async def test_import_study_endpoint(self, client):
        """POST /studies/{oid}/import returns imported criteria."""
        resp = await client.post(
            "/api/v1/medidata-rave/studies/REGEN-2024-ONCO-201/import",
            json={
                "study_oid": "REGEN-2024-ONCO-201",
                "environment": "Prod",
                "auto_create_trial": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_oid"] == "REGEN-2024-ONCO-201"
        assert data["criteria_count"] > 0
        assert len(data["criteria"]) > 0

    @pytest.mark.asyncio
    async def test_import_study_no_body(self, client):
        """POST /studies/{oid}/import works without request body."""
        resp = await client.post(
            "/api/v1/medidata-rave/studies/REGEN-2024-ALZ-301/import",
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_subjects_endpoint(self, client):
        """GET /studies/{oid}/subjects returns subjects."""
        resp = await client.get(
            "/api/v1/medidata-rave/studies/STUDY-001/subjects",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "subjects" in data
        assert len(data["subjects"]) > 0

    @pytest.mark.asyncio
    async def test_push_screening_endpoint(self, client):
        """POST /screening/push returns push results."""
        resp = await client.post(
            "/api/v1/medidata-rave/screening/push",
            json={
                "trial_id": "trial-001",
                "patient_ids": ["pat-001", "pat-002"],
                "include_details": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pushed_count"] == 2
        assert data["failed_count"] == 0
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_enrollment_sync_endpoint(self, client):
        """POST /enrollment/sync returns sync results."""
        resp = await client.post(
            "/api/v1/medidata-rave/enrollment/sync",
            params={"trial_id": "trial-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] > 0
        assert len(data["status_updates"]) > 0

    @pytest.mark.asyncio
    async def test_status_endpoint(self, client):
        """GET /status returns integration status."""
        resp = await client.get("/api/v1/medidata-rave/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "demo_mode" in data
