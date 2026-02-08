"""Tests for RFP Response Template and Competitive Positioning (Partnership-1).

Covers:
- Template section completeness and retrieval
- Capability catalog coverage and maturity classification
- Competitive matrix scoring and category completeness
- RFP generation with custom requirements
- Case study content and structure
- Requirement matching accuracy and confidence scoring
- Section retrieval (valid and invalid)
- Pricing tier structure
- API endpoint responses
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.rfp_management import (
    CapabilityCatalogResponse,
    CaseStudy,
    CaseStudyListResponse,
    CaseStudyTherapeuticArea,
    CompetitiveMatrixResponse,
    DifferentiationScore,
    MaturityLevel,
    PlatformCapability,
    PricingTier,
    RFPGeneratedResponse,
    RFPGenerateRequest,
    RFPTemplateListResponse,
    RFPTemplateSection,
    RequirementMatch,
    RequirementMatchResponse,
)
from app.services.rfp_service import RFPService, get_rfp_service, reset_rfp_service


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def service() -> RFPService:
    """Create a fresh RFPService."""
    return RFPService()


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before each test."""
    reset_rfp_service()
    yield
    reset_rfp_service()


# ===========================================================================
# Template Section Tests
# ===========================================================================


class TestTemplateSections:
    """Test RFP template sections."""

    def test_list_templates_returns_all_sections(self, service: RFPService):
        """All 10 template sections should be present."""
        result = service.list_templates()
        assert isinstance(result, RFPTemplateListResponse)
        assert result.total_sections == 10

    def test_template_section_ids(self, service: RFPService):
        """Verify all expected section IDs are present."""
        section_ids = service.get_section_ids()
        expected = {
            "executive_summary",
            "technical_architecture",
            "clinical_capabilities",
            "security_compliance",
            "data_management",
            "integration",
            "analytics",
            "quality",
            "implementation",
            "pricing",
        }
        assert set(section_ids) == expected

    def test_each_section_has_content(self, service: RFPService):
        """Each section must have non-empty content."""
        result = service.list_templates()
        for section in result.sections:
            assert section.section_id, "Section ID must not be empty"
            assert section.title, "Title must not be empty"
            assert len(section.content) > 50, (
                f"Section '{section.section_id}' content too short"
            )

    def test_each_section_has_key_points(self, service: RFPService):
        """Each section must have at least 3 key points."""
        result = service.list_templates()
        for section in result.sections:
            assert len(section.key_points) >= 3, (
                f"Section '{section.section_id}' has fewer than 3 key points"
            )

    def test_each_section_has_evidence(self, service: RFPService):
        """Each section must have at least 2 evidence items."""
        result = service.list_templates()
        for section in result.sections:
            assert len(section.evidence) >= 2, (
                f"Section '{section.section_id}' has fewer than 2 evidence items"
            )

    def test_get_valid_section(self, service: RFPService):
        """Retrieving a valid section returns the correct data."""
        section = service.get_template_section("executive_summary")
        assert section is not None
        assert section.section_id == "executive_summary"
        assert section.title == "Executive Summary"

    def test_get_invalid_section_returns_none(self, service: RFPService):
        """Retrieving an invalid section returns None."""
        section = service.get_template_section("nonexistent_section")
        assert section is None

    def test_executive_summary_mentions_fhir(self, service: RFPService):
        """Executive summary should mention FHIR integration."""
        section = service.get_template_section("executive_summary")
        assert section is not None
        assert "FHIR" in section.content or any(
            "FHIR" in kp for kp in section.key_points
        )

    def test_pricing_section_has_tiers(self, service: RFPService):
        """Pricing section should mention all three tiers."""
        section = service.get_template_section("pricing")
        assert section is not None
        combined = section.content + " ".join(section.key_points)
        assert "Starter" in combined
        assert "Professional" in combined
        assert "Enterprise" in combined


# ===========================================================================
# Capability Catalog Tests
# ===========================================================================


class TestCapabilityCatalog:
    """Test platform capability catalog."""

    def test_catalog_has_capabilities(self, service: RFPService):
        """Catalog should have at least 10 capabilities."""
        catalog = service.get_capability_catalog()
        assert isinstance(catalog, CapabilityCatalogResponse)
        assert catalog.total_capabilities >= 10

    def test_catalog_maturity_breakdown(self, service: RFPService):
        """Maturity breakdown should sum to total capabilities."""
        catalog = service.get_capability_catalog()
        total_from_maturity = sum(catalog.by_maturity.values())
        assert total_from_maturity == catalog.total_capabilities

    def test_catalog_has_production_capabilities(self, service: RFPService):
        """Catalog should have production-level capabilities."""
        catalog = service.get_capability_catalog()
        assert catalog.by_maturity.get("production", 0) >= 5

    def test_each_capability_has_required_fields(self, service: RFPService):
        """Each capability must have id, name, category, description, and maturity."""
        catalog = service.get_capability_catalog()
        for cap in catalog.capabilities:
            assert cap.id, "Capability ID must not be empty"
            assert cap.name, "Name must not be empty"
            assert cap.category, "Category must not be empty"
            assert len(cap.description) > 20, (
                f"Capability '{cap.id}' description too short"
            )
            assert cap.maturity in MaturityLevel

    def test_each_capability_has_features(self, service: RFPService):
        """Each capability should have at least 3 key features."""
        catalog = service.get_capability_catalog()
        for cap in catalog.capabilities:
            assert len(cap.key_features) >= 3, (
                f"Capability '{cap.id}' has fewer than 3 features"
            )

    def test_capability_lookup_by_id(self, service: RFPService):
        """Looking up a capability by ID should work."""
        cap = service.get_capability_by_id("fhir_integration")
        assert cap is not None
        assert cap.name == "FHIR R4 Integration"
        assert cap.maturity == MaturityLevel.PRODUCTION

    def test_capability_lookup_invalid_id(self, service: RFPService):
        """Looking up a nonexistent capability returns None."""
        cap = service.get_capability_by_id("nonexistent_capability")
        assert cap is None

    def test_fhir_capability_has_standards(self, service: RFPService):
        """FHIR capability should list relevant standards."""
        cap = service.get_capability_by_id("fhir_integration")
        assert cap is not None
        assert any("FHIR" in s for s in cap.standards)

    def test_unique_capability_ids(self, service: RFPService):
        """All capability IDs must be unique."""
        catalog = service.get_capability_catalog()
        ids = [c.id for c in catalog.capabilities]
        assert len(ids) == len(set(ids))


# ===========================================================================
# Competitive Matrix Tests
# ===========================================================================


class TestCompetitiveMatrix:
    """Test competitive positioning matrix."""

    def test_matrix_has_categories(self, service: RFPService):
        """Matrix should have at least 6 competitive categories."""
        matrix = service.get_competitive_matrix()
        assert isinstance(matrix, CompetitiveMatrixResponse)
        assert len(matrix.categories) >= 6

    def test_matrix_has_key_differentiators(self, service: RFPService):
        """Matrix should list key differentiators."""
        matrix = service.get_competitive_matrix()
        assert len(matrix.key_differentiators) >= 3

    def test_matrix_has_summary(self, service: RFPService):
        """Matrix should have a non-empty summary."""
        matrix = service.get_competitive_matrix()
        assert len(matrix.summary) > 50

    def test_each_category_has_our_score(self, service: RFPService):
        """Each category must have our differentiation score."""
        matrix = service.get_competitive_matrix()
        for cat in matrix.categories:
            assert cat.our_score in DifferentiationScore
            assert cat.category, "Category name must not be empty"

    def test_each_category_has_competitors(self, service: RFPService):
        """Each category must have at least 2 competitor scores."""
        matrix = service.get_competitive_matrix()
        for cat in matrix.categories:
            assert len(cat.competitors) >= 2, (
                f"Category '{cat.category}' has fewer than 2 competitors"
            )

    def test_leading_scores_exist(self, service: RFPService):
        """We should have LEADING scores in at least 3 categories."""
        matrix = service.get_competitive_matrix()
        leading_count = sum(
            1 for c in matrix.categories
            if c.our_score == DifferentiationScore.LEADING
        )
        assert leading_count >= 3

    def test_fhir_compliance_is_leading(self, service: RFPService):
        """FHIR R4 Compliance should be scored as LEADING."""
        matrix = service.get_competitive_matrix()
        fhir_cat = next(
            (c for c in matrix.categories if "FHIR" in c.category), None
        )
        assert fhir_cat is not None
        assert fhir_cat.our_score == DifferentiationScore.LEADING

    def test_competitor_scores_are_valid(self, service: RFPService):
        """All competitor scores must be valid DifferentiationScore values."""
        matrix = service.get_competitive_matrix()
        for cat in matrix.categories:
            for comp in cat.competitors:
                assert comp.score in DifferentiationScore
                assert comp.competitor, "Competitor name must not be empty"


# ===========================================================================
# Case Study Tests
# ===========================================================================


class TestCaseStudies:
    """Test case study templates."""

    def test_has_three_case_studies(self, service: RFPService):
        """There should be exactly 3 case studies."""
        result = service.get_case_studies()
        assert isinstance(result, CaseStudyListResponse)
        assert result.total == 3

    def test_case_study_therapeutic_areas(self, service: RFPService):
        """Case studies should cover ophthalmology, dermatology, and oncology."""
        result = service.get_case_studies()
        areas = {cs.therapeutic_area for cs in result.case_studies}
        assert CaseStudyTherapeuticArea.OPHTHALMOLOGY in areas
        assert CaseStudyTherapeuticArea.DERMATOLOGY in areas
        assert CaseStudyTherapeuticArea.ONCOLOGY in areas

    def test_case_study_has_required_fields(self, service: RFPService):
        """Each case study must have all required narrative fields."""
        result = service.get_case_studies()
        for cs in result.case_studies:
            assert cs.id, "Case study ID must not be empty"
            assert cs.title, "Title must not be empty"
            assert cs.drug_name, "Drug name must not be empty"
            assert cs.indication, "Indication must not be empty"
            assert len(cs.challenge) > 50, (
                f"Case study '{cs.id}' challenge too short"
            )
            assert len(cs.solution) > 50, (
                f"Case study '{cs.id}' solution too short"
            )

    def test_case_study_has_metrics(self, service: RFPService):
        """Each case study must have at least 3 result metrics."""
        result = service.get_case_studies()
        for cs in result.case_studies:
            assert len(cs.results) >= 3, (
                f"Case study '{cs.id}' has fewer than 3 metrics"
            )

    def test_case_study_lookup(self, service: RFPService):
        """Looking up a case study by ID should work."""
        cs = service.get_case_study_by_id("cs_dme_eylea")
        assert cs is not None
        assert "EYLEA" in cs.drug_name

    def test_case_study_lookup_invalid(self, service: RFPService):
        """Looking up a nonexistent case study returns None."""
        cs = service.get_case_study_by_id("nonexistent")
        assert cs is None

    def test_dme_eylea_case_study(self, service: RFPService):
        """DME/EYLEA case study should have correct drug and indication."""
        cs = service.get_case_study_by_id("cs_dme_eylea")
        assert cs is not None
        assert "aflibercept" in cs.drug_name.lower() or "EYLEA" in cs.drug_name
        assert "DME" in cs.indication or "Diabetic Macular" in cs.indication

    def test_cscc_libtayo_case_study(self, service: RFPService):
        """CSCC/Libtayo case study should reference oncology."""
        cs = service.get_case_study_by_id("cs_cscc_libtayo")
        assert cs is not None
        assert cs.therapeutic_area == CaseStudyTherapeuticArea.ONCOLOGY


# ===========================================================================
# Requirement Matching Tests
# ===========================================================================


class TestRequirementMatching:
    """Test requirement matching engine."""

    def test_match_fhir_requirement(self, service: RFPService):
        """FHIR-related requirements should match FHIR capability."""
        result = service.match_requirements(
            ["Must support FHIR R4 data exchange with EHR systems"]
        )
        assert isinstance(result, RequirementMatchResponse)
        assert result.total_requirements == 1
        assert result.matched_count >= 1
        assert result.matches[0].matched is True
        cap_ids = [c.id for c in result.matches[0].matched_capabilities]
        assert "fhir_integration" in cap_ids

    def test_match_hipaa_requirement(self, service: RFPService):
        """HIPAA compliance requirements should match security capability."""
        result = service.match_requirements(
            ["Must be HIPAA compliant with full audit logging"]
        )
        assert result.matched_count >= 1
        assert result.matches[0].matched is True

    def test_match_screening_requirement(self, service: RFPService):
        """Screening requirements should match trial screening capability."""
        result = service.match_requirements(
            ["Automated patient eligibility screening against trial criteria"]
        )
        assert result.matched_count >= 1

    def test_match_multiple_requirements(self, service: RFPService):
        """Matching multiple requirements should return per-requirement results."""
        requirements = [
            "FHIR R4 integration with major EHR systems",
            "HIPAA compliant security controls",
            "Automated trial screening with inclusion/exclusion criteria",
            "Diversity and inclusion reporting",
        ]
        result = service.match_requirements(requirements)
        assert result.total_requirements == 4
        assert result.matched_count >= 3
        assert len(result.matches) == 4

    def test_unmatched_requirement(self, service: RFPService):
        """A completely unrelated requirement should be a gap."""
        result = service.match_requirements(
            ["Must include blockchain-based supply chain tracking"]
        )
        assert result.gap_count >= 1
        assert result.matches[0].matched is False
        assert result.matches[0].gap_notes != ""

    def test_coverage_score(self, service: RFPService):
        """Coverage score should be between 0 and 1."""
        result = service.match_requirements(
            [
                "FHIR integration",
                "NLP extraction",
                "Something impossible to match xyz123",
            ]
        )
        assert 0.0 <= result.coverage_score <= 1.0

    def test_confidence_ranges(self, service: RFPService):
        """Confidence scores should be between 0 and 1."""
        result = service.match_requirements(
            ["FHIR R4 health information exchange interoperability"]
        )
        for match in result.matches:
            assert 0.0 <= match.confidence <= 1.0


# ===========================================================================
# RFP Generation Tests
# ===========================================================================


class TestRFPGeneration:
    """Test RFP response generation."""

    def test_generate_full_rfp(self, service: RFPService):
        """Generating a full RFP should include all sections."""
        request = RFPGenerateRequest(
            sponsor_name="Regeneron Pharmaceuticals",
            therapeutic_area="Ophthalmology",
            trial_phase="III",
        )
        result = service.generate_rfp_response(request)
        assert isinstance(result, RFPGeneratedResponse)
        assert result.sponsor_name == "Regeneron Pharmaceuticals"
        assert result.therapeutic_area == "Ophthalmology"
        assert len(result.sections) == 10

    def test_generate_rfp_with_selected_sections(self, service: RFPService):
        """RFP with selected sections should only include those sections."""
        request = RFPGenerateRequest(
            sponsor_name="Sanofi",
            sections=["executive_summary", "clinical_capabilities"],
        )
        result = service.generate_rfp_response(request)
        assert len(result.sections) == 2
        section_ids = {s.section_id for s in result.sections}
        assert "executive_summary" in section_ids
        assert "clinical_capabilities" in section_ids

    def test_generate_rfp_without_pricing(self, service: RFPService):
        """RFP without pricing should exclude pricing section."""
        request = RFPGenerateRequest(
            sponsor_name="Pfizer",
            include_pricing=False,
        )
        result = service.generate_rfp_response(request)
        section_ids = {s.section_id for s in result.sections}
        assert "pricing" not in section_ids

    def test_generate_rfp_with_requirements(self, service: RFPService):
        """RFP with requirements should match capabilities."""
        request = RFPGenerateRequest(
            sponsor_name="Regeneron",
            requirements=[
                "FHIR R4 integration",
                "HIPAA compliance",
                "Automated screening",
            ],
        )
        result = service.generate_rfp_response(request)
        assert len(result.matched_capabilities) > 0
        assert result.requirement_coverage > 0.0

    def test_generate_rfp_includes_case_studies(self, service: RFPService):
        """RFP with case studies enabled should include relevant studies."""
        request = RFPGenerateRequest(
            sponsor_name="Regeneron",
            therapeutic_area="Ophthalmology",
            include_case_studies=True,
        )
        result = service.generate_rfp_response(request)
        assert len(result.case_studies) >= 1

    def test_generate_rfp_without_case_studies(self, service: RFPService):
        """RFP with case studies disabled should have no case studies."""
        request = RFPGenerateRequest(
            sponsor_name="Regeneron",
            include_case_studies=False,
        )
        result = service.generate_rfp_response(request)
        assert len(result.case_studies) == 0

    def test_generate_rfp_includes_competitive_matrix(self, service: RFPService):
        """RFP with competitive matrix enabled should include it."""
        request = RFPGenerateRequest(
            sponsor_name="Regeneron",
            include_competitive_matrix=True,
        )
        result = service.generate_rfp_response(request)
        assert result.competitive_matrix is not None

    def test_generate_rfp_without_competitive_matrix(self, service: RFPService):
        """RFP with competitive matrix disabled should exclude it."""
        request = RFPGenerateRequest(
            sponsor_name="Regeneron",
            include_competitive_matrix=False,
        )
        result = service.generate_rfp_response(request)
        assert result.competitive_matrix is None

    def test_generate_rfp_has_timestamp(self, service: RFPService):
        """Generated RFP should have a timestamp."""
        request = RFPGenerateRequest(sponsor_name="Test Pharma")
        result = service.generate_rfp_response(request)
        assert result.generated_at is not None


# ===========================================================================
# Pricing Tier Tests
# ===========================================================================


class TestPricingTiers:
    """Test pricing tier structure."""

    def test_has_three_tiers(self, service: RFPService):
        """Should have Starter, Professional, and Enterprise tiers."""
        tiers = service.get_pricing_tiers()
        assert len(tiers) == 3

    def test_tier_names(self, service: RFPService):
        """Tier names should match expected values."""
        tiers = service.get_pricing_tiers()
        names = {t.tier for t in tiers}
        assert PricingTier.STARTER in names
        assert PricingTier.PROFESSIONAL in names
        assert PricingTier.ENTERPRISE in names

    def test_each_tier_has_features(self, service: RFPService):
        """Each tier should have at least 5 features."""
        tiers = service.get_pricing_tiers()
        for t in tiers:
            assert len(t.features) >= 5, (
                f"Tier '{t.name}' has fewer than 5 features"
            )


# ===========================================================================
# Singleton Tests
# ===========================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_rfp_service_returns_same_instance(self):
        """get_rfp_service should return the same instance."""
        svc1 = get_rfp_service()
        svc2 = get_rfp_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset_rfp_service should clear the singleton."""
        svc1 = get_rfp_service()
        reset_rfp_service()
        svc2 = get_rfp_service()
        assert svc1 is not svc2

    def test_service_stats(self):
        """Service stats should report correct counts."""
        svc = get_rfp_service()
        stats = svc.get_stats()
        assert stats["capabilities"] >= 10
        assert stats["template_sections"] == 10
        assert stats["case_studies"] == 3
        assert stats["competitive_categories"] >= 6
        assert stats["pricing_tiers"] == 3


# ===========================================================================
# API Endpoint Tests
# ===========================================================================


@pytest.mark.asyncio
class TestAPIEndpoints:
    """Test API endpoint responses."""

    async def test_list_templates_endpoint(self):
        """GET /partnerships/rfp/templates should return all sections."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/partnerships/rfp/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sections"] == 10

    async def test_get_template_section_endpoint(self):
        """GET /partnerships/rfp/templates/executive_summary should return section."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/rfp/templates/executive_summary"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["section_id"] == "executive_summary"

    async def test_get_template_section_not_found(self):
        """GET /partnerships/rfp/templates/invalid should return 404."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/rfp/templates/invalid_section"
            )
        assert resp.status_code == 404

    async def test_capabilities_endpoint(self):
        """GET /partnerships/rfp/capabilities should return catalog."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/partnerships/rfp/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_capabilities"] >= 10

    async def test_competitive_matrix_endpoint(self):
        """GET /partnerships/rfp/competitive-matrix should return matrix."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/partnerships/rfp/competitive-matrix"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["categories"]) >= 6

    async def test_case_studies_endpoint(self):
        """GET /partnerships/rfp/case-studies should return case studies."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/partnerships/rfp/case-studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    async def test_generate_rfp_endpoint(self):
        """POST /partnerships/rfp/generate should generate RFP."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/partnerships/rfp/generate",
                json={
                    "sponsor_name": "Regeneron",
                    "therapeutic_area": "Ophthalmology",
                    "trial_phase": "III",
                    "requirements": ["FHIR R4 integration"],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sponsor_name"] == "Regeneron"
        assert len(data["sections"]) > 0

    async def test_match_requirements_endpoint(self):
        """POST /partnerships/rfp/match-requirements should match requirements."""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/partnerships/rfp/match-requirements",
                json={
                    "requirements": [
                        "FHIR R4 integration",
                        "HIPAA compliance",
                    ]
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requirements"] == 2
        assert data["matched_count"] >= 1
