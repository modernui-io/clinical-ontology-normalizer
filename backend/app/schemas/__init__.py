"""Pydantic schemas for Clinical Ontology Normalizer."""

from app.schemas.base import (
    Assertion,
    Domain,
    Experiencer,
    JobStatus,
    Temporality,
)
from app.schemas.clinical_fact import (
    ClinicalFact,
    ClinicalFactCreate,
    FactEvidence,
    FactEvidenceCreate,
)
from app.schemas.document import (
    Document,
    DocumentCreate,
    DocumentUploadResponse,
    StructuredResource,
    StructuredResourceCreate,
)
from app.schemas.knowledge_graph import (
    KGEdge,
    KGEdgeCreate,
    KGNode,
    KGNodeCreate,
    PatientGraph,
)
from app.schemas.kg_requests import (
    # Enums
    RelationshipType,
    ReasoningStrategy,
    SemanticGroup,
    SortOrder,
    # Base models
    DateRangeParams,
    KGBaseModel,
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
    # Enums
    ContraindicationType,
    InferenceClass,
    InteractionSeverity,
    # Base models
    KGResponseModel,
    PaginatedResponse,
    # Concept responses
    ConceptDefinition,
    ConceptResponse,
    ConceptSearchResponse,
    ConceptSearchResult,
    ConceptSynonym,
    SemanticTypeInfo,
    SimilarConcept,
    SimilarConceptResponse,
    # Relationship responses
    RelationshipQueryResponse,
    RelationshipResponse,
    # Path responses
    ConceptPath,
    PathEdge,
    PathFindingResponse,
    PathNode,
    # Reasoning responses
    ClinicalInference,
    InferenceResponse,
    ReasoningEvidence,
    ReasoningResponse,
    ReasoningResult,
    # Drug responses
    Contraindication,
    ContraindicationResponse,
    DrugInteraction,
    DrugInteractionResponse,
    # Patient responses
    PatientConcept,
    PatientGraphResponse,
    PatientRelationship,
    PatientTimelineResponse,
    TimelineEvent,
    # Admin responses
    CacheInvalidationResponse,
    CacheStatsResponse,
    GraphQualityMetrics,
    GraphStatsResponse,
    SemanticGroupStats,
    # Error responses
    ErrorDetail,
    KGErrorResponse,
    ValidationErrorResponse,
)
from app.schemas.mention import (
    Mention,
    MentionConceptCandidate,
    MentionConceptCandidateCreate,
    MentionCreate,
)
from app.schemas.response import (
    APIResponse,
    ErrorDetail as APIErrorDetail,
    ErrorResponse,
    PaginatedAPIResponse,
    PaginationMeta,
    ResponseMeta,
)

__all__ = [
    # Base Enums
    "Assertion",
    "Domain",
    "Experiencer",
    "JobStatus",
    "Temporality",
    # KG Request Enums
    "RelationshipType",
    "ReasoningStrategy",
    "SemanticGroup",
    "SortOrder",
    # KG Response Enums
    "ContraindicationType",
    "InferenceClass",
    "InteractionSeverity",
    # Document
    "Document",
    "DocumentCreate",
    "DocumentUploadResponse",
    "StructuredResource",
    "StructuredResourceCreate",
    # Mention
    "Mention",
    "MentionCreate",
    "MentionConceptCandidate",
    "MentionConceptCandidateCreate",
    # ClinicalFact
    "ClinicalFact",
    "ClinicalFactCreate",
    "FactEvidence",
    "FactEvidenceCreate",
    # KnowledgeGraph
    "KGNode",
    "KGNodeCreate",
    "KGEdge",
    "KGEdgeCreate",
    "PatientGraph",
    # KG Base models
    "DateRangeParams",
    "KGBaseModel",
    "KGResponseModel",
    "PaginatedResponse",
    "PaginationParams",
    # KG Concept schemas
    "BatchConceptLookupRequest",
    "ConceptCreateRequest",
    "ConceptDefinition",
    "ConceptLookupRequest",
    "ConceptResponse",
    "ConceptSearchRequest",
    "ConceptSearchResponse",
    "ConceptSearchResult",
    "ConceptSynonym",
    "SemanticTypeInfo",
    "SimilarConcept",
    "SimilarConceptResponse",
    "SimilarConceptsRequest",
    # KG Relationship schemas
    "PathFindingRequest",
    "RelationshipCreateRequest",
    "RelationshipQueryRequest",
    "RelationshipQueryResponse",
    "RelationshipResponse",
    # KG Path schemas
    "ConceptPath",
    "PathEdge",
    "PathFindingResponse",
    "PathNode",
    # KG Reasoning schemas
    "ClinicalInference",
    "InferenceRequest",
    "InferenceResponse",
    "ReasoningEvidence",
    "ReasoningRequest",
    "ReasoningResponse",
    "ReasoningResult",
    # KG Drug schemas
    "Contraindication",
    "ContraindicationResponse",
    "DrugContraindicationRequest",
    "DrugInteraction",
    "DrugInteractionRequest",
    "DrugInteractionResponse",
    # KG Patient schemas
    "PatientConcept",
    "PatientGraphQueryRequest",
    "PatientGraphResponse",
    "PatientRelationship",
    "PatientTimelineRequest",
    "PatientTimelineResponse",
    "TimelineEvent",
    # KG Admin schemas
    "CacheInvalidationRequest",
    "CacheInvalidationResponse",
    "CacheStatsResponse",
    "GraphExportRequest",
    "GraphQualityMetrics",
    "GraphStatsRequest",
    "GraphStatsResponse",
    "SemanticGroupStats",
    # KG Error schemas
    "ErrorDetail",
    "KGErrorResponse",
    "ValidationErrorResponse",
    # Validators
    "validate_cui",
    "validate_patient_id",
    "validate_rxcui",
    # VP-Backend: Standard API response models
    "APIResponse",
    "APIErrorDetail",
    "ErrorResponse",
    "PaginatedAPIResponse",
    "PaginationMeta",
    "ResponseMeta",
]
