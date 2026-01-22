"""Response schemas for Knowledge Graph API endpoints.

This module provides Pydantic models for KG API responses:
- Concept data models
- Relationship data models
- Reasoning and inference results
- Error responses
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.kg_requests import RelationshipType, SemanticGroup


# =============================================================================
# Base Response Models
# =============================================================================


class KGResponseModel(BaseModel):
    """Base model for all KG responses."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class PaginatedResponse(KGResponseModel):
    """Base model for paginated responses."""

    page: int = Field(description="Current page number")
    page_size: int = Field(alias="pageSize", description="Items per page")
    total_count: int = Field(alias="totalCount", description="Total items available")
    total_pages: int = Field(alias="totalPages", description="Total pages")
    has_next: bool = Field(alias="hasNext", description="Whether more pages exist")
    has_previous: bool = Field(alias="hasPrevious", description="Whether previous pages exist")


# =============================================================================
# Concept Responses
# =============================================================================


class SemanticTypeInfo(KGResponseModel):
    """Information about a semantic type."""

    type_id: str = Field(alias="typeId", description="Semantic type identifier")
    type_name: str = Field(alias="typeName", description="Human-readable name")
    group: SemanticGroup | None = Field(default=None, description="Semantic group")
    tree_number: str | None = Field(
        default=None, alias="treeNumber", description="UMLS tree number"
    )


class ConceptDefinition(KGResponseModel):
    """A definition of a concept."""

    text: str = Field(description="Definition text")
    source: str = Field(description="Source vocabulary")
    source_id: str | None = Field(
        default=None, alias="sourceId", description="ID in source vocabulary"
    )


class ConceptSynonym(KGResponseModel):
    """A synonym for a concept."""

    term: str = Field(description="Synonym term")
    term_type: str = Field(alias="termType", description="Term type (e.g., PT, SY)")
    source: str = Field(description="Source vocabulary")
    is_preferred: bool = Field(alias="isPreferred", default=False)


class ConceptResponse(KGResponseModel):
    """Response for a single concept lookup."""

    cui: str = Field(description="Concept Unique Identifier")
    name: str = Field(description="Preferred name")
    semantic_types: list[SemanticTypeInfo] = Field(
        alias="semanticTypes", description="Semantic type information"
    )
    definitions: list[ConceptDefinition] | None = Field(
        default=None, description="Concept definitions"
    )
    synonyms: list[ConceptSynonym] | None = Field(
        default=None, description="Alternative terms"
    )
    atom_count: int | None = Field(
        default=None, alias="atomCount", description="Number of atoms"
    )
    is_obsolete: bool = Field(
        default=False, alias="isObsolete", description="Whether concept is obsolete"
    )
    last_updated: datetime | None = Field(
        default=None, alias="lastUpdated", description="Last update timestamp"
    )


class ConceptSearchResult(KGResponseModel):
    """A single search result."""

    cui: str = Field(description="Concept CUI")
    name: str = Field(description="Concept name")
    semantic_types: list[str] = Field(alias="semanticTypes")
    score: float = Field(description="Relevance score")
    match_type: str = Field(
        alias="matchType", description="Type of match (exact, partial, etc.)"
    )
    matched_term: str = Field(alias="matchedTerm", description="Term that matched")
    source: str | None = Field(default=None, description="Source vocabulary")


class ConceptSearchResponse(PaginatedResponse):
    """Response for concept search."""

    query: str = Field(description="Original search query")
    results: list[ConceptSearchResult] = Field(description="Search results")
    search_time_ms: float = Field(
        alias="searchTimeMs", description="Search execution time"
    )


class SimilarConceptResponse(KGResponseModel):
    """Response for similar concepts."""

    source_cui: str = Field(alias="sourceCui", description="Source concept CUI")
    source_name: str = Field(alias="sourceName", description="Source concept name")
    similar_concepts: list["SimilarConcept"] = Field(
        alias="similarConcepts", description="Similar concepts found"
    )


class SimilarConcept(KGResponseModel):
    """A similar concept with similarity score."""

    cui: str = Field(description="Concept CUI")
    name: str = Field(description="Concept name")
    similarity_score: float = Field(
        alias="similarityScore", description="Similarity score (0-1)"
    )
    semantic_types: list[str] = Field(alias="semanticTypes")
    common_relationships: int = Field(
        alias="commonRelationships", description="Number of shared relationships"
    )


# =============================================================================
# Relationship Responses
# =============================================================================


class RelationshipResponse(KGResponseModel):
    """A single relationship between concepts."""

    source_cui: str = Field(alias="sourceCui")
    source_name: str = Field(alias="sourceName")
    target_cui: str = Field(alias="targetCui")
    target_name: str = Field(alias="targetName")
    relationship_type: RelationshipType = Field(alias="relationshipType")
    relationship_label: str = Field(alias="relationshipLabel")
    confidence: float = Field(default=1.0, description="Confidence score")
    evidence_count: int = Field(
        default=0, alias="evidenceCount", description="Supporting evidence count"
    )
    sources: list[str] = Field(default_factory=list, description="Source vocabularies")


class RelationshipQueryResponse(KGResponseModel):
    """Response for relationship query."""

    source_cui: str = Field(alias="sourceCui")
    source_name: str = Field(alias="sourceName")
    relationships: list[RelationshipResponse] = Field(description="Found relationships")
    total_count: int = Field(alias="totalCount")


# =============================================================================
# Path and Reasoning Responses
# =============================================================================


class PathNode(KGResponseModel):
    """A node in a path."""

    cui: str = Field(description="Concept CUI")
    name: str = Field(description="Concept name")
    semantic_types: list[str] = Field(alias="semanticTypes")
    position: int = Field(description="Position in path")


class PathEdge(KGResponseModel):
    """An edge in a path."""

    source_cui: str = Field(alias="sourceCui")
    target_cui: str = Field(alias="targetCui")
    relationship_type: str = Field(alias="relationshipType")
    confidence: float = Field(default=1.0)


class ConceptPath(KGResponseModel):
    """A path between two concepts."""

    nodes: list[PathNode] = Field(description="Nodes in the path")
    edges: list[PathEdge] = Field(description="Edges connecting nodes")
    length: int = Field(description="Number of hops")
    confidence: float = Field(description="Overall path confidence")
    path_type: str = Field(alias="pathType", description="Classification of path")


class PathFindingResponse(KGResponseModel):
    """Response for path finding."""

    source_cui: str = Field(alias="sourceCui")
    source_name: str = Field(alias="sourceName")
    target_cui: str = Field(alias="targetCui")
    target_name: str = Field(alias="targetName")
    paths: list[ConceptPath] = Field(description="Found paths")
    execution_time_ms: float = Field(alias="executionTimeMs")


class ReasoningEvidence(KGResponseModel):
    """Evidence supporting a reasoning conclusion."""

    source: str = Field(description="Evidence source")
    text: str | None = Field(default=None, description="Evidence text")
    confidence: float = Field(description="Evidence confidence")
    citation: str | None = Field(default=None, description="Citation reference")


class ReasoningResult(KGResponseModel):
    """A single reasoning result."""

    conclusion_cui: str = Field(alias="conclusionCui")
    conclusion_name: str = Field(alias="conclusionName")
    semantic_types: list[str] = Field(alias="semanticTypes")
    confidence: float = Field(description="Overall confidence")
    reasoning_path: ConceptPath = Field(alias="reasoningPath")
    evidence: list[ReasoningEvidence] | None = Field(default=None)
    explanation: str | None = Field(default=None, description="Human-readable explanation")


class ReasoningResponse(KGResponseModel):
    """Response for multi-hop reasoning."""

    source_cuis: list[str] = Field(alias="sourceCuis")
    results: list[ReasoningResult] = Field(description="Reasoning results")
    total_paths_explored: int = Field(alias="totalPathsExplored")
    execution_time_ms: float = Field(alias="executionTimeMs")
    strategy_used: str = Field(alias="strategyUsed")


# =============================================================================
# Clinical Inference Responses
# =============================================================================


class InferenceClass(str, Enum):
    """Classification of clinical inferences."""

    HIGH_CONFIDENCE = "high_confidence"
    MODERATE_CONFIDENCE = "moderate_confidence"
    LOW_CONFIDENCE = "low_confidence"
    SPECULATIVE = "speculative"


class ClinicalInference(KGResponseModel):
    """A clinical inference result."""

    inference_type: str = Field(alias="inferenceType")
    concept_cui: str = Field(alias="conceptCui")
    concept_name: str = Field(alias="conceptName")
    confidence: float = Field(description="Inference confidence")
    classification: InferenceClass = Field(description="Confidence classification")
    supporting_concepts: list[str] = Field(
        alias="supportingConcepts", description="CUIs supporting this inference"
    )
    reasoning_chain: ConceptPath | None = Field(
        default=None, alias="reasoningChain"
    )
    explanation: str | None = Field(default=None)
    clinical_significance: str | None = Field(
        default=None, alias="clinicalSignificance"
    )


class InferenceResponse(KGResponseModel):
    """Response for clinical inference."""

    patient_id: str = Field(alias="patientId")
    inference_type: str = Field(alias="inferenceType")
    inferences: list[ClinicalInference] = Field(description="Inference results")
    context_concepts: list[str] = Field(
        alias="contextConcepts", description="Input context CUIs"
    )
    generated_at: datetime = Field(alias="generatedAt")
    model_version: str = Field(alias="modelVersion")


# =============================================================================
# Drug Interaction Responses
# =============================================================================


class InteractionSeverity(str, Enum):
    """Drug interaction severity levels."""

    CONTRAINDICATED = "contraindicated"
    SEVERE = "severe"
    MODERATE = "moderate"
    MINOR = "minor"
    UNKNOWN = "unknown"


class DrugInteraction(KGResponseModel):
    """A drug-drug interaction."""

    drug1_cui: str = Field(alias="drug1Cui")
    drug1_name: str = Field(alias="drug1Name")
    drug2_cui: str = Field(alias="drug2Cui")
    drug2_name: str = Field(alias="drug2Name")
    severity: InteractionSeverity = Field(description="Interaction severity")
    description: str = Field(description="Interaction description")
    mechanism: str | None = Field(default=None, description="Mechanism of interaction")
    management: str | None = Field(default=None, description="Clinical management")
    evidence_level: str | None = Field(
        default=None, alias="evidenceLevel", description="Evidence quality"
    )
    sources: list[str] = Field(default_factory=list)


class DrugInteractionResponse(KGResponseModel):
    """Response for drug interaction check."""

    drugs_checked: list[str] = Field(alias="drugsChecked")
    interactions: list[DrugInteraction] = Field(description="Found interactions")
    interaction_count: int = Field(alias="interactionCount")
    severe_count: int = Field(alias="severeCount")
    checked_at: datetime = Field(alias="checkedAt")


class ContraindicationType(str, Enum):
    """Types of contraindications."""

    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    CAUTION = "caution"


class Contraindication(KGResponseModel):
    """A drug contraindication."""

    drug_cui: str = Field(alias="drugCui")
    drug_name: str = Field(alias="drugName")
    reason_cui: str = Field(alias="reasonCui")
    reason_name: str = Field(alias="reasonName")
    contraindication_type: ContraindicationType = Field(alias="contraindicationType")
    description: str = Field(description="Contraindication description")
    category: str = Field(description="Category (allergy, condition, etc.)")
    recommendation: str | None = Field(default=None)
    sources: list[str] = Field(default_factory=list)


class ContraindicationResponse(KGResponseModel):
    """Response for contraindication check."""

    patient_id: str = Field(alias="patientId")
    drug_cui: str = Field(alias="drugCui")
    drug_name: str = Field(alias="drugName")
    contraindications: list[Contraindication] = Field(description="Found contraindications")
    is_safe: bool = Field(alias="isSafe", description="Whether drug is safe for patient")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    checked_at: datetime = Field(alias="checkedAt")


# =============================================================================
# Patient Graph Responses
# =============================================================================


class PatientConcept(KGResponseModel):
    """A concept from a patient's graph."""

    cui: str = Field(description="Concept CUI")
    name: str = Field(description="Concept name")
    semantic_types: list[str] = Field(alias="semanticTypes")
    category: str = Field(description="Category (condition, medication, etc.)")
    recorded_date: datetime | None = Field(
        default=None, alias="recordedDate"
    )
    status: str | None = Field(default=None, description="Current status")
    source: str | None = Field(default=None, description="Data source")


class PatientRelationship(KGResponseModel):
    """A relationship in patient's graph."""

    source_cui: str = Field(alias="sourceCui")
    target_cui: str = Field(alias="targetCui")
    relationship_type: str = Field(alias="relationshipType")
    recorded_date: datetime | None = Field(default=None, alias="recordedDate")
    inferred: bool = Field(default=False, description="Whether relationship is inferred")


class PatientGraphResponse(KGResponseModel):
    """Response for patient graph query."""

    patient_id: str = Field(alias="patientId")
    concepts: list[PatientConcept] = Field(description="Patient concepts")
    relationships: list[PatientRelationship] = Field(description="Relationships")
    concept_count: int = Field(alias="conceptCount")
    relationship_count: int = Field(alias="relationshipCount")
    last_updated: datetime = Field(alias="lastUpdated")


class TimelineEvent(KGResponseModel):
    """An event on patient timeline."""

    event_id: str = Field(alias="eventId")
    concept_cui: str = Field(alias="conceptCui")
    concept_name: str = Field(alias="conceptName")
    event_type: str = Field(alias="eventType")
    event_date: datetime = Field(alias="eventDate")
    end_date: datetime | None = Field(default=None, alias="endDate")
    status: str | None = Field(default=None)
    details: dict[str, Any] | None = Field(default=None)
    inferred: bool = Field(default=False)


class PatientTimelineResponse(KGResponseModel):
    """Response for patient timeline."""

    patient_id: str = Field(alias="patientId")
    events: list[TimelineEvent] = Field(description="Timeline events")
    event_count: int = Field(alias="eventCount")
    start_date: datetime = Field(alias="startDate")
    end_date: datetime = Field(alias="endDate")
    granularity: str = Field(description="Timeline granularity")


# =============================================================================
# Admin Responses
# =============================================================================


class SemanticGroupStats(KGResponseModel):
    """Statistics for a semantic group."""

    group: SemanticGroup = Field(description="Semantic group")
    concept_count: int = Field(alias="conceptCount")
    relationship_count: int = Field(alias="relationshipCount")
    percentage: float = Field(description="Percentage of total")


class GraphQualityMetrics(KGResponseModel):
    """Quality metrics for the knowledge graph."""

    completeness_score: float = Field(alias="completenessScore")
    consistency_score: float = Field(alias="consistencyScore")
    connectivity_score: float = Field(alias="connectivityScore")
    freshness_score: float = Field(alias="freshnessScore")
    overall_score: float = Field(alias="overallScore")


class GraphStatsResponse(KGResponseModel):
    """Response for graph statistics."""

    total_concepts: int = Field(alias="totalConcepts")
    total_relationships: int = Field(alias="totalRelationships")
    total_semantic_types: int = Field(alias="totalSemanticTypes")
    avg_relationships_per_concept: float = Field(alias="avgRelationshipsPerConcept")
    last_updated: datetime = Field(alias="lastUpdated")
    distribution: list[SemanticGroupStats] | None = Field(default=None)
    quality_metrics: GraphQualityMetrics | None = Field(
        default=None, alias="qualityMetrics"
    )


class CacheStatsResponse(KGResponseModel):
    """Response for cache statistics."""

    total_entries: int = Field(alias="totalEntries")
    hit_rate: float = Field(alias="hitRate", description="Cache hit rate")
    miss_rate: float = Field(alias="missRate", description="Cache miss rate")
    memory_usage_mb: float = Field(alias="memoryUsageMb")
    oldest_entry: datetime | None = Field(default=None, alias="oldestEntry")
    newest_entry: datetime | None = Field(default=None, alias="newestEntry")


class CacheInvalidationResponse(KGResponseModel):
    """Response for cache invalidation."""

    entries_invalidated: int = Field(alias="entriesInvalidated")
    cuis_affected: list[str] | None = Field(default=None, alias="cuisAffected")
    patients_affected: list[str] | None = Field(default=None, alias="patientsAffected")
    invalidated_at: datetime = Field(alias="invalidatedAt")


# =============================================================================
# Error Responses
# =============================================================================


class ErrorDetail(KGResponseModel):
    """Detailed error information."""

    field: str | None = Field(default=None, description="Field that caused error")
    message: str = Field(description="Error message")
    code: str | None = Field(default=None, description="Error code")


class KGErrorResponse(KGResponseModel):
    """Standard error response."""

    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable message")
    details: list[ErrorDetail] | None = Field(default=None)
    correlation_id: str | None = Field(
        default=None, alias="correlationId", description="Request correlation ID"
    )
    timestamp: datetime = Field(description="Error timestamp")


class ValidationErrorResponse(KGResponseModel):
    """Response for validation errors."""

    error: str = Field(default="validation_error")
    message: str = Field(default="Request validation failed")
    details: list[ErrorDetail] = Field(description="Validation error details")
    correlation_id: str | None = Field(default=None, alias="correlationId")
