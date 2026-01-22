"""Tests for Knowledge Graph request/response validation schemas.

This module tests Pydantic validation for KG API requests and responses.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.kg_requests import (
    # Enums
    RelationshipType,
    ReasoningStrategy,
    SemanticGroup,
    SortOrder,
    # Base models
    DateRangeParams,
    PaginationParams,
    # Concept requests
    BatchConceptLookupRequest,
    ConceptCreateRequest,
    ConceptLookupRequest,
    ConceptSearchRequest,
    SimilarConceptsRequest,
    # Relationship requests
    PathFindingRequest,
    RelationshipCreateRequest,
    RelationshipQueryRequest,
    # Reasoning requests
    InferenceRequest,
    ReasoningRequest,
    # Patient requests
    PatientGraphQueryRequest,
    PatientTimelineRequest,
    # Drug requests
    DrugContraindicationRequest,
    DrugInteractionRequest,
    # Admin requests
    CacheInvalidationRequest,
    GraphExportRequest,
    GraphStatsRequest,
    # Validators
    validate_cui,
    validate_patient_id,
    validate_rxcui,
)
from app.schemas.kg_responses import (
    # Base models
    PaginatedResponse,
    # Concept responses
    ConceptDefinition,
    ConceptResponse,
    ConceptSearchResponse,
    ConceptSearchResult,
    SemanticTypeInfo,
    SimilarConcept,
    # Relationship responses
    RelationshipResponse,
    # Path responses
    ConceptPath,
    PathEdge,
    PathNode,
    # Reasoning responses
    ReasoningResult,
    # Error responses
    ErrorDetail,
    KGErrorResponse,
    ValidationErrorResponse,
)


# =============================================================================
# CUI Validation Tests
# =============================================================================


class TestCUIValidation:
    """Test CUI format validation."""

    def test_valid_cui_uppercase(self) -> None:
        """Test valid uppercase CUI."""
        result = validate_cui("C0004096")
        assert result == "C0004096"

    def test_valid_cui_lowercase_converted(self) -> None:
        """Test lowercase CUI is converted to uppercase."""
        result = validate_cui("c0004096")
        assert result == "C0004096"

    def test_invalid_cui_missing_c(self) -> None:
        """Test CUI without C prefix."""
        with pytest.raises(ValueError, match="Invalid CUI format"):
            validate_cui("0004096")

    def test_invalid_cui_wrong_prefix(self) -> None:
        """Test CUI with wrong prefix."""
        with pytest.raises(ValueError, match="Invalid CUI format"):
            validate_cui("D0004096")

    def test_invalid_cui_too_short(self) -> None:
        """Test CUI with too few digits."""
        with pytest.raises(ValueError, match="Invalid CUI format"):
            validate_cui("C000409")

    def test_invalid_cui_too_long(self) -> None:
        """Test CUI with too many digits."""
        with pytest.raises(ValueError, match="Invalid CUI format"):
            validate_cui("C00040961")

    def test_invalid_cui_non_numeric(self) -> None:
        """Test CUI with non-numeric characters."""
        with pytest.raises(ValueError, match="Invalid CUI format"):
            validate_cui("C000409A")


class TestPatientIDValidation:
    """Test patient ID format validation."""

    def test_valid_uuid(self) -> None:
        """Test valid UUID format."""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = validate_patient_id(uuid)
        assert result == uuid

    def test_valid_uuid_uppercase(self) -> None:
        """Test valid uppercase UUID."""
        uuid = "123E4567-E89B-12D3-A456-426614174000"
        result = validate_patient_id(uuid)
        assert result == uuid

    def test_valid_patient_prefix_6_digits(self) -> None:
        """Test valid P prefix with 6 digits."""
        result = validate_patient_id("P123456")
        assert result == "P123456"

    def test_valid_patient_prefix_10_digits(self) -> None:
        """Test valid P prefix with 10 digits."""
        result = validate_patient_id("P1234567890")
        assert result == "P1234567890"

    def test_invalid_patient_prefix_5_digits(self) -> None:
        """Test P prefix with too few digits."""
        with pytest.raises(ValueError, match="Invalid patient ID"):
            validate_patient_id("P12345")

    def test_invalid_patient_prefix_11_digits(self) -> None:
        """Test P prefix with too many digits."""
        with pytest.raises(ValueError, match="Invalid patient ID"):
            validate_patient_id("P12345678901")

    def test_invalid_format(self) -> None:
        """Test completely invalid format."""
        with pytest.raises(ValueError, match="Invalid patient ID"):
            validate_patient_id("invalid-id")


class TestRxCUIValidation:
    """Test RxNorm CUI validation."""

    def test_valid_rxcui_short(self) -> None:
        """Test valid short RxCUI."""
        assert validate_rxcui("1") == "1"

    def test_valid_rxcui_long(self) -> None:
        """Test valid 10-digit RxCUI."""
        assert validate_rxcui("1234567890") == "1234567890"

    def test_invalid_rxcui_non_numeric(self) -> None:
        """Test RxCUI with letters."""
        with pytest.raises(ValueError, match="Invalid RxCUI"):
            validate_rxcui("123abc")

    def test_invalid_rxcui_too_long(self) -> None:
        """Test RxCUI with more than 10 digits."""
        with pytest.raises(ValueError, match="Invalid RxCUI"):
            validate_rxcui("12345678901")


# =============================================================================
# Pagination Tests
# =============================================================================


class TestPaginationParams:
    """Test pagination parameter validation."""

    def test_default_values(self) -> None:
        """Test default pagination values."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20

    def test_custom_values(self) -> None:
        """Test custom pagination values."""
        params = PaginationParams(page=5, page_size=50)
        assert params.page == 5
        assert params.page_size == 50

    def test_offset_calculation(self) -> None:
        """Test offset calculation."""
        params = PaginationParams(page=3, page_size=20)
        assert params.offset == 40

    def test_page_minimum(self) -> None:
        """Test page minimum constraint."""
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_page_maximum(self) -> None:
        """Test page maximum constraint."""
        with pytest.raises(ValidationError):
            PaginationParams(page=10001)

    def test_page_size_minimum(self) -> None:
        """Test page size minimum."""
        with pytest.raises(ValidationError):
            PaginationParams(page_size=0)

    def test_page_size_maximum(self) -> None:
        """Test page size maximum."""
        with pytest.raises(ValidationError):
            PaginationParams(page_size=101)


class TestDateRangeParams:
    """Test date range parameter validation."""

    def test_valid_date_range(self) -> None:
        """Test valid date range."""
        params = DateRangeParams(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert params.start_date == date(2024, 1, 1)
        assert params.end_date == date(2024, 12, 31)

    def test_same_start_end_date(self) -> None:
        """Test same start and end date is valid."""
        params = DateRangeParams(
            start_date=date(2024, 6, 15),
            end_date=date(2024, 6, 15),
        )
        assert params.start_date == params.end_date

    def test_invalid_date_range(self) -> None:
        """Test start date after end date."""
        with pytest.raises(ValidationError, match="start_date must be before"):
            DateRangeParams(
                start_date=date(2024, 12, 31),
                end_date=date(2024, 1, 1),
            )

    def test_optional_dates(self) -> None:
        """Test dates are optional."""
        params = DateRangeParams()
        assert params.start_date is None
        assert params.end_date is None


# =============================================================================
# Concept Request Tests
# =============================================================================


class TestConceptLookupRequest:
    """Test concept lookup request validation."""

    def test_valid_request(self) -> None:
        """Test valid concept lookup request."""
        request = ConceptLookupRequest(cui="C0004096")
        assert request.cui == "C0004096"
        assert request.include_relationships is False
        assert request.include_definitions is True

    def test_cui_normalized(self) -> None:
        """Test CUI is normalized to uppercase."""
        request = ConceptLookupRequest(cui="c0004096")
        assert request.cui == "C0004096"

    def test_invalid_cui(self) -> None:
        """Test invalid CUI rejected."""
        with pytest.raises(ValidationError):
            ConceptLookupRequest(cui="invalid")

    def test_max_relationships_constraint(self) -> None:
        """Test max relationships constraint."""
        with pytest.raises(ValidationError):
            ConceptLookupRequest(cui="C0004096", max_relationships=101)


class TestBatchConceptLookupRequest:
    """Test batch concept lookup request validation."""

    def test_valid_batch_request(self) -> None:
        """Test valid batch request."""
        request = BatchConceptLookupRequest(
            cuis=["C0004096", "C0020538", "C0011849"]
        )
        assert len(request.cuis) == 3
        assert all(cui.startswith("C") for cui in request.cuis)

    def test_empty_cuis_rejected(self) -> None:
        """Test empty CUI list rejected."""
        with pytest.raises(ValidationError):
            BatchConceptLookupRequest(cuis=[])

    def test_too_many_cuis_rejected(self) -> None:
        """Test more than 100 CUIs rejected."""
        cuis = [f"C{str(i).zfill(7)}" for i in range(101)]
        with pytest.raises(ValidationError):
            BatchConceptLookupRequest(cuis=cuis)

    def test_invalid_cui_in_list(self) -> None:
        """Test invalid CUI in list rejected."""
        with pytest.raises(ValidationError):
            BatchConceptLookupRequest(cuis=["C0004096", "invalid"])


class TestConceptSearchRequest:
    """Test concept search request validation."""

    def test_valid_search_request(self) -> None:
        """Test valid search request."""
        request = ConceptSearchRequest(query="aspirin")
        assert request.query == "aspirin"
        assert request.sort_by == SortOrder.RELEVANCE
        assert request.page == 1

    def test_query_minimum_length(self) -> None:
        """Test query minimum length."""
        with pytest.raises(ValidationError):
            ConceptSearchRequest(query="a")

    def test_query_maximum_length(self) -> None:
        """Test query maximum length."""
        with pytest.raises(ValidationError):
            ConceptSearchRequest(query="a" * 501)

    def test_semantic_groups_filter(self) -> None:
        """Test semantic groups filter."""
        request = ConceptSearchRequest(
            query="aspirin",
            semantic_groups=[SemanticGroup.CHEMICALS_AND_DRUGS],
        )
        assert SemanticGroup.CHEMICALS_AND_DRUGS in request.semantic_groups

    def test_whitespace_stripped(self) -> None:
        """Test whitespace is stripped from query."""
        request = ConceptSearchRequest(query="  aspirin  ")
        assert request.query == "aspirin"


class TestSimilarConceptsRequest:
    """Test similar concepts request validation."""

    def test_valid_request(self) -> None:
        """Test valid similar concepts request."""
        request = SimilarConceptsRequest(cui="C0004096")
        assert request.cui == "C0004096"
        assert request.similarity_threshold == 0.7

    def test_similarity_threshold_range(self) -> None:
        """Test similarity threshold must be 0-1."""
        with pytest.raises(ValidationError):
            SimilarConceptsRequest(cui="C0004096", similarity_threshold=1.5)

        with pytest.raises(ValidationError):
            SimilarConceptsRequest(cui="C0004096", similarity_threshold=-0.1)


# =============================================================================
# Relationship Request Tests
# =============================================================================


class TestRelationshipQueryRequest:
    """Test relationship query request validation."""

    def test_valid_request(self) -> None:
        """Test valid relationship query."""
        request = RelationshipQueryRequest(source_cui="C0004096")
        assert request.source_cui == "C0004096"
        assert request.direction == "outgoing"

    def test_with_target_cui(self) -> None:
        """Test request with target CUI."""
        request = RelationshipQueryRequest(
            source_cui="C0004096",
            target_cui="C0020538",
        )
        assert request.target_cui == "C0020538"

    def test_direction_validation(self) -> None:
        """Test direction must be valid."""
        with pytest.raises(ValidationError):
            RelationshipQueryRequest(
                source_cui="C0004096",
                direction="invalid",
            )


class TestPathFindingRequest:
    """Test path finding request validation."""

    def test_valid_request(self) -> None:
        """Test valid path finding request."""
        request = PathFindingRequest(
            source_cui="C0004096",
            target_cui="C0020538",
        )
        assert request.source_cui == "C0004096"
        assert request.target_cui == "C0020538"
        assert request.max_hops == 3

    def test_max_hops_constraint(self) -> None:
        """Test max hops must be 1-6."""
        with pytest.raises(ValidationError):
            PathFindingRequest(
                source_cui="C0004096",
                target_cui="C0020538",
                max_hops=7,
            )

    def test_avoid_cuis_validated(self) -> None:
        """Test avoid CUIs are validated."""
        request = PathFindingRequest(
            source_cui="C0004096",
            target_cui="C0020538",
            avoid_cuis=["C0000001"],
        )
        assert request.avoid_cuis == ["C0000001"]

        with pytest.raises(ValidationError):
            PathFindingRequest(
                source_cui="C0004096",
                target_cui="C0020538",
                avoid_cuis=["invalid"],
            )


class TestRelationshipCreateRequest:
    """Test relationship create request validation."""

    def test_valid_request(self) -> None:
        """Test valid relationship create request."""
        request = RelationshipCreateRequest(
            source_cui="C0004096",
            target_cui="C0020538",
            relationship_type=RelationshipType.TREATS,
        )
        assert request.source_cui == "C0004096"
        assert request.target_cui == "C0020538"

    def test_same_source_target_rejected(self) -> None:
        """Test same source and target rejected."""
        with pytest.raises(ValidationError, match="must be different"):
            RelationshipCreateRequest(
                source_cui="C0004096",
                target_cui="C0004096",
                relationship_type=RelationshipType.TREATS,
            )

    def test_confidence_range(self) -> None:
        """Test confidence must be 0-1."""
        with pytest.raises(ValidationError):
            RelationshipCreateRequest(
                source_cui="C0004096",
                target_cui="C0020538",
                relationship_type=RelationshipType.TREATS,
                confidence=1.5,
            )


# =============================================================================
# Reasoning Request Tests
# =============================================================================


class TestReasoningRequest:
    """Test multi-hop reasoning request validation."""

    def test_valid_request_with_semantic_groups(self) -> None:
        """Test valid request with target semantic groups."""
        request = ReasoningRequest(
            source_cuis=["C0004096"],
            target_semantic_groups=[SemanticGroup.DISORDERS],
        )
        assert request.source_cuis == ["C0004096"]
        assert request.strategy == ReasoningStrategy.WEIGHTED

    def test_valid_request_with_target_cuis(self) -> None:
        """Test valid request with target CUIs."""
        request = ReasoningRequest(
            source_cuis=["C0004096"],
            target_cuis=["C0020538"],
        )
        assert request.target_cuis == ["C0020538"]

    def test_no_targets_rejected(self) -> None:
        """Test request without targets rejected."""
        with pytest.raises(ValidationError, match="Must specify"):
            ReasoningRequest(source_cuis=["C0004096"])

    def test_max_source_cuis(self) -> None:
        """Test max source CUIs constraint."""
        cuis = [f"C{str(i).zfill(7)}" for i in range(11)]
        with pytest.raises(ValidationError):
            ReasoningRequest(
                source_cuis=cuis,
                target_semantic_groups=[SemanticGroup.DISORDERS],
            )

    def test_timeout_constraint(self) -> None:
        """Test timeout must be 1-120 seconds."""
        with pytest.raises(ValidationError):
            ReasoningRequest(
                source_cuis=["C0004096"],
                target_semantic_groups=[SemanticGroup.DISORDERS],
                timeout_seconds=121,
            )


class TestInferenceRequest:
    """Test clinical inference request validation."""

    def test_valid_request(self) -> None:
        """Test valid inference request."""
        request = InferenceRequest(
            patient_id="P1234567",
            concept_cuis=["C0004096", "C0020538"],
        )
        assert request.patient_id == "P1234567"
        assert request.inference_type == "diagnosis"

    def test_inference_type_validation(self) -> None:
        """Test inference type must be valid."""
        with pytest.raises(ValidationError):
            InferenceRequest(
                patient_id="P1234567",
                concept_cuis=["C0004096"],
                inference_type="invalid",
            )

    def test_max_concept_cuis(self) -> None:
        """Test max concept CUIs constraint."""
        cuis = [f"C{str(i).zfill(7)}" for i in range(51)]
        with pytest.raises(ValidationError):
            InferenceRequest(
                patient_id="P1234567",
                concept_cuis=cuis,
            )


# =============================================================================
# Patient Request Tests
# =============================================================================


class TestPatientGraphQueryRequest:
    """Test patient graph query request validation."""

    def test_valid_request(self) -> None:
        """Test valid patient graph request."""
        request = PatientGraphQueryRequest(
            patient_id="123e4567-e89b-12d3-a456-426614174000"
        )
        assert request.include_conditions is True
        assert request.include_medications is True

    def test_date_range_validation(self) -> None:
        """Test date range validated."""
        with pytest.raises(ValidationError, match="start_date must be before"):
            PatientGraphQueryRequest(
                patient_id="P1234567",
                start_date=date(2024, 12, 31),
                end_date=date(2024, 1, 1),
            )

    def test_max_concepts_constraint(self) -> None:
        """Test max concepts constraint."""
        with pytest.raises(ValidationError):
            PatientGraphQueryRequest(
                patient_id="P1234567",
                max_concepts=1001,
            )


class TestPatientTimelineRequest:
    """Test patient timeline request validation."""

    def test_valid_request(self) -> None:
        """Test valid timeline request."""
        request = PatientTimelineRequest(patient_id="P1234567")
        assert request.granularity == "day"
        assert request.include_inferred is False

    def test_granularity_validation(self) -> None:
        """Test granularity must be valid."""
        with pytest.raises(ValidationError):
            PatientTimelineRequest(
                patient_id="P1234567",
                granularity="hour",
            )


# =============================================================================
# Drug Request Tests
# =============================================================================


class TestDrugInteractionRequest:
    """Test drug interaction request validation."""

    def test_valid_request(self) -> None:
        """Test valid drug interaction request."""
        request = DrugInteractionRequest(
            drug_cuis=["C0004096", "C0020538"]
        )
        assert len(request.drug_cuis) == 2
        assert request.include_severity is True

    def test_minimum_drugs(self) -> None:
        """Test minimum 2 drugs required."""
        with pytest.raises(ValidationError):
            DrugInteractionRequest(drug_cuis=["C0004096"])

    def test_maximum_drugs(self) -> None:
        """Test maximum 20 drugs allowed."""
        cuis = [f"C{str(i).zfill(7)}" for i in range(21)]
        with pytest.raises(ValidationError):
            DrugInteractionRequest(drug_cuis=cuis)


class TestDrugContraindicationRequest:
    """Test drug contraindication request validation."""

    def test_valid_request(self) -> None:
        """Test valid contraindication request."""
        request = DrugContraindicationRequest(
            patient_id="P1234567",
            drug_cui="C0004096",
        )
        assert request.patient_id == "P1234567"
        assert request.check_allergies is True

    def test_all_checks_disabled(self) -> None:
        """Test all checks can be disabled."""
        request = DrugContraindicationRequest(
            patient_id="P1234567",
            drug_cui="C0004096",
            check_allergies=False,
            check_conditions=False,
            check_age=False,
            check_pregnancy=False,
            check_renal_function=False,
            check_hepatic_function=False,
        )
        assert request.check_allergies is False


# =============================================================================
# Admin Request Tests
# =============================================================================


class TestGraphStatsRequest:
    """Test graph stats request validation."""

    def test_default_values(self) -> None:
        """Test default values."""
        request = GraphStatsRequest()
        assert request.include_distribution is False
        assert request.include_quality_metrics is False

    def test_with_semantic_groups(self) -> None:
        """Test with semantic group filter."""
        request = GraphStatsRequest(
            semantic_groups=[SemanticGroup.DISORDERS, SemanticGroup.CHEMICALS_AND_DRUGS]
        )
        assert len(request.semantic_groups) == 2


class TestGraphExportRequest:
    """Test graph export request validation."""

    def test_valid_request(self) -> None:
        """Test valid export request."""
        request = GraphExportRequest(format="json")
        assert request.format == "json"
        assert request.compress is True

    def test_format_validation(self) -> None:
        """Test format must be valid."""
        with pytest.raises(ValidationError):
            GraphExportRequest(format="xml")

    def test_max_concepts_constraint(self) -> None:
        """Test max concepts constraint."""
        with pytest.raises(ValidationError):
            GraphExportRequest(max_concepts=1000001)


class TestCacheInvalidationRequest:
    """Test cache invalidation request validation."""

    def test_invalidate_by_cuis(self) -> None:
        """Test invalidation by CUIs."""
        request = CacheInvalidationRequest(cuis=["C0004096"])
        assert request.cuis == ["C0004096"]

    def test_invalidate_by_patients(self) -> None:
        """Test invalidation by patient IDs."""
        request = CacheInvalidationRequest(patient_ids=["P1234567"])
        assert request.patient_ids == ["P1234567"]

    def test_invalidate_all(self) -> None:
        """Test invalidate all flag."""
        request = CacheInvalidationRequest(invalidate_all=True)
        assert request.invalidate_all is True

    def test_no_target_rejected(self) -> None:
        """Test request without target rejected."""
        with pytest.raises(ValidationError, match="Must specify"):
            CacheInvalidationRequest()

    def test_invalid_cui_in_list(self) -> None:
        """Test invalid CUI rejected."""
        with pytest.raises(ValidationError):
            CacheInvalidationRequest(cuis=["invalid"])


# =============================================================================
# Response Schema Tests
# =============================================================================


class TestConceptResponseSchema:
    """Test concept response schema."""

    def test_valid_response(self) -> None:
        """Test valid concept response."""
        response = ConceptResponse(
            cui="C0004096",
            name="Aspirin",
            semantic_types=[
                SemanticTypeInfo(
                    type_id="T109",
                    type_name="Organic Chemical",
                )
            ],
        )
        assert response.cui == "C0004096"
        assert response.name == "Aspirin"
        assert len(response.semantic_types) == 1

    def test_with_definitions(self) -> None:
        """Test response with definitions."""
        response = ConceptResponse(
            cui="C0004096",
            name="Aspirin",
            semantic_types=[],
            definitions=[
                ConceptDefinition(
                    text="Acetylsalicylic acid",
                    source="NCI",
                )
            ],
        )
        assert len(response.definitions) == 1


class TestConceptSearchResponseSchema:
    """Test concept search response schema."""

    def test_valid_response(self) -> None:
        """Test valid search response."""
        response = ConceptSearchResponse(
            query="aspirin",
            results=[
                ConceptSearchResult(
                    cui="C0004096",
                    name="Aspirin",
                    semantic_types=["T109"],
                    score=0.95,
                    match_type="exact",
                    matched_term="aspirin",
                )
            ],
            page=1,
            page_size=20,
            total_count=1,
            total_pages=1,
            has_next=False,
            has_previous=False,
            search_time_ms=15.5,
        )
        assert response.query == "aspirin"
        assert len(response.results) == 1
        assert response.results[0].score == 0.95


class TestPathResponseSchemas:
    """Test path-related response schemas."""

    def test_path_node(self) -> None:
        """Test path node."""
        node = PathNode(
            cui="C0004096",
            name="Aspirin",
            semantic_types=["T109"],
            position=0,
        )
        assert node.position == 0

    def test_path_edge(self) -> None:
        """Test path edge."""
        edge = PathEdge(
            source_cui="C0004096",
            target_cui="C0020538",
            relationship_type="treats",
        )
        assert edge.relationship_type == "treats"

    def test_concept_path(self) -> None:
        """Test complete concept path."""
        path = ConceptPath(
            nodes=[
                PathNode(cui="C0004096", name="Aspirin", semantic_types=["T109"], position=0),
                PathNode(cui="C0020538", name="Hypertension", semantic_types=["T047"], position=1),
            ],
            edges=[
                PathEdge(source_cui="C0004096", target_cui="C0020538", relationship_type="treats"),
            ],
            length=1,
            confidence=0.85,
            path_type="treatment",
        )
        assert path.length == 1
        assert path.confidence == 0.85


class TestErrorResponseSchemas:
    """Test error response schemas."""

    def test_error_detail(self) -> None:
        """Test error detail."""
        detail = ErrorDetail(
            field="cui",
            message="Invalid CUI format",
            code="INVALID_CUI",
        )
        assert detail.field == "cui"

    def test_kg_error_response(self) -> None:
        """Test KG error response."""
        response = KGErrorResponse(
            error="validation_error",
            message="Request validation failed",
            details=[
                ErrorDetail(field="cui", message="Invalid format"),
            ],
            correlation_id="abc-123",
            timestamp=datetime.now(timezone.utc),
        )
        assert response.error == "validation_error"
        assert len(response.details) == 1

    def test_validation_error_response(self) -> None:
        """Test validation error response."""
        response = ValidationErrorResponse(
            details=[
                ErrorDetail(field="cui", message="Required"),
                ErrorDetail(field="name", message="Too short"),
            ],
        )
        assert response.error == "validation_error"
        assert len(response.details) == 2


# =============================================================================
# Enum Tests
# =============================================================================


class TestRequestEnums:
    """Test enum definitions in request schemas."""

    def test_semantic_groups(self) -> None:
        """Test semantic group values."""
        assert SemanticGroup.DISORDERS.value == "DISO"
        assert SemanticGroup.CHEMICALS_AND_DRUGS.value == "CHEM"

    def test_relationship_types(self) -> None:
        """Test relationship type values."""
        assert RelationshipType.TREATS.value == "treats"
        assert RelationshipType.CAUSES.value == "causes"

    def test_sort_order(self) -> None:
        """Test sort order values."""
        assert SortOrder.RELEVANCE.value == "relevance"
        assert SortOrder.DATE_DESC.value == "date_desc"

    def test_reasoning_strategy(self) -> None:
        """Test reasoning strategy values."""
        assert ReasoningStrategy.BREADTH_FIRST.value == "bfs"
        assert ReasoningStrategy.WEIGHTED.value == "weighted"


# =============================================================================
# Alias Tests
# =============================================================================


class TestFieldAliases:
    """Test field aliases for camelCase API."""

    def test_pagination_alias(self) -> None:
        """Test pagination uses camelCase alias."""
        params = PaginationParams(page=1, pageSize=50)
        assert params.page_size == 50

    def test_concept_lookup_aliases(self) -> None:
        """Test concept lookup aliases."""
        request = ConceptLookupRequest(
            cui="C0004096",
            includeRelationships=True,
            includeDefinitions=False,
            maxRelationships=25,
        )
        assert request.include_relationships is True
        assert request.include_definitions is False
        assert request.max_relationships == 25

    def test_path_finding_aliases(self) -> None:
        """Test path finding aliases."""
        request = PathFindingRequest(
            sourceCui="C0004096",
            targetCui="C0020538",
            maxHops=4,
            maxPaths=10,
        )
        assert request.source_cui == "C0004096"
        assert request.target_cui == "C0020538"
        assert request.max_hops == 4
        assert request.max_paths == 10


# =============================================================================
# Extra Fields Tests
# =============================================================================


class TestExtraFieldsRejected:
    """Test that extra fields are rejected."""

    def test_extra_fields_concept_lookup(self) -> None:
        """Test extra fields rejected in concept lookup."""
        with pytest.raises(ValidationError, match="Extra inputs"):
            ConceptLookupRequest(
                cui="C0004096",
                unknown_field="value",
            )

    def test_extra_fields_search(self) -> None:
        """Test extra fields rejected in search."""
        with pytest.raises(ValidationError, match="Extra inputs"):
            ConceptSearchRequest(
                query="aspirin",
                invalid_param=True,
            )


# =============================================================================
# Concept Create Request Tests
# =============================================================================


class TestConceptCreateRequest:
    """Test concept create request validation."""

    def test_valid_request(self) -> None:
        """Test valid concept create request."""
        request = ConceptCreateRequest(
            cui="C0004096",
            name="Aspirin",
            semantic_types=["T109"],
            source_vocabulary="SNOMEDCT_US",
        )
        assert request.cui == "C0004096"
        assert request.name == "Aspirin"

    def test_invalid_cui_rejected(self) -> None:
        """Test invalid CUI rejected."""
        with pytest.raises(ValidationError):
            ConceptCreateRequest(
                cui="invalid",
                name="Test",
                semantic_types=["T109"],
                source_vocabulary="SNOMEDCT_US",
            )

    def test_empty_semantic_types_rejected(self) -> None:
        """Test empty semantic types rejected."""
        with pytest.raises(ValidationError):
            ConceptCreateRequest(
                cui="C0004096",
                name="Test",
                semantic_types=[],
                source_vocabulary="SNOMEDCT_US",
            )

    def test_empty_name_rejected(self) -> None:
        """Test empty name rejected."""
        with pytest.raises(ValidationError):
            ConceptCreateRequest(
                cui="C0004096",
                name="",
                semantic_types=["T109"],
                source_vocabulary="SNOMEDCT_US",
            )
