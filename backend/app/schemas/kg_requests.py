"""Request validation schemas for Knowledge Graph API endpoints.

This module provides Pydantic models for validating KG API requests:
- CUI and identifier validation
- Query parameter validation
- Request body validation
- Semantic type constraints
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# =============================================================================
# Enums
# =============================================================================


class SemanticGroup(str, Enum):
    """UMLS Semantic Groups for categorizing concepts."""

    ANATOMY = "ANAT"
    CHEMICALS_AND_DRUGS = "CHEM"
    CONCEPTS_AND_IDEAS = "CONC"
    DEVICES = "DEVI"
    DISORDERS = "DISO"
    GENES_AND_MOLECULAR_SEQUENCES = "GENE"
    GEOGRAPHIC_AREAS = "GEOG"
    LIVING_BEINGS = "LIVB"
    OBJECTS = "OBJC"
    OCCUPATIONS = "OCCU"
    ORGANIZATIONS = "ORGA"
    PHENOMENA = "PHEN"
    PHYSIOLOGY = "PHYS"
    PROCEDURES = "PROC"


class RelationshipType(str, Enum):
    """Types of relationships between concepts."""

    IS_A = "is_a"
    PART_OF = "part_of"
    CAUSES = "causes"
    TREATS = "treats"
    DIAGNOSES = "diagnoses"
    INDICATES = "indicates"
    CONTRAINDICATED = "contraindicated"
    INTERACTS_WITH = "interacts_with"
    HAS_INGREDIENT = "has_ingredient"
    HAS_MANIFESTATION = "has_manifestation"
    HAS_FINDING_SITE = "has_finding_site"
    ASSOCIATED_WITH = "associated_with"


class SortOrder(str, Enum):
    """Sort order for query results."""

    RELEVANCE = "relevance"
    ALPHABETICAL = "alphabetical"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"
    CONFIDENCE_ASC = "confidence_asc"
    CONFIDENCE_DESC = "confidence_desc"


class ReasoningStrategy(str, Enum):
    """Multi-hop reasoning strategies."""

    BREADTH_FIRST = "bfs"
    DEPTH_FIRST = "dfs"
    BIDIRECTIONAL = "bidirectional"
    WEIGHTED = "weighted"
    SEMANTIC = "semantic"


# =============================================================================
# Custom Types and Validators
# =============================================================================


# CUI pattern: C followed by 7 digits
CUI_PATTERN = re.compile(r"^C\d{7}$")

# Patient ID pattern: UUID or custom format
PATIENT_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$|"
    r"^P\d{6,10}$",
    re.IGNORECASE,
)

# RxNorm CUI pattern
RXCUI_PATTERN = re.compile(r"^\d{1,10}$")


def validate_cui(value: str) -> str:
    """Validate UMLS CUI format."""
    if not CUI_PATTERN.match(value.upper()):
        raise ValueError(
            f"Invalid CUI format: {value}. Must be C followed by 7 digits (e.g., C0004096)"
        )
    return value.upper()


def validate_patient_id(value: str) -> str:
    """Validate patient ID format."""
    if not PATIENT_ID_PATTERN.match(value):
        raise ValueError(
            f"Invalid patient ID format: {value}. Must be UUID or P followed by 6-10 digits"
        )
    return value


def validate_rxcui(value: str) -> str:
    """Validate RxNorm CUI format."""
    if not RXCUI_PATTERN.match(value):
        raise ValueError(
            f"Invalid RxCUI format: {value}. Must be 1-10 digits"
        )
    return value


# =============================================================================
# Base Models
# =============================================================================


class KGBaseModel(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        populate_by_name=True,
    )


class PaginationParams(KGBaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, le=10000, description="Page number")
    page_size: int = Field(
        default=20, ge=1, le=100, alias="pageSize", description="Items per page"
    )

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class DateRangeParams(KGBaseModel):
    """Date range parameters for filtering."""

    start_date: date | None = Field(
        default=None, alias="startDate", description="Start date (inclusive)"
    )
    end_date: date | None = Field(
        default=None, alias="endDate", description="End date (inclusive)"
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeParams":
        """Validate that start_date <= end_date."""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be before or equal to end_date")
        return self


# =============================================================================
# Concept Lookup Requests
# =============================================================================


class ConceptLookupRequest(KGBaseModel):
    """Request to look up a single concept by CUI."""

    cui: str = Field(description="UMLS Concept Unique Identifier")
    include_relationships: bool = Field(
        default=False,
        alias="includeRelationships",
        description="Include related concepts",
    )
    include_definitions: bool = Field(
        default=True,
        alias="includeDefinitions",
        description="Include concept definitions",
    )
    include_semantic_types: bool = Field(
        default=True,
        alias="includeSemanticTypes",
        description="Include semantic type information",
    )
    max_relationships: int = Field(
        default=10,
        ge=0,
        le=100,
        alias="maxRelationships",
        description="Maximum relationships to return",
    )

    @field_validator("cui")
    @classmethod
    def validate_cui_format(cls, v: str) -> str:
        return validate_cui(v)


class BatchConceptLookupRequest(KGBaseModel):
    """Request to look up multiple concepts by CUI."""

    cuis: list[str] = Field(
        min_length=1,
        max_length=100,
        description="List of CUIs to look up",
    )
    include_relationships: bool = Field(
        default=False, alias="includeRelationships"
    )
    include_definitions: bool = Field(
        default=True, alias="includeDefinitions"
    )

    @field_validator("cuis")
    @classmethod
    def validate_all_cuis(cls, v: list[str]) -> list[str]:
        return [validate_cui(cui) for cui in v]


# =============================================================================
# Concept Search Requests
# =============================================================================


class ConceptSearchRequest(KGBaseModel):
    """Request to search for concepts by text."""

    query: str = Field(
        min_length=2,
        max_length=500,
        description="Search query text",
    )
    semantic_groups: list[SemanticGroup] | None = Field(
        default=None,
        alias="semanticGroups",
        description="Filter by semantic groups",
    )
    semantic_types: list[str] | None = Field(
        default=None,
        alias="semanticTypes",
        description="Filter by specific semantic types",
    )
    sources: list[str] | None = Field(
        default=None,
        description="Filter by source vocabularies (e.g., SNOMEDCT_US, ICD10CM)",
    )
    include_obsolete: bool = Field(
        default=False,
        alias="includeObsolete",
        description="Include obsolete concepts",
    )
    exact_match: bool = Field(
        default=False,
        alias="exactMatch",
        description="Require exact string match",
    )
    sort_by: SortOrder = Field(
        default=SortOrder.RELEVANCE,
        alias="sortBy",
        description="Sort order for results",
    )
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=100, alias="pageSize")


class SimilarConceptsRequest(KGBaseModel):
    """Request to find concepts similar to a given concept."""

    cui: str = Field(description="Source concept CUI")
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        alias="similarityThreshold",
        description="Minimum similarity score (0-1)",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=100,
        alias="maxResults",
        description="Maximum number of similar concepts",
    )
    same_semantic_group: bool = Field(
        default=True,
        alias="sameSemanticGroup",
        description="Limit to same semantic group",
    )

    @field_validator("cui")
    @classmethod
    def validate_cui_format(cls, v: str) -> str:
        return validate_cui(v)


# =============================================================================
# Relationship Requests
# =============================================================================


class RelationshipQueryRequest(KGBaseModel):
    """Request to query relationships between concepts."""

    source_cui: str = Field(alias="sourceCui", description="Source concept CUI")
    target_cui: str | None = Field(
        default=None,
        alias="targetCui",
        description="Optional target concept CUI",
    )
    relationship_types: list[RelationshipType] | None = Field(
        default=None,
        alias="relationshipTypes",
        description="Filter by relationship types",
    )
    direction: str = Field(
        default="outgoing",
        pattern="^(outgoing|incoming|both)$",
        description="Relationship direction",
    )
    max_results: int = Field(
        default=50, ge=1, le=500, alias="maxResults"
    )

    @field_validator("source_cui")
    @classmethod
    def validate_source_cui(cls, v: str) -> str:
        return validate_cui(v)

    @field_validator("target_cui")
    @classmethod
    def validate_target_cui(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_cui(v)
        return v


class PathFindingRequest(KGBaseModel):
    """Request to find paths between two concepts."""

    source_cui: str = Field(alias="sourceCui", description="Starting concept CUI")
    target_cui: str = Field(alias="targetCui", description="Target concept CUI")
    max_hops: int = Field(
        default=3,
        ge=1,
        le=6,
        alias="maxHops",
        description="Maximum path length",
    )
    max_paths: int = Field(
        default=5,
        ge=1,
        le=20,
        alias="maxPaths",
        description="Maximum paths to return",
    )
    allowed_relationships: list[RelationshipType] | None = Field(
        default=None,
        alias="allowedRelationships",
        description="Allowed relationship types in path",
    )
    avoid_cuis: list[str] | None = Field(
        default=None,
        alias="avoidCuis",
        description="CUIs to exclude from paths",
    )

    @field_validator("source_cui", "target_cui")
    @classmethod
    def validate_cuis(cls, v: str) -> str:
        return validate_cui(v)

    @field_validator("avoid_cuis")
    @classmethod
    def validate_avoid_cuis(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return [validate_cui(cui) for cui in v]
        return v


# =============================================================================
# Multi-Hop Reasoning Requests
# =============================================================================


class ReasoningRequest(KGBaseModel):
    """Request for multi-hop reasoning over the knowledge graph."""

    source_cuis: list[str] = Field(
        alias="sourceCuis",
        min_length=1,
        max_length=10,
        description="Starting concept CUIs",
    )
    target_semantic_groups: list[SemanticGroup] | None = Field(
        default=None,
        alias="targetSemanticGroups",
        description="Target semantic groups to reach",
    )
    target_cuis: list[str] | None = Field(
        default=None,
        alias="targetCuis",
        description="Specific target CUIs",
    )
    max_hops: int = Field(
        default=3, ge=1, le=5, alias="maxHops"
    )
    strategy: ReasoningStrategy = Field(
        default=ReasoningStrategy.WEIGHTED,
        description="Reasoning traversal strategy",
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        alias="minConfidence",
        description="Minimum path confidence",
    )
    include_evidence: bool = Field(
        default=True,
        alias="includeEvidence",
        description="Include supporting evidence",
    )
    max_results: int = Field(
        default=10, ge=1, le=50, alias="maxResults"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=120,
        alias="timeoutSeconds",
        description="Query timeout in seconds",
    )

    @field_validator("source_cuis")
    @classmethod
    def validate_source_cuis(cls, v: list[str]) -> list[str]:
        return [validate_cui(cui) for cui in v]

    @field_validator("target_cuis")
    @classmethod
    def validate_target_cuis(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return [validate_cui(cui) for cui in v]
        return v

    @model_validator(mode="after")
    def validate_targets(self) -> "ReasoningRequest":
        """Ensure at least one target type is specified."""
        if not self.target_semantic_groups and not self.target_cuis:
            raise ValueError(
                "Must specify either target_semantic_groups or target_cuis"
            )
        return self


class InferenceRequest(KGBaseModel):
    """Request for clinical inference based on patient data."""

    patient_id: str = Field(alias="patientId", description="Patient identifier")
    concept_cuis: list[str] = Field(
        alias="conceptCuis",
        min_length=1,
        max_length=50,
        description="Relevant concept CUIs from patient record",
    )
    inference_type: str = Field(
        default="diagnosis",
        alias="inferenceType",
        pattern="^(diagnosis|treatment|prognosis|contraindication|interaction)$",
        description="Type of clinical inference",
    )
    context_window_days: int = Field(
        default=90,
        ge=1,
        le=365,
        alias="contextWindowDays",
        description="Days of context to consider",
    )
    include_explanations: bool = Field(
        default=True,
        alias="includeExplanations",
        description="Include reasoning explanations",
    )

    @field_validator("patient_id")
    @classmethod
    def validate_patient(cls, v: str) -> str:
        return validate_patient_id(v)

    @field_validator("concept_cuis")
    @classmethod
    def validate_concepts(cls, v: list[str]) -> list[str]:
        return [validate_cui(cui) for cui in v]


# =============================================================================
# Patient Graph Requests
# =============================================================================


class PatientGraphQueryRequest(KGBaseModel):
    """Request to query a patient's knowledge graph."""

    patient_id: str = Field(alias="patientId", description="Patient identifier")
    include_conditions: bool = Field(
        default=True, alias="includeConditions"
    )
    include_medications: bool = Field(
        default=True, alias="includeMedications"
    )
    include_procedures: bool = Field(
        default=True, alias="includeProcedures"
    )
    include_observations: bool = Field(
        default=True, alias="includeObservations"
    )
    start_date: date | None = Field(
        default=None, alias="startDate"
    )
    end_date: date | None = Field(
        default=None, alias="endDate"
    )
    max_concepts: int = Field(
        default=100, ge=1, le=1000, alias="maxConcepts"
    )

    @field_validator("patient_id")
    @classmethod
    def validate_patient(cls, v: str) -> str:
        return validate_patient_id(v)

    @model_validator(mode="after")
    def validate_date_range(self) -> "PatientGraphQueryRequest":
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be before end_date")
        return self


class PatientTimelineRequest(KGBaseModel):
    """Request for patient timeline with temporal relationships."""

    patient_id: str = Field(alias="patientId")
    granularity: str = Field(
        default="day",
        pattern="^(day|week|month|year)$",
        description="Timeline granularity",
    )
    include_inferred: bool = Field(
        default=False,
        alias="includeInferred",
        description="Include inferred events",
    )
    event_types: list[str] | None = Field(
        default=None,
        alias="eventTypes",
        description="Filter by event types",
    )
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")

    @field_validator("patient_id")
    @classmethod
    def validate_patient(cls, v: str) -> str:
        return validate_patient_id(v)


# =============================================================================
# Drug Interaction Requests
# =============================================================================


class DrugInteractionRequest(KGBaseModel):
    """Request to check drug interactions."""

    drug_cuis: list[str] = Field(
        alias="drugCuis",
        min_length=2,
        max_length=20,
        description="Drug concept CUIs to check",
    )
    include_severity: bool = Field(
        default=True, alias="includeSeverity"
    )
    include_mechanism: bool = Field(
        default=True, alias="includeMechanism"
    )
    include_management: bool = Field(
        default=True, alias="includeManagement"
    )

    @field_validator("drug_cuis")
    @classmethod
    def validate_drug_cuis(cls, v: list[str]) -> list[str]:
        return [validate_cui(cui) for cui in v]


class DrugContraindicationRequest(KGBaseModel):
    """Request to check drug contraindications for a patient."""

    patient_id: str = Field(alias="patientId")
    drug_cui: str = Field(alias="drugCui", description="Drug to check")
    check_allergies: bool = Field(default=True, alias="checkAllergies")
    check_conditions: bool = Field(default=True, alias="checkConditions")
    check_age: bool = Field(default=True, alias="checkAge")
    check_pregnancy: bool = Field(default=True, alias="checkPregnancy")
    check_renal_function: bool = Field(default=True, alias="checkRenalFunction")
    check_hepatic_function: bool = Field(default=True, alias="checkHepaticFunction")

    @field_validator("patient_id")
    @classmethod
    def validate_patient(cls, v: str) -> str:
        return validate_patient_id(v)

    @field_validator("drug_cui")
    @classmethod
    def validate_drug(cls, v: str) -> str:
        return validate_cui(v)


# =============================================================================
# Graph Update Requests
# =============================================================================


class ConceptCreateRequest(KGBaseModel):
    """Request to create a new concept in the graph."""

    cui: str = Field(description="Concept Unique Identifier")
    name: str = Field(min_length=1, max_length=500, description="Concept name")
    semantic_types: list[str] = Field(
        alias="semanticTypes",
        min_length=1,
        description="Semantic type codes",
    )
    definitions: list[str] | None = Field(
        default=None, description="Concept definitions"
    )
    synonyms: list[str] | None = Field(
        default=None, description="Alternative names"
    )
    source_vocabulary: str = Field(
        alias="sourceVocabulary",
        description="Source vocabulary (e.g., SNOMEDCT_US)",
    )
    source_code: str | None = Field(
        default=None, alias="sourceCode", description="Code in source vocabulary"
    )

    @field_validator("cui")
    @classmethod
    def validate_cui_format(cls, v: str) -> str:
        return validate_cui(v)


class RelationshipCreateRequest(KGBaseModel):
    """Request to create a relationship between concepts."""

    source_cui: str = Field(alias="sourceCui")
    target_cui: str = Field(alias="targetCui")
    relationship_type: RelationshipType = Field(alias="relationshipType")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_source: str | None = Field(
        default=None, alias="evidenceSource"
    )
    valid_from: datetime | None = Field(default=None, alias="validFrom")
    valid_to: datetime | None = Field(default=None, alias="validTo")

    @field_validator("source_cui", "target_cui")
    @classmethod
    def validate_cuis(cls, v: str) -> str:
        return validate_cui(v)

    @model_validator(mode="after")
    def validate_different_concepts(self) -> "RelationshipCreateRequest":
        if self.source_cui == self.target_cui:
            raise ValueError("source_cui and target_cui must be different")
        return self


# =============================================================================
# Admin Requests
# =============================================================================


class GraphStatsRequest(KGBaseModel):
    """Request for graph statistics."""

    include_distribution: bool = Field(
        default=False, alias="includeDistribution"
    )
    include_quality_metrics: bool = Field(
        default=False, alias="includeQualityMetrics"
    )
    semantic_groups: list[SemanticGroup] | None = Field(
        default=None, alias="semanticGroups"
    )


class GraphExportRequest(KGBaseModel):
    """Request to export graph data."""

    format: str = Field(
        default="json",
        pattern="^(json|csv|rdf|graphml)$",
        description="Export format",
    )
    semantic_groups: list[SemanticGroup] | None = Field(
        default=None, alias="semanticGroups"
    )
    include_relationships: bool = Field(
        default=True, alias="includeRelationships"
    )
    max_concepts: int = Field(
        default=10000, ge=1, le=1000000, alias="maxConcepts"
    )
    compress: bool = Field(default=True, description="Compress output")


class CacheInvalidationRequest(KGBaseModel):
    """Request to invalidate cache entries."""

    cuis: list[str] | None = Field(
        default=None, description="Specific CUIs to invalidate"
    )
    patient_ids: list[str] | None = Field(
        default=None, alias="patientIds", description="Patient caches to invalidate"
    )
    invalidate_all: bool = Field(
        default=False, alias="invalidateAll", description="Invalidate entire cache"
    )
    cache_types: list[str] | None = Field(
        default=None,
        alias="cacheTypes",
        description="Cache types to invalidate",
    )

    @field_validator("cuis")
    @classmethod
    def validate_cuis(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return [validate_cui(cui) for cui in v]
        return v

    @field_validator("patient_ids")
    @classmethod
    def validate_patients(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return [validate_patient_id(pid) for pid in v]
        return v

    @model_validator(mode="after")
    def validate_invalidation_target(self) -> "CacheInvalidationRequest":
        """Ensure at least one invalidation target is specified."""
        if (
            not self.cuis
            and not self.patient_ids
            and not self.invalidate_all
            and not self.cache_types
        ):
            raise ValueError(
                "Must specify cuis, patient_ids, cache_types, or invalidate_all"
            )
        return self
