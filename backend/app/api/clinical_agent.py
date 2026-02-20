"""Clinical Agent API for bulk document processing and hybrid querying.

Provides endpoints for:
- Bulk document import with NLP processing
- Knowledge graph building from extracted entities
- Hybrid EHR + Knowledge Graph querying with LLM reasoning

NOTE: This is the CANONICAL pilot route for ingestion-to-QA (P0-020).
All new pilot integrations should use /api/v1/clinical-agent.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import and_, func, or_, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth_middleware import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.permissions import Permission, PermissionChecker
from app.models import Document as DocumentModel
from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.models.mention import Mention as MentionModel
from app.models.provenance import ReasoningStepType
from app.models.vocabulary import ConceptRelationship
from app.schemas.base import Domain, ExtractionStatus, JobStatus
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_augmented_rag import GraphAugmentedRAGService
from app.services.multi_agent_orchestrator import (
    AgentContext,
    MultiAgentOrchestrator,
    get_multi_agent_orchestrator,
)
from app.services.nlp_rule_based import RuleBasedNLPService
from app.services.provenance_db_service import get_provenance_db_service
from app.services.concept_lookup import lookup_concept_cached
from app.services.confidence_policy_service import check_action_gate
from app.services.workflow_confidence_policy import detect_workflow_type, get_policy_for_workflow, get_policy_version
from app.services.temporal_extractor import TemporalExtractor, extract_entity_dates
from app.core.config import settings
from app.core.degradation_context import DegradationContext
from app.schemas.degradation import DegradationMetadata
from app.schemas.confidence_semantics import (
    ConfidenceBreakdown,
    ConfidenceComponent,
    ConfidenceSource,
)
from app.schemas.uncertainty_taxonomy import classify_uncertainty

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# P0-020: Custom route class that marks clinical-agent routes as the
# canonical pilot route with X-API-Stability: pilot header.
# ---------------------------------------------------------------------------

class _PilotRoute(APIRoute):
    """APIRoute subclass that adds X-API-Stability: pilot to responses."""

    def get_route_handler(self):  # type: ignore[override]
        original = super().get_route_handler()

        async def _wrapped(request: Request) -> Response:
            response = await original(request)
            response.headers["X-API-Stability"] = "pilot"
            response.headers["X-Route-Status"] = "canonical"
            return response

        return _wrapped


router = APIRouter(
    prefix="/clinical-agent",
    tags=["Clinical Agent"],
    route_class=_PilotRoute,
)


# =============================================================================
# Request/Response Models
# =============================================================================


class ClinicalNote(BaseModel):
    """Single clinical note for bulk import."""

    note_id: str = Field(..., description="Unique identifier for this note")
    note_type: str = Field(..., description="Type: progress_note, discharge_summary, etc.")
    date: str = Field(..., description="Note date (YYYY-MM-DD)")
    text: str = Field(..., description="Clinical note text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # VP-Data-1: Input validation for bulk import content
    @field_validator("text")
    @classmethod
    def validate_text_length(cls, v: str) -> str:
        """Validate text length to prevent memory issues with very large notes."""
        max_length = 100_000  # 100KB max per note
        if len(v) > max_length:
            raise ValueError(
                f"Note text exceeds maximum length of {max_length} characters "
                f"(got {len(v)} characters)"
            )
        if len(v.strip()) == 0:
            raise ValueError("Note text cannot be empty or whitespace-only")
        return v

    @field_validator("note_id", "note_type")
    @classmethod
    def validate_identifiers(cls, v: str) -> str:
        """Validate identifier fields."""
        if len(v) > 255:
            raise ValueError(f"Field exceeds maximum length of 255 characters")
        if len(v.strip()) == 0:
            raise ValueError("Field cannot be empty or whitespace-only")
        return v.strip()


class BulkImportRequest(BaseModel):
    """Request for bulk document import."""

    patient_id: str = Field(..., description="Patient identifier")
    notes: list[ClinicalNote] = Field(..., min_length=1, max_length=500, description="List of clinical notes")
    build_knowledge_graph: bool = Field(True, description="Build knowledge graph after import")

    model_config = {
        "json_schema_extra": {
            "example": {
                "patient_id": "TEST12345",
                "notes": [
                    {
                        "note_id": "note_001",
                        "note_type": "progress_note",
                        "date": "2024-01-15",
                        "text": "Patient presents with type 2 diabetes, hypertension. Taking metformin 1000mg BID.",
                        "metadata": {"provider": "Dr. Smith"}
                    }
                ],
                "build_knowledge_graph": True
            }
        }
    }


class ExtractedEntity(BaseModel):
    """Entity extracted from clinical text."""

    text: str = Field(..., description="Extracted text span")
    entity_type: str = Field(..., description="CONDITION, DRUG, MEASUREMENT, PROCEDURE")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")
    assertion: str = Field("PRESENT", description="PRESENT, ABSENT, POSSIBLE")
    omop_concept_id: int | None = Field(None, description="Mapped OMOP concept ID")
    note_id: str = Field("frontend", description="Source note ID")
    # Negation trigger info (from assertion classifier)
    negation_trigger: str | None = Field(None, description="Trigger phrase that caused negation")
    negation_trigger_confidence: float | None = Field(None, ge=0, le=1, description="Confidence of negation trigger")
    # Temporal info (for bi-temporal tracking)
    event_date: str | None = Field(None, description="Date when event occurred (ISO format)")
    document_date: str | None = Field(None, description="Date of source document (ISO format)")

    # VP-Data-1: Input validation for entity content
    @field_validator("text")
    @classmethod
    def validate_text_length(cls, v: str) -> str:
        """Validate entity text length."""
        max_length = 1000  # 1KB max per entity text
        if len(v) > max_length:
            raise ValueError(
                f"Entity text exceeds maximum length of {max_length} characters"
            )
        if len(v.strip()) == 0:
            raise ValueError("Entity text cannot be empty")
        return v.strip()

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        """Validate entity type is one of the allowed values."""
        allowed_types = {"CONDITION", "DRUG", "MEASUREMENT", "PROCEDURE", "OBSERVATION"}
        v_upper = v.upper()
        if v_upper not in allowed_types:
            raise ValueError(
                f"Invalid entity_type '{v}'. Must be one of: {', '.join(sorted(allowed_types))}"
            )
        return v_upper

    @field_validator("assertion")
    @classmethod
    def validate_assertion(cls, v: str) -> str:
        """Validate assertion is one of the allowed values."""
        allowed_assertions = {"PRESENT", "ABSENT", "POSSIBLE", "CONDITIONAL", "HYPOTHETICAL"}
        v_upper = v.upper()
        if v_upper not in allowed_assertions:
            raise ValueError(
                f"Invalid assertion '{v}'. Must be one of: {', '.join(sorted(allowed_assertions))}"
            )
        return v_upper


class BuildGraphFromEntitiesRequest(BaseModel):
    """Request to build knowledge graph from pre-extracted entities."""

    patient_id: str = Field(..., description="Patient identifier")
    entities: list[ExtractedEntity] = Field(default_factory=list, max_length=5000, description="Pre-extracted entities")
    clinical_text: str | None = Field(default=None, description="Raw clinical text for extraction")
    extraction_method: str = Field(
        default="hybrid",
        description="Method used for extraction: rule_based, llm, hybrid"
    )

    @model_validator(mode="after")
    def require_entities_or_text(self) -> "BuildGraphFromEntitiesRequest":
        """At least one of entities or clinical_text must be provided."""
        if not self.entities and not self.clinical_text:
            raise ValueError("At least one of 'entities' (non-empty) or 'clinical_text' must be provided")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "patient_id": "TEST67890",
                "entities": [
                    {
                        "text": "sickle cell disease",
                        "entity_type": "CONDITION",
                        "confidence": 0.95,
                        "assertion": "PRESENT",
                        "omop_concept_id": 4322024,
                        "note_id": "frontend"
                    },
                    {
                        "text": "hydroxyurea",
                        "entity_type": "DRUG",
                        "confidence": 0.92,
                        "assertion": "PRESENT",
                        "omop_concept_id": 1305058,
                        "note_id": "frontend"
                    }
                ]
            }
        }
    }


class BuildGraphResponse(BaseModel):
    """Response from building graph from pre-extracted entities."""

    patient_id: str
    entities_processed: int
    knowledge_graph: KnowledgeGraphSummary
    processing_time_ms: float


class ImportedNote(BaseModel):
    """Result for a single imported note."""

    note_id: str
    document_id: UUID
    entity_count: int
    entities: list[ExtractedEntity]
    extraction_status: ExtractionStatus = Field(
        ExtractionStatus.OK,
        description="P0-006: Note-level extraction status (ok, partial, failed)",
    )


class BulkImportResponse(BaseModel):
    """Response from bulk document import."""

    patient_id: str
    total_notes: int
    total_entities: int
    notes: list[ImportedNote]
    knowledge_graph: KnowledgeGraphSummary | None = None
    processing_time_ms: float
    extraction_status: ExtractionStatus = Field(
        ExtractionStatus.OK,
        description="P0-006: Pipeline-level extraction status (ok, partial, failed)",
    )


class KnowledgeGraphSummary(BaseModel):
    """Summary of knowledge graph for a patient."""

    patient_id: str
    node_count: int
    edge_count: int
    conditions: list[str]
    medications: list[str]
    measurements: list[str]
    procedures: list[str]
    negated_conditions: list[str] = Field(default_factory=list, description="Conditions ruled out")
    extraction_method: str = Field(default="hybrid", description="Method used for extraction")
    merge_rejected_count: int = Field(
        default=0,
        description="P1-007: Number of entity merges rejected by provenance validation",
    )


class KGNodeResponse(BaseModel):
    """Knowledge graph node for API response."""

    id: str
    node_type: str
    label: str
    omop_concept_id: int | None
    properties: dict


class KGEdgeResponse(BaseModel):
    """Knowledge graph edge for API response."""

    id: str
    source_node_id: str  # Match frontend expected field name
    target_node_id: str  # Match frontend expected field name
    edge_type: str
    properties: dict
    # Temporal fields
    temporality: str | None = None
    temporal_order: str | None = None
    event_date: str | None = None


class PatientGraphResponse(BaseModel):
    """Complete patient knowledge graph."""

    patient_id: str
    nodes: list[KGNodeResponse]
    edges: list[KGEdgeResponse]
    summary: KnowledgeGraphSummary


class HybridQueryRequest(BaseModel):
    """Request for hybrid EHR + KG query."""

    question: str = Field(..., min_length=3, description="Natural language question")
    include_evidence: bool = Field(True, description="Include source evidence in response")
    max_results: int = Field(10, ge=1, le=50, description="Maximum results to return")

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What medications is the patient taking for diabetes?",
                "include_evidence": True,
                "max_results": 10
            }
        }
    }


class EvidenceSource(BaseModel):
    """Evidence from a clinical note."""

    note_id: str
    note_type: str
    note_date: str
    excerpt: str
    relevance_score: float


class HybridQueryResponse(BaseModel):
    """Response from hybrid query."""

    question: str
    answer: str
    confidence: float
    sources: list[str]
    entities_found: list[ExtractedEntity]
    evidence: list[EvidenceSource] = []
    knowledge_graph_paths: list[dict] = []
    reasoning: str | None = None
    guideline_citations: list[dict] = []
    query_id: str | None = None
    reasoning_chain: list[dict] = []
    entity_provenance: list[dict] = []
    policy_citations: list[dict] = []
    provenance_url: str | None = None
    # P0-022: Decline behavior when evidence is insufficient
    declined: bool = False
    decline_reason: str | None = None
    escalation_path: str | None = None
    # P0-023: Mandatory provenance for every non-empty answer
    source_document_ids: list[str] = []
    provenance_complete: bool = True
    dependency_state: dict[str, bool] = Field(
        default_factory=dict,
        description="P0-004: Availability flags for KG, document store, and LLM dependencies",
    )
    action_gate: dict | None = Field(
        default=None,
        description="P0-021: Confidence-to-action gate result",
    )
    # P1-001: Evidence-weighted confidence rationale
    confidence_rationale: str | None = Field(
        default=None,
        description="P1-001: Human-readable explanation of how confidence was computed",
    )
    # P1-002: Structured confidence breakdown
    confidence_breakdown: ConfidenceBreakdown | None = Field(
        default=None,
        description="P1-002: Structured breakdown of confidence components",
    )
    # P1-005: Note processing coverage metrics
    notes_processed: int = Field(
        default=0,
        description="P1-005: Number of clinical notes successfully processed",
    )
    notes_failed: int = Field(
        default=0,
        description="P1-005: Number of clinical notes that failed processing",
    )
    coverage_percent: float = Field(
        default=100.0,
        description="P1-005: Percentage of available notes successfully processed",
    )
    # P1-006: Data freshness and ingestion timestamp
    data_freshness_iso: str | None = Field(
        default=None,
        description="P1-006: ISO-8601 timestamp of the most recently ingested document",
    )
    last_ingestion_ts: str | None = Field(
        default=None,
        description="P1-006: ISO-8601 timestamp of the last document ingestion run",
    )
    # P1-019: Fallback indicator for degraded responses
    fallback_used: bool = Field(
        default=False,
        description="P1-019: True when a fallback path was taken instead of the primary path",
    )
    fallback_reason_code: str | None = Field(
        default=None,
        description="P1-019: Machine-readable reason code for fallback (e.g. 'llm_unavailable')",
    )
    # P2-007: Uncertainty reason codes
    uncertainty_reasons: list[str] = Field(
        default_factory=list,
        description="P2-007: Applicable uncertainty reason codes (e.g. UC-001)",
    )
    # P2-019: Query budget time breakdown
    query_budget_ms: dict[str, float] | None = Field(
        default=None,
        description="P2-019: Time spent per query phase in milliseconds",
    )
    # Phase 1 Safety Envelope: Degradation tracking
    degradation: DegradationMetadata | None = None


# =============================================================================
# Helper Functions
# =============================================================================


def compute_evidence_weighted_confidence(
    kg_node_count: int,
    document_count: int,
    guideline_count: int,
    extraction_quality: float,
    graph_path_count: int = 0,
    consensus_strong_count: int = 0,
    calculator_count: int = 0,
) -> tuple[float, str]:
    """P1-001: Compute evidence-weighted confidence with rationale.

    Returns (score, rationale_string).
    """
    weights = {
        "kg_nodes": 0.25,
        "documents": 0.25,
        "guidelines": 0.15,
        "extraction_quality": 0.15,
        "graph_paths": 0.10,
        "consensus": 0.05,
        "calculators": 0.05,
    }

    # Normalize counts to 0-1 scores (diminishing returns via min/cap)
    kg_score = min(kg_node_count * 0.05, 1.0)
    doc_score = min(document_count * 0.15, 1.0)
    guideline_score = min(guideline_count * 0.25, 1.0)
    extraction_score = min(max(extraction_quality, 0.0), 1.0)
    graph_path_score = min(graph_path_count * 0.10, 1.0)
    consensus_score = min(consensus_strong_count * 0.30, 1.0)
    calculator_score = min(calculator_count * 0.30, 1.0)

    weighted_sum = (
        kg_score * weights["kg_nodes"]
        + doc_score * weights["documents"]
        + guideline_score * weights["guidelines"]
        + extraction_score * weights["extraction_quality"]
        + graph_path_score * weights["graph_paths"]
        + consensus_score * weights["consensus"]
        + calculator_score * weights["calculators"]
    )

    # Apply base offset and cap
    score = min(0.95, 0.4 + weighted_sum * 0.55)

    parts: list[str] = []
    parts.append(f"{kg_node_count} KG nodes ({weights['kg_nodes']})")
    parts.append(f"{document_count} documents ({weights['documents']})")
    parts.append(f"{guideline_count} guidelines ({weights['guidelines']})")
    parts.append(f"extraction quality {extraction_score:.2f} ({weights['extraction_quality']})")
    if graph_path_count:
        parts.append(f"{graph_path_count} graph paths ({weights['graph_paths']})")
    if consensus_strong_count:
        parts.append(f"{consensus_strong_count} strong consensus ({weights['consensus']})")
    if calculator_count:
        parts.append(f"{calculator_count} calculators ({weights['calculators']})")

    rationale = f"evidence_weighted: {', '.join(parts)}"
    return round(score, 4), rationale


def _domain_to_node_type(domain: str) -> NodeType:
    """Map domain string to NodeType."""
    mapping = {
        "CONDITION": NodeType.CONDITION,
        "DRUG": NodeType.DRUG,
        "MEASUREMENT": NodeType.MEASUREMENT,
        "PROCEDURE": NodeType.PROCEDURE,
        "OBSERVATION": NodeType.OBSERVATION,
    }
    return mapping.get(domain.upper(), NodeType.OBSERVATION)


def _node_type_to_edge_type(node_type: NodeType) -> EdgeType:
    """Map node type to patient edge type."""
    mapping = {
        NodeType.CONDITION: EdgeType.HAS_CONDITION,
        NodeType.DRUG: EdgeType.TAKES_DRUG,
        NodeType.MEASUREMENT: EdgeType.HAS_MEASUREMENT,
        NodeType.PROCEDURE: EdgeType.HAS_PROCEDURE,
        NodeType.OBSERVATION: EdgeType.HAS_OBSERVATION,
    }
    return mapping.get(node_type, EdgeType.HAS_OBSERVATION)


def _assertion_to_temporality(assertion: str) -> str:
    """Map assertion status to temporality for bi-temporal tracking.

    Must return a valid Temporality enum value (current, past, future).
    Assertion semantics (negated, possible) are stored separately in edge properties.
    """
    mapping = {
        "PRESENT": "current",
        "ABSENT": "current",       # Negation tracked via assertion in edge properties
        "POSSIBLE": "current",     # Uncertainty tracked via assertion in edge properties
        "CONDITIONAL": "future",
        "HYPOTHETICAL": "future",
        "HISTORICAL": "past",
    }
    return mapping.get(assertion.upper(), "current")


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse date string to datetime object.

    Supports common date formats:
    - ISO 8601: 2024-01-15, 2024-01-15T10:30:00
    - US format: 01/15/2024, 1/15/2024
    - Clinical format: 15-Jan-2024, Jan 15, 2024
    """
    if not date_str:
        return None

    from dateutil import parser

    try:
        parsed = parser.parse(date_str)
        # Ensure timezone awareness
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError):
        logger.warning(f"Could not parse date: {date_str}")
        return None


def _normalize_measurement_text(text: str) -> str:
    """Normalize measurement text for concept lookup.

    Extracts the lab/measurement name from text that may include values.
    Examples:
        "BUN 26 mg/dL: 26mg/dL" -> "BUN"
        "HbA1c 6.1%: 6.1%" -> "HbA1c"
        "Glucose 112 mg/dL" -> "Glucose"
        "eGFR 50 mL/min" -> "eGFR"
        "WBC 8.2 K/uL" -> "WBC"
    """
    import re

    # Common lab name patterns to extract
    # Pattern: starts with letters/numbers, ends before first number with unit
    # e.g., "BUN 26" -> "BUN", "HbA1c 6.1%" -> "HbA1c"

    # First, try to extract just the lab name (before colon if present)
    if ":" in text:
        text = text.split(":")[0].strip()

    # Remove trailing values: number followed by optional unit
    # Matches patterns like "26 mg/dL", "6.1%", "50 mL/min", "8.2 K/uL"
    cleaned = re.sub(r"\s+[\d.,]+\s*[%a-zA-Z/]*\s*$", "", text).strip()

    # If we removed everything, return the first word
    if not cleaned:
        cleaned = text.split()[0] if text.split() else text

    # Common abbreviation mappings for better matching
    lab_mappings = {
        "a1c": "Hemoglobin A1c",
        "hba1c": "Hemoglobin A1c",
        "hgb": "Hemoglobin",
        "wbc": "Leukocytes",
        "plt": "Platelet count",
        "bun": "Blood urea nitrogen",
        "cr": "Creatinine",
        "egfr": "Glomerular filtration rate",
        "na": "Sodium",
        "k": "Potassium",
        "cl": "Chloride",
        "co2": "Carbon dioxide",
        "aptt": "Activated partial thromboplastin time",
        "inr": "INR",
        "pt": "Prothrombin time",
    }

    # Check if the cleaned text matches a common abbreviation
    lower_cleaned = cleaned.lower()
    if lower_cleaned in lab_mappings:
        return lab_mappings[lower_cleaned]

    return cleaned


# OMOP relationship types that create entity-to-entity edges
# Maps OMOP relationship_id to EdgeType (None = skip this relationship)
OMOP_CLINICAL_RELATIONSHIPS = {
    # Drug-Condition treatment relationships (67K+ loaded)
    "May treat": EdgeType.DRUG_TREATS,
    "May be treated by": EdgeType.CONDITION_TREATED_BY,
    "Treats of": EdgeType.DRUG_TREATS,
    "Indication of": EdgeType.DRUG_TREATS,
    # Contraindication relationships (41K+ loaded)
    "CI to": EdgeType.CONTRAINDICATED_WITH,
    "CI by": EdgeType.CONTRAINDICATED_WITH,
    # Drug-Drug interaction relationships (22K+ loaded)
    "Has drug-drug inter": EdgeType.DRUG_INTERACTION,
    "Drug-drug inter for": EdgeType.DRUG_INTERACTION,
    # Skip these relationships for entity edges
    "Ingredient of": None,
    "Tradename of": None,
    "Has tradename": None,
    "Is a": None,
    "Subsumes": None,
    "Maps to": None,
    "Mapped from": None,
}


def _get_narrative_context(nodes: list) -> str:
    """Extract narrative context from knowledge graph nodes for LLM.

    Looks for narrative node types (ADMISSION, HOSPITAL_COURSE, CLINICAL_EVENT,
    DISCHARGE, EPISODE) and formats them for inclusion in LLM prompts.

    Args:
        nodes: List of KGNode objects from the knowledge graph

    Returns:
        Formatted string with narrative context, or empty string if no narrative nodes
    """
    narrative_parts = []

    # Find admission node
    admission_nodes = [n for n in nodes if n.node_type == NodeType.ADMISSION]
    for admission in admission_nodes:
        props = admission.properties or {}
        primary_problem = props.get("primary_problem", admission.label)
        contributing = props.get("contributing_factors", [])
        symptoms = props.get("presenting_symptoms", [])
        admission_date = props.get("admission_date", "unknown date")

        narrative_parts.append(f"ADMISSION ({admission_date}):")
        narrative_parts.append(f"  Primary reason: {primary_problem}")
        if contributing:
            narrative_parts.append(f"  Contributing factors: {', '.join(contributing)}")
        if symptoms:
            narrative_parts.append(f"  Presenting symptoms: {', '.join(symptoms)}")

    # Find hospital course node
    course_nodes = [n for n in nodes if n.node_type == NodeType.HOSPITAL_COURSE]
    for course in course_nodes:
        props = course.properties or {}
        summary = props.get("summary", "")
        interventions = props.get("interventions", [])
        complications = props.get("complications", [])
        response = props.get("response_to_treatment", "")
        los = props.get("length_of_stay_days")

        narrative_parts.append("\nHOSPITAL COURSE:")
        if summary:
            narrative_parts.append(f"  Summary: {summary}")
        if interventions:
            narrative_parts.append(f"  Interventions: {', '.join(interventions)}")
        if complications:
            narrative_parts.append(f"  Complications: {', '.join(complications)}")
        if response:
            narrative_parts.append(f"  Response to treatment: {response}")
        if los:
            narrative_parts.append(f"  Length of stay: {los} days")

    # Find clinical events (sorted by relative_day if available)
    event_nodes = [n for n in nodes if n.node_type == NodeType.CLINICAL_EVENT]
    event_nodes_sorted = sorted(
        event_nodes,
        key=lambda x: (x.properties or {}).get("relative_day") or 999
    )
    if event_nodes_sorted:
        narrative_parts.append("\nKEY EVENTS:")
        for event in event_nodes_sorted:
            props = event.properties or {}
            event_text = event.label
            event_type = props.get("event_type", "event")
            day = props.get("relative_day")
            severity = props.get("severity", "")

            day_str = f"Day {day}: " if day else ""
            severity_str = f" ({severity})" if severity else ""
            narrative_parts.append(f"  {day_str}[{event_type}] {event_text}{severity_str}")

    # Find discharge node
    discharge_nodes = [n for n in nodes if n.node_type == NodeType.DISCHARGE]
    for discharge in discharge_nodes:
        props = discharge.properties or {}
        disposition = props.get("disposition", "")
        discharge_date = props.get("discharge_date", "")
        follow_up = props.get("follow_up_appointments", [])
        restrictions = props.get("activity_restrictions", [])
        precautions = props.get("return_precautions", [])

        narrative_parts.append("\nDISCHARGE:")
        if disposition:
            narrative_parts.append(f"  Disposition: {disposition}")
        if discharge_date:
            narrative_parts.append(f"  Date: {discharge_date}")
        if follow_up:
            narrative_parts.append(f"  Follow-up: {', '.join(follow_up)}")
        if restrictions:
            narrative_parts.append(f"  Activity restrictions: {', '.join(restrictions)}")
        if precautions:
            narrative_parts.append(f"  Return if: {', '.join(precautions)}")

    if narrative_parts:
        return "Clinical Narrative:\n" + "\n".join(narrative_parts)
    return ""


async def _query_omop_relationships(
    db: AsyncSession,
    entity_concept_ids: dict[int, str],  # omop_concept_id -> node_id
) -> list[tuple[str, str, str, str]]:
    """Query OMOP ConceptRelationship table for relationships between entities.

    Args:
        db: Database session
        entity_concept_ids: Mapping of OMOP concept IDs to node IDs

    Returns:
        List of (source_node_id, target_node_id, relationship_type, edge_type) tuples
    """
    if len(entity_concept_ids) < 2:
        return []

    concept_ids = list(entity_concept_ids.keys())
    relationships = []

    try:
        # Query relationships where both concepts are in our entity set
        # Select only columns that exist in the table
        result = await db.execute(
            select(
                ConceptRelationship.concept_id_1,
                ConceptRelationship.concept_id_2,
                ConceptRelationship.relationship_id,
            ).where(
                and_(
                    ConceptRelationship.concept_id_1.in_(concept_ids),
                    ConceptRelationship.concept_id_2.in_(concept_ids),
                    # Note: Table doesn't have invalid_reason column, all loaded relationships are valid
                )
            )
        )
        rows = result.fetchall()

        for row in rows:
            concept_id_1, concept_id_2, rel_type = row[0], row[1], row[2]

            # Check if this is a clinical relationship we want to create edges for
            if rel_type in OMOP_CLINICAL_RELATIONSHIPS:
                edge_type = OMOP_CLINICAL_RELATIONSHIPS[rel_type]
                if edge_type is not None:
                    source_node = entity_concept_ids.get(concept_id_1)
                    target_node = entity_concept_ids.get(concept_id_2)

                    if source_node and target_node:
                        relationships.append((
                            source_node,
                            target_node,
                            rel_type,
                            edge_type,
                        ))

        logger.info(f"Found {len(relationships)} OMOP relationships between {len(concept_ids)} entities")

    except Exception as e:
        DegradationContext.record_stage_failure("omop_relationships", e, [])
        logger.warning(f"Failed to query OMOP relationships: {e}")

    return relationships


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "/import",
    response_model=BulkImportResponse,
    summary="Bulk import clinical documents",
    description="Import multiple clinical notes, extract entities via NLP, and optionally build knowledge graph.",
)
async def bulk_import_documents(
    request: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.WRITE_DOCUMENTS])),
) -> BulkImportResponse:
    """Bulk import clinical documents with NLP processing.

    This endpoint:
    1. Stores all documents in the database
    2. Runs NLP extraction on each document
    3. Optionally builds a patient knowledge graph
    """
    start_time = datetime.now(timezone.utc)

    # Initialize NLP service
    nlp_service = RuleBasedNLPService()

    imported_notes: list[ImportedNote] = []
    all_entities: list[ExtractedEntity] = []

    # Process each note
    failed_extractions = 0
    for note in request.notes:
        # Create document record
        doc_id = str(uuid4())
        db_document = DocumentModel(
            id=doc_id,
            patient_id=request.patient_id,
            note_type=note.note_type,
            text=note.text,
            extra_metadata={
                **note.metadata,
                "original_note_id": note.note_id,
                "note_date": note.date,
            },
            status=JobStatus.COMPLETED,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(db_document)

        # Extract entities using NLP
        try:
            mentions = nlp_service.extract_mentions(note.text, doc_id)

            # Phase 4: Extract temporal expressions if enabled
            entity_dates: dict[str, datetime] = {}
            if settings.enable_temporal_extraction and mentions:
                try:
                    # Parse document date if available
                    doc_date = None
                    if note.date:
                        try:
                            doc_date = datetime.strptime(note.date, "%Y-%m-%d")
                        except ValueError:
                            pass

                    # Build entity list for temporal binding
                    entity_info = [
                        {
                            "text": m.text,
                            "start": m.start_offset,
                            "end": m.end_offset,
                        }
                        for m in mentions
                    ]

                    # Extract dates and bind to entities
                    entity_dates = extract_entity_dates(note.text, entity_info, doc_date)
                    if entity_dates:
                        logger.debug(f"Extracted {len(entity_dates)} temporal bindings for note {note.note_id}")
                except Exception as te:
                    DegradationContext.record_stage_failure("temporal_extraction", te, {})
                    logger.warning(f"Temporal extraction failed for note {note.note_id}: {te}")

            note_entities: list[ExtractedEntity] = []
            for mention in mentions:
                # Map domain_hint to entity_type (Condition, Drug, etc.)
                domain = getattr(mention, 'domain_hint', None) or 'OBSERVATION'
                entity_type = domain.upper() if domain else 'OBSERVATION'

                # Get extracted date for this entity if available
                event_date_str = None
                if mention.text in entity_dates:
                    event_date_str = entity_dates[mention.text].isoformat()

                entity = ExtractedEntity(
                    text=mention.text,
                    entity_type=entity_type,
                    confidence=mention.confidence,
                    assertion=str(getattr(mention, 'assertion', 'PRESENT')),
                    omop_concept_id=getattr(mention, 'omop_concept_id', None),
                    note_id=note.note_id,
                    event_date=event_date_str,
                    document_date=note.date,
                )
                note_entities.append(entity)
                all_entities.append(entity)

                # Store mention in database
                # Get enum values properly (strip "EnumName." prefix if present)
                assertion_val = getattr(mention, 'assertion', 'PRESENT')
                if hasattr(assertion_val, 'value'):
                    assertion_val = assertion_val.value
                else:
                    assertion_val = str(assertion_val).split('.')[-1]  # "Assertion.PRESENT" -> "PRESENT"

                temporality_val = getattr(mention, 'temporality', 'CURRENT')
                if hasattr(temporality_val, 'value'):
                    temporality_val = temporality_val.value
                else:
                    temporality_val = str(temporality_val).split('.')[-1]

                experiencer_val = getattr(mention, 'experiencer', 'PATIENT')
                if hasattr(experiencer_val, 'value'):
                    experiencer_val = experiencer_val.value
                else:
                    experiencer_val = str(experiencer_val).split('.')[-1]

                db_mention = MentionModel(
                    id=str(uuid4()),
                    document_id=doc_id,
                    text=mention.text,
                    start_offset=mention.start_offset,
                    end_offset=mention.end_offset,
                    lexical_variant=mention.text.lower(),
                    section=getattr(mention, 'section', None),
                    assertion=assertion_val,
                    temporality=temporality_val,
                    experiencer=experiencer_val,
                    confidence=mention.confidence,
                )
                db.add(db_mention)

            imported_notes.append(ImportedNote(
                note_id=note.note_id,
                document_id=UUID(doc_id),
                entity_count=len(note_entities),
                entities=note_entities,
            ))

        except Exception as e:
            DegradationContext.record_stage_failure("nlp_extraction", e, [])
            failed_extractions += 1
            logger.error(f"NLP extraction failed for note {note.note_id}: {e}")
            imported_notes.append(ImportedNote(
                note_id=note.note_id,
                document_id=UUID(doc_id),
                entity_count=0,
                entities=[],
                extraction_status=ExtractionStatus.FAILED,
            ))

    if failed_extractions > 0:
        DegradationContext.record_stage_failure(
            "bulk_nlp_extraction",
            RuntimeError(f"{failed_extractions} of {len(request.notes)} extraction(s) failed"),
            None,
        )

    # Commit documents and mentions
    await db.commit()

    # Step 9: Create provenance records for extracted entities
    try:
        provenance_svc = get_provenance_db_service()
        for entity in all_entities:
            # Find the document ID for this entity's note
            source_doc_id = None
            for imp_note in imported_notes:
                if imp_note.note_id == entity.note_id:
                    source_doc_id = str(imp_note.document_id)
                    break

            await provenance_svc.create_provenance_record(
                session=db,
                entity_type="kg_node",
                entity_id=f"{request.patient_id}:{entity.text.lower()}:{entity.entity_type}",
                patient_id=request.patient_id,
                extraction_method="nlp_rule_based",
                confidence_level="high" if entity.confidence >= 0.8 else "medium" if entity.confidence >= 0.5 else "low",
                confidence_score=entity.confidence,
                source_document_id=source_doc_id,
                extracted_text=entity.text,
                metadata={
                    "entity_type": entity.entity_type,
                    "assertion": entity.assertion,
                    "omop_concept_id": entity.omop_concept_id,
                    "note_id": entity.note_id,
                },
            )
        await db.flush()
    except Exception as e:
        DegradationContext.record_stage_failure("entity_provenance", e, None)
        logger.warning(f"Failed to create entity provenance records: {e}")

    # P0-006: Compute pipeline-level extraction status
    failed_notes = [
        n for n in imported_notes if n.extraction_status == ExtractionStatus.FAILED
    ]
    if len(failed_notes) == len(imported_notes):
        pipeline_extraction_status = ExtractionStatus.FAILED
    elif len(failed_notes) > 0:
        pipeline_extraction_status = ExtractionStatus.PARTIAL
    else:
        pipeline_extraction_status = ExtractionStatus.OK

    # Build knowledge graph if requested
    kg_summary = None
    if request.build_knowledge_graph:
        # P0-005: Block graph build when extraction has note-level failures
        if pipeline_extraction_status == ExtractionStatus.FAILED:
            logger.warning(
                "P0-005: Blocking graph build for patient %s — "
                "all %d notes failed extraction",
                request.patient_id,
                len(failed_notes),
            )
        elif pipeline_extraction_status == ExtractionStatus.PARTIAL:
            logger.warning(
                "P0-005: Blocking graph build for patient %s — "
                "%d/%d notes failed extraction. "
                "Partial extraction cannot produce complete graph.",
                request.patient_id,
                len(failed_notes),
                len(imported_notes),
            )
        else:
            kg_summary = await _build_patient_knowledge_graph(
                db, request.patient_id, all_entities
            )
            await db.commit()

    end_time = datetime.now(timezone.utc)
    processing_time_ms = (end_time - start_time).total_seconds() * 1000

    return BulkImportResponse(
        patient_id=request.patient_id,
        total_notes=len(request.notes),
        total_entities=len(all_entities),
        notes=imported_notes,
        knowledge_graph=kg_summary,
        processing_time_ms=round(processing_time_ms, 2),
        extraction_status=pipeline_extraction_status,
    )


@router.post(
    "/build-graph",
    response_model=BuildGraphResponse,
    summary="Build knowledge graph from pre-extracted entities",
    description="Build a patient knowledge graph using entities already extracted by the frontend NLP.",
)
async def build_graph_from_entities(
    request: BuildGraphFromEntitiesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.WRITE_CLINICAL_FACTS])),
) -> BuildGraphResponse:
    """Build knowledge graph from pre-extracted entities.

    This endpoint accepts entities that have already been extracted by the frontend
    NLP service, allowing the richer extraction results to be used for graph building.
    """
    start_time = datetime.now(timezone.utc)

    try:
        all_entities = list(request.entities)

        # If clinical_text provided, do additional rule-based extraction
        # to capture entities the frontend might have missed
        if request.clinical_text:
            try:
                rule_nlp = RuleBasedNLPService()
                mentions = rule_nlp.extract_mentions(request.clinical_text, document_id=uuid4())
                # Map domain_hint from ExtractedMention to KG entity types
                domain_map = {
                    "Condition": "CONDITION",
                    "Drug": "DRUG",
                    "Procedure": "PROCEDURE",
                    "Measurement": "MEASUREMENT",
                    "Observation": "OBSERVATION",
                }
                existing_texts = {e.text.lower() for e in all_entities}
                for m in mentions:
                    kg_type = domain_map.get(m.domain_hint or "", "OBSERVATION")
                    if m.text.lower() not in existing_texts:
                        assertion_str = "ABSENT" if m.assertion.value == "absent" else "PRESENT"
                        all_entities.append(ExtractedEntity(
                            text=m.text,
                            entity_type=kg_type,
                            confidence=m.confidence,
                            assertion=assertion_str,
                            omop_concept_id=m.omop_concept_id,
                            note_id="rule_based_supplement",
                            document_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        ))
                        existing_texts.add(m.text.lower())
                logger.info(f"Supplemental extraction added {len(all_entities) - len(request.entities)} entities from clinical text")
            except Exception as text_err:
                DegradationContext.record_stage_failure("supplemental_extraction", text_err, [])
                logger.warning(f"Supplemental text extraction failed: {text_err}")

        # Build the knowledge graph from all entities
        kg_summary = await _build_patient_knowledge_graph(
            db, request.patient_id, all_entities, request.extraction_method
        )
        await db.commit()
    except Exception as e:
        DegradationContext.record_stage_failure("graph_build", e, None)
        await db.rollback()
        logger.error(f"Failed to build graph for patient {request.patient_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build knowledge graph: {str(e)}"
        )

    end_time = datetime.now(timezone.utc)
    processing_time_ms = (end_time - start_time).total_seconds() * 1000

    return BuildGraphResponse(
        patient_id=request.patient_id,
        entities_processed=len(all_entities),
        knowledge_graph=kg_summary,
        processing_time_ms=round(processing_time_ms, 2),
    )


def _validate_narrative_grounding(
    link_text: str,
    link_type: str,
    seen_entities: dict[str, str],
    entity_type_filter: str | None = None,
) -> str | None:
    """P0-007: Validate that a narrative link is grounded in pre-extracted entities.

    Returns the matched entity node_id if grounded, or None if ungrounded.
    Logs rejected (ungrounded) links with a reason code.
    """
    link_text_lower = link_text.lower()
    for entity_key, entity_node_id in seen_entities.items():
        if entity_type_filter and f"|{entity_type_filter}" not in entity_key:
            continue
        if link_text_lower in entity_key.lower():
            return entity_node_id

    # P0-007: Ungrounded link — reject with reason code
    logger.warning(
        "P0-007 UNGROUNDED_LINK: Rejecting narrative link "
        "type=%s text=%r — not traceable to any pre-extracted entity "
        "(entity_type_filter=%s, available_entities=%d)",
        link_type,
        link_text,
        entity_type_filter,
        len(seen_entities),
    )
    return None


async def _create_narrative_nodes(
    db: AsyncSession,
    patient_id: str,
    patient_node_id: str,
    narrative: dict,
    seen_entities: dict[str, str],
    now: datetime,
) -> dict:
    """Create narrative nodes and edges from extracted clinical narrative.

    Creates:
    - Episode node (container for the hospitalization)
    - Admission node with ADMITTED_FOR edges to conditions
    - Clinical event nodes with PRECEDES/FOLLOWS temporal edges
    - Hospital course node
    - Discharge node with DISCHARGED_WITH edges

    P0-007: All entity-linking edges are validated for narrative grounding.
    Ungrounded links (not traceable to source narrative) are rejected with a
    reason code logged.

    Returns:
        Dict with node_count and edge_count created
    """
    node_count = 0
    edge_count = 0

    # Create episode node (container for the hospitalization)
    episode_node_id = str(uuid4())
    episode_node = KGNode(
        id=episode_node_id,
        patient_id=patient_id,
        node_type=NodeType.EPISODE,
        label="Hospitalization Episode",
        properties={
            "created_at": now.isoformat(),
            "narrative_source": True,
        },
    )
    db.add(episode_node)
    node_count += 1

    # Link episode to patient
    episode_edge = KGEdge(
        id=str(uuid4()),
        patient_id=patient_id,
        source_node_id=patient_node_id,
        target_node_id=episode_node_id,
        edge_type=EdgeType.HAS_EPISODE,
        properties={"narrative_source": True},
    )
    db.add(episode_edge)
    edge_count += 1

    # Create admission node if admission reason is provided
    admission_node_id = None
    if admission_reason := narrative.get("admission_reason"):
        admission_node_id = str(uuid4())
        admission_node = KGNode(
            id=admission_node_id,
            patient_id=patient_id,
            node_type=NodeType.ADMISSION,
            label=admission_reason.get("primary_problem", "Admission"),
            properties={
                "primary_problem": admission_reason.get("primary_problem"),
                "contributing_factors": admission_reason.get("contributing_factors", []),
                "presenting_symptoms": admission_reason.get("presenting_symptoms", []),
                "admission_date": admission_reason.get("admission_date"),
                "admission_source": admission_reason.get("admission_source"),
                "narrative_source": True,
            },
        )
        db.add(admission_node)
        node_count += 1

        # Link admission to episode
        admission_episode_edge = KGEdge(
            id=str(uuid4()),
            patient_id=patient_id,
            source_node_id=admission_node_id,
            target_node_id=episode_node_id,
            edge_type=EdgeType.PART_OF_EPISODE,
            properties={"narrative_source": True},
        )
        db.add(admission_episode_edge)
        edge_count += 1

        # Create ADMITTED_FOR edges to linked conditions
        # P0-007: Validate grounding before creating edges
        for condition_text in admission_reason.get("linked_condition_texts", []):
            grounded_node_id = _validate_narrative_grounding(
                condition_text, "ADMITTED_FOR", seen_entities, "CONDITION"
            )
            if grounded_node_id:
                admitted_for_edge = KGEdge(
                    id=str(uuid4()),
                    patient_id=patient_id,
                    source_node_id=admission_node_id,
                    target_node_id=grounded_node_id,
                    edge_type=EdgeType.ADMITTED_FOR,
                    properties={"linked_text": condition_text, "narrative_source": True},
                )
                db.add(admitted_for_edge)
                edge_count += 1

    # Create hospital course node and clinical events
    prev_event_node_id = admission_node_id  # For temporal ordering
    if hospital_course := narrative.get("hospital_course"):
        # Create hospital course summary node
        course_node_id = str(uuid4())
        course_node = KGNode(
            id=course_node_id,
            patient_id=patient_id,
            node_type=NodeType.HOSPITAL_COURSE,
            label="Hospital Course",
            properties={
                "summary": hospital_course.get("summary"),
                "interventions": hospital_course.get("interventions", []),
                "complications": hospital_course.get("complications", []),
                "response_to_treatment": hospital_course.get("response_to_treatment"),
                "length_of_stay_days": hospital_course.get("length_of_stay_days"),
                "narrative_source": True,
            },
        )
        db.add(course_node)
        node_count += 1

        # Link course to episode
        course_episode_edge = KGEdge(
            id=str(uuid4()),
            patient_id=patient_id,
            source_node_id=course_node_id,
            target_node_id=episode_node_id,
            edge_type=EdgeType.PART_OF_EPISODE,
            properties={"narrative_source": True},
        )
        db.add(course_episode_edge)
        edge_count += 1

        # Create clinical event nodes with temporal ordering
        for event_data in hospital_course.get("key_events", []):
            event_node_id = str(uuid4())
            event_node = KGNode(
                id=event_node_id,
                patient_id=patient_id,
                node_type=NodeType.CLINICAL_EVENT,
                label=event_data.get("event_text", "Clinical Event"),
                properties={
                    "event_type": event_data.get("event_type"),
                    "event_date": event_data.get("event_date"),
                    "relative_day": event_data.get("relative_day"),
                    "severity": event_data.get("severity"),
                    "narrative_source": True,
                },
            )
            db.add(event_node)
            node_count += 1

            # Link event to episode
            event_episode_edge = KGEdge(
                id=str(uuid4()),
                patient_id=patient_id,
                source_node_id=event_node_id,
                target_node_id=episode_node_id,
                edge_type=EdgeType.PART_OF_EPISODE,
                properties={"narrative_source": True},
            )
            db.add(event_episode_edge)
            edge_count += 1

            # Create PRECEDES/FOLLOWS temporal edges
            if prev_event_node_id:
                precedes_edge = KGEdge(
                    id=str(uuid4()),
                    patient_id=patient_id,
                    source_node_id=prev_event_node_id,
                    target_node_id=event_node_id,
                    edge_type=EdgeType.PRECEDES,
                    properties={"temporal_ordering": True, "narrative_source": True},
                )
                db.add(precedes_edge)
                edge_count += 1

            # Create CAUSED_BY edge if specified
            # P0-007: Validate grounding before creating causal edges
            if caused_by := event_data.get("caused_by"):
                grounded_cause_id = _validate_narrative_grounding(
                    caused_by, "CAUSED_BY", seen_entities
                )
                if grounded_cause_id:
                    caused_by_edge = KGEdge(
                        id=str(uuid4()),
                        patient_id=patient_id,
                        source_node_id=event_node_id,
                        target_node_id=grounded_cause_id,
                        edge_type=EdgeType.CAUSED_BY,
                        properties={"cause_text": caused_by, "narrative_source": True},
                    )
                    db.add(caused_by_edge)
                    edge_count += 1

            # Create RESULTED_IN edge if specified
            # P0-007: Validate grounding before creating result edges
            if resulted_in := event_data.get("resulted_in"):
                grounded_result_id = _validate_narrative_grounding(
                    resulted_in, "RESULTED_IN", seen_entities
                )
                if grounded_result_id:
                    resulted_in_edge = KGEdge(
                        id=str(uuid4()),
                        patient_id=patient_id,
                        source_node_id=event_node_id,
                        target_node_id=grounded_result_id,
                        edge_type=EdgeType.RESULTED_IN,
                        properties={"result_text": resulted_in, "narrative_source": True},
                    )
                    db.add(resulted_in_edge)
                    edge_count += 1

            prev_event_node_id = event_node_id

    # Create discharge node if discharge plan is provided
    if discharge_plan := narrative.get("discharge_plan"):
        discharge_node_id = str(uuid4())
        discharge_node = KGNode(
            id=discharge_node_id,
            patient_id=patient_id,
            node_type=NodeType.DISCHARGE,
            label=f"Discharge: {discharge_plan.get('disposition', 'Unknown')}",
            properties={
                "disposition": discharge_plan.get("disposition"),
                "discharge_date": discharge_plan.get("discharge_date"),
                "follow_up_appointments": discharge_plan.get("follow_up_appointments", []),
                "activity_restrictions": discharge_plan.get("activity_restrictions", []),
                "diet_instructions": discharge_plan.get("diet_instructions"),
                "wound_care": discharge_plan.get("wound_care"),
                "return_precautions": discharge_plan.get("return_precautions", []),
                "pending_results": discharge_plan.get("pending_results", []),
                "narrative_source": True,
            },
        )
        db.add(discharge_node)
        node_count += 1

        # Link discharge to episode
        discharge_episode_edge = KGEdge(
            id=str(uuid4()),
            patient_id=patient_id,
            source_node_id=discharge_node_id,
            target_node_id=episode_node_id,
            edge_type=EdgeType.PART_OF_EPISODE,
            properties={"narrative_source": True},
        )
        db.add(discharge_episode_edge)
        edge_count += 1

        # Create PRECEDES edge from last event to discharge
        if prev_event_node_id:
            discharge_precedes_edge = KGEdge(
                id=str(uuid4()),
                patient_id=patient_id,
                source_node_id=prev_event_node_id,
                target_node_id=discharge_node_id,
                edge_type=EdgeType.PRECEDES,
                properties={"temporal_ordering": True, "narrative_source": True},
            )
            db.add(discharge_precedes_edge)
            edge_count += 1

        # Create DISCHARGED_WITH edges to discharge medications
        for med_text in discharge_plan.get("discharge_medications", []):
            med_text_lower = med_text.lower()
            for entity_key, entity_node_id in seen_entities.items():
                if "|DRUG" in entity_key and med_text_lower in entity_key.lower():
                    discharged_with_edge = KGEdge(
                        id=str(uuid4()),
                        patient_id=patient_id,
                        source_node_id=discharge_node_id,
                        target_node_id=entity_node_id,
                        edge_type=EdgeType.DISCHARGED_WITH,
                        properties={"medication_text": med_text, "narrative_source": True},
                    )
                    db.add(discharged_with_edge)
                    edge_count += 1
                    break

    logger.info(f"Created {node_count} narrative nodes and {edge_count} narrative edges")
    return {"node_count": node_count, "edge_count": edge_count}


async def _build_patient_knowledge_graph(
    db: AsyncSession,
    patient_id: str,
    entities: list[ExtractedEntity],
    extraction_method: str = "hybrid",
    narrative: dict | None = None,
) -> KnowledgeGraphSummary:
    """Build knowledge graph from extracted entities.

    Integrates:
    - Temporal fields (temporality, recorded_at)
    - Provenance tracking (extraction_method, source_notes)
    - Assertion classification (includes negated entities with proper marking)
    - Clinical narrative nodes (admission, course, events, discharge)
    """
    now = datetime.now(timezone.utc)

    # Clear existing graph for this patient
    await db.execute(
        delete(KGEdge).where(KGEdge.patient_id == patient_id)
    )
    await db.execute(
        delete(KGNode).where(KGNode.patient_id == patient_id)
    )

    # Create patient node
    patient_node_id = str(uuid4())
    patient_node = KGNode(
        id=patient_node_id,
        patient_id=patient_id,
        node_type=NodeType.PATIENT,
        label=f"Patient {patient_id}",
        omop_concept_id=None,
        properties={
            "created_at": now.isoformat(),
            "extraction_method": extraction_method,
        },
    )

    # Batch collections — avoid per-entity db.add() to eliminate
    # intermediate flushes during concept lookup queries
    pending_nodes: list[KGNode] = [patient_node]
    pending_edges: list[KGEdge] = []

    # Track unique entities (deduplicate by text + type + assertion)
    # Include assertion in key to allow both "HIV present" and "HIV absent" nodes
    seen_entities: dict[str, str] = {}  # (text_lower, type, assertion) -> node_id
    entity_event_dates: dict[str, datetime] = {}  # node_id -> event_date (for temporal ordering)
    entity_concept_ids: dict[int, str] = {}  # omop_concept_id -> node_id (for OMOP relationships)
    note_nodes: dict[str, str] = {}  # note_key -> node_id (for provenance edges)
    date_nodes: dict[str, str] = {}  # date_key -> node_id (for temporal edges)
    conditions: list[str] = []
    medications: list[str] = []
    measurements: list[str] = []
    procedures: list[str] = []
    negated_conditions: list[str] = []

    # Pre-indexed entity type dicts for O(1) lookups in synthetic edge creation
    drug_entities: dict[str, str] = {}       # text_lower -> node_id
    condition_entities: dict[str, str] = {}  # text_lower -> node_id
    measurement_entities: dict[str, str] = {}  # text_lower -> node_id

    node_count = 1  # Patient node
    edge_count = 0

    for entity in entities:
        # Skip low confidence entities
        if entity.confidence < 0.5:
            continue

        # Phase 2: Map entity to OMOP concept_id if enabled
        if settings.enable_concept_mapping and not entity.omop_concept_id:
            try:
                # Map entity_type to domain for lookup
                domain = entity.entity_type.upper()
                if domain == "CONDITION":
                    domain = "Condition"
                elif domain in ("DRUG", "MEDICATION"):
                    domain = "Drug"
                elif domain in ("MEASUREMENT", "LAB"):
                    domain = "Measurement"
                elif domain == "PROCEDURE":
                    domain = "Procedure"
                else:
                    domain = None

                # Normalize text for concept lookup
                # For measurements, extract just the lab name (e.g., "BUN 26 mg/dL" -> "BUN")
                lookup_text = entity.text
                if domain == "Measurement":
                    lookup_text = _normalize_measurement_text(entity.text)

                concept_match = await lookup_concept_cached(db, lookup_text, domain)
                if concept_match:
                    entity.omop_concept_id = concept_match.concept_id
                    logger.debug(
                        f"Mapped '{entity.text}' -> concept_id {concept_match.concept_id} "
                        f"({concept_match.concept_name}, {concept_match.vocabulary_id})"
                    )
            except Exception as e:
                DegradationContext.record_stage_failure("concept_lookup", e, None)
                logger.warning(f"Concept lookup failed for '{entity.text}': {e}")

        # Map assertion to temporality for bi-temporal tracking
        # PRESENT/ABSENT/POSSIBLE -> current, HISTORICAL -> past, CONDITIONAL -> future
        temporality = _assertion_to_temporality(entity.assertion)

        # Include assertion in dedup key to track both positive and negative findings
        entity_key = f"{entity.text.lower()}|{entity.entity_type}|{entity.assertion}"

        if entity_key not in seen_entities:
            # Create new node
            node_id = str(uuid4())
            node_type = _domain_to_node_type(entity.entity_type)

            # Build node properties with provenance tracking
            node_properties = {
                "assertion": entity.assertion,
                "confidence": entity.confidence,
                "source_notes": [entity.note_id],
                # Provenance fields
                "extraction_method": extraction_method,
                "extraction_confidence": entity.confidence,
                "recorded_at": now.isoformat(),
            }

            # Add negation trigger info if available (from assertion classifier)
            if entity.negation_trigger:
                node_properties["negation_trigger"] = entity.negation_trigger
                node_properties["negation_trigger_confidence"] = entity.negation_trigger_confidence

            # Add temporal dates if available
            if entity.event_date:
                node_properties["event_date"] = entity.event_date
            if entity.document_date:
                node_properties["document_date"] = entity.document_date

            # Add negation-specific metadata if ABSENT
            if entity.assertion == "ABSENT":
                node_properties["is_negated"] = True
                node_properties["negation_type"] = "ruled_out"

            entity_node = KGNode(
                id=node_id,
                patient_id=patient_id,
                node_type=node_type,
                label=entity.text,
                omop_concept_id=entity.omop_concept_id,
                properties=node_properties,
            )
            pending_nodes.append(entity_node)
            seen_entities[entity_key] = node_id
            node_count += 1

            # Track OMOP concept ID for relationship lookup
            if entity.omop_concept_id:
                entity_concept_ids[entity.omop_concept_id] = node_id

            # Create edge from patient to entity with temporal + provenance
            edge_type = _node_type_to_edge_type(node_type)

            # Parse temporal dates if provided
            event_date_parsed = _parse_date(entity.event_date) if entity.event_date else None
            doc_date_parsed = _parse_date(entity.document_date) if entity.document_date else None

            # Track event dates for temporal ordering between entities
            if event_date_parsed:
                entity_event_dates[node_id] = event_date_parsed

            # Build edge properties with negation trigger if available
            edge_properties = {
                "first_noted": entity.note_id,
                "extraction_method": extraction_method,
                "assertion": entity.assertion,
                "source_confidence": entity.confidence,
            }
            if entity.negation_trigger:
                edge_properties["negation_trigger"] = entity.negation_trigger
                edge_properties["negation_trigger_confidence"] = entity.negation_trigger_confidence

            edge = KGEdge(
                id=str(uuid4()),
                patient_id=patient_id,
                source_node_id=patient_node_id,
                target_node_id=node_id,
                edge_type=edge_type,
                # Temporal fields
                temporality=temporality,
                recorded_at=now,
                temporal_confidence=entity.confidence,
                event_date=event_date_parsed,
                source_document_date=doc_date_parsed,
                # Provenance in properties
                properties=edge_properties,
            )
            pending_edges.append(edge)
            edge_count += 1

            # Create provenance edge: Entity -> EXTRACTED_FROM -> Note
            if entity.note_id:
                note_key = f"note:{entity.note_id}"
                if note_key not in note_nodes:
                    # Create the note node
                    note_node = KGNode(
                        id=str(uuid4()),
                        patient_id=patient_id,
                        node_type=NodeType.CLINICAL_NOTE,
                        label=f"Note {entity.note_id}",
                        properties={
                            "note_id": entity.note_id,
                            "document_date": entity.document_date,
                        },
                    )
                    pending_nodes.append(note_node)
                    note_nodes[note_key] = note_node.id
                    node_count += 1

                # Create EXTRACTED_FROM edge
                provenance_edge = KGEdge(
                    id=str(uuid4()),
                    patient_id=patient_id,
                    source_node_id=node_id,
                    target_node_id=note_nodes[note_key],
                    edge_type=EdgeType.EXTRACTED_FROM,
                    properties={"extraction_method": extraction_method},
                )
                pending_edges.append(provenance_edge)
                edge_count += 1

            # Create temporal edge: Entity -> OCCURRED_ON -> Date
            # Use event_date if available, otherwise fall back to document_date
            temporal_date = event_date_parsed or doc_date_parsed
            if temporal_date:
                date_str = temporal_date.strftime("%Y-%m-%d")
                date_key = f"date:{date_str}"
                if date_key not in date_nodes:
                    # Create the date node
                    date_node = KGNode(
                        id=str(uuid4()),
                        patient_id=patient_id,
                        node_type=NodeType.DATE,
                        label=date_str,
                        properties={"date": date_str, "year": temporal_date.year},
                    )
                    pending_nodes.append(date_node)
                    date_nodes[date_key] = date_node.id
                    node_count += 1

                # Create OCCURRED_ON edge
                temporal_edge = KGEdge(
                    id=str(uuid4()),
                    patient_id=patient_id,
                    source_node_id=node_id,
                    target_node_id=date_nodes[date_key],
                    edge_type=EdgeType.OCCURRED_ON,
                    event_date=temporal_date,
                    properties={
                        "date": date_str,
                        "date_source": "event_date" if event_date_parsed else "document_date",
                    },
                )
                pending_edges.append(temporal_edge)
                edge_count += 1

            # Track for summary and pre-index by type for synthetic edges
            if node_type == NodeType.CONDITION:
                if entity.assertion == "ABSENT":
                    negated_conditions.append(f"[RULED OUT] {entity.text}")
                else:
                    conditions.append(entity.text)
                condition_entities[entity.text.lower()] = node_id
            elif node_type == NodeType.DRUG:
                medications.append(entity.text)
                drug_entities[entity.text.lower()] = node_id
            elif node_type == NodeType.MEASUREMENT:
                measurements.append(entity.text)
                measurement_entities[entity.text.lower()] = node_id
            elif node_type == NodeType.PROCEDURE:
                procedures.append(entity.text)
        else:
            # Update existing node with additional source note
            # (In production, would update the properties)
            pass

    # Create treatment relationships (Drug -> treats -> Condition)
    # Phase 3: When USE_ONTOLOGY_EDGES=true, skip hardcoded mappings (OMOP relationships used instead)
    # When USE_ONTOLOGY_EDGES=false, use hardcoded heuristics as fallback
    # P0-008: In production, hardcoded/synthetic edges are disabled entirely.
    # Synthetic edges are only created in dev/test mode with use_ontology_edges=False.
    hardcoded_edge_count = 0
    _allow_synthetic_edges = not settings.use_ontology_edges
    if settings.is_production and _allow_synthetic_edges:
        logger.warning(
            "P0-008: use_ontology_edges=False in production — "
            "hardcoded synthetic edges are DISABLED in production pathways. "
            "Set USE_ONTOLOGY_EDGES=true or use OMOP relationships instead."
        )
        _allow_synthetic_edges = False
    if _allow_synthetic_edges:
        logger.info("Using hardcoded treatment mappings (USE_ONTOLOGY_EDGES=false, non-production)")

        # Expanded drug -> condition treatment mappings
        treatment_map = {
            # Diabetes medications
            "metformin": ["diabetes", "dm", "dm2", "type 2 diabetes", "hyperglycemia"],
            "insulin": ["diabetes", "dm", "dm2", "type 1 diabetes", "hyperglycemia"],
            "glipizide": ["diabetes", "dm", "dm2", "type 2 diabetes"],
            "sitagliptin": ["diabetes", "dm", "dm2", "type 2 diabetes"],
            "empagliflozin": ["diabetes", "dm", "dm2", "type 2 diabetes", "heart failure"],
            # Cardiovascular medications
            "lisinopril": ["hypertension", "htn", "high blood pressure", "heart failure", "chf"],
            "amlodipine": ["hypertension", "htn", "high blood pressure"],
            "losartan": ["hypertension", "htn", "high blood pressure"],
            "metoprolol": ["hypertension", "htn", "heart failure", "afib", "atrial fibrillation"],
            "carvedilol": ["heart failure", "chf", "hfref", "hypertension"],
            "furosemide": ["heart failure", "chf", "edema", "hfref", "fluid overload"],
            "spironolactone": ["heart failure", "chf", "hfref", "ascites"],
            # Anticoagulants
            "aspirin": ["coronary", "cad", "mi", "heart", "stroke", "cardiovascular"],
            "apixaban": ["afib", "atrial fibrillation", "dvt", "pe", "pulmonary embolism"],
            "warfarin": ["afib", "atrial fibrillation", "dvt", "pe", "mechanical valve"],
            "rivaroxaban": ["afib", "atrial fibrillation", "dvt", "pe"],
            # Lipid medications
            "atorvastatin": ["hyperlipidemia", "cholesterol", "high cholesterol", "dyslipidemia", "cad"],
            "rosuvastatin": ["hyperlipidemia", "cholesterol", "high cholesterol", "dyslipidemia"],
            "simvastatin": ["hyperlipidemia", "cholesterol", "high cholesterol", "dyslipidemia"],
            # HIV medications
            "biktarvy": ["hiv", "aids", "human immunodeficiency virus"],
            "descovy": ["hiv", "aids", "prep", "human immunodeficiency virus"],
            "truvada": ["hiv", "aids", "prep", "human immunodeficiency virus"],
            "dovato": ["hiv", "aids", "human immunodeficiency virus"],
            "genvoya": ["hiv", "aids", "human immunodeficiency virus"],
            "triumeq": ["hiv", "aids", "human immunodeficiency virus"],
            # Pain medications
            "gabapentin": ["neuropathy", "nerve pain", "neuropathic pain", "seizure", "epilepsy"],
            "pregabalin": ["neuropathy", "nerve pain", "neuropathic pain", "fibromyalgia"],
            "acetaminophen": ["pain", "fever", "headache"],
            "ibuprofen": ["pain", "inflammation", "arthritis", "fever"],
            "tramadol": ["pain", "chronic pain"],
            # Respiratory medications
            "albuterol": ["asthma", "copd", "wheezing", "bronchospasm"],
            "fluticasone": ["asthma", "copd", "allergic rhinitis"],
            "montelukast": ["asthma", "allergic rhinitis", "allergies"],
            # GI medications
            "omeprazole": ["gerd", "acid reflux", "peptic ulcer", "gastritis"],
            "pantoprazole": ["gerd", "acid reflux", "peptic ulcer", "gastritis"],
            # Psychiatric medications
            "sertraline": ["depression", "anxiety", "ptsd", "ocd"],
            "fluoxetine": ["depression", "anxiety", "ocd", "panic disorder"],
            "escitalopram": ["depression", "anxiety", "gad"],
            "bupropion": ["depression", "smoking cessation"],
            "quetiapine": ["bipolar", "schizophrenia", "depression"],
            # Antibiotics - oral
            "amoxicillin": ["infection", "bacterial infection", "pneumonia", "sinusitis"],
            "azithromycin": ["infection", "bacterial infection", "pneumonia", "bronchitis"],
            "ciprofloxacin": ["infection", "uti", "urinary tract infection"],
            "doxycycline": ["infection", "bacterial infection", "acne", "rosacea"],
            "levofloxacin": ["infection", "pneumonia", "uti", "sinusitis"],
            "metronidazole": ["infection", "c diff", "bacterial vaginosis", "h pylori"],
            # Antibiotics - IV/Hospital
            "tmp-smx": ["infection", "uti", "pcp", "pneumocystis", "pneumonia", "mrsa"],
            "bactrim": ["infection", "uti", "pcp", "pneumocystis", "pneumonia", "mrsa"],
            "sulfamethoxazole": ["infection", "uti", "pcp", "pneumocystis", "pneumonia"],
            "vancomycin": ["infection", "mrsa", "c diff", "endocarditis", "osteomyelitis", "sepsis"],
            "vanc": ["infection", "mrsa", "c diff", "endocarditis", "osteomyelitis", "sepsis"],
            "linezolid": ["infection", "mrsa", "vre", "pneumonia", "skin infection"],
            "daptomycin": ["infection", "mrsa", "vre", "bacteremia", "endocarditis", "skin infection"],
            "ceftriaxone": ["infection", "pneumonia", "meningitis", "gonorrhea", "sepsis"],
            "cefepime": ["infection", "pneumonia", "febrile neutropenia", "sepsis", "uti"],
            "piperacillin": ["infection", "pneumonia", "sepsis", "intraabdominal"],
            "meropenem": ["infection", "sepsis", "pneumonia", "meningitis", "intraabdominal"],
            "cefazolin": ["infection", "skin infection", "surgical prophylaxis"],
            "ampicillin": ["infection", "endocarditis", "meningitis", "listeria"],
            "gentamicin": ["infection", "endocarditis", "sepsis", "uti"],
            "tobramycin": ["infection", "pneumonia", "cystic fibrosis", "sepsis"],
            "micafungin": ["fungal infection", "candida", "candidemia"],
            "fluconazole": ["fungal infection", "candida", "thrush", "cryptococcus"],
            "acyclovir": ["herpes", "hsv", "vzv", "shingles", "viral infection"],
            # Sedatives/Pain - Hospital
            "fentanyl": ["pain", "sedation", "anesthesia"],
            "hydromorphone": ["pain", "severe pain"],
            "morphine": ["pain", "severe pain", "dyspnea"],
            "oxycodone": ["pain", "chronic pain"],
            "ketamine": ["pain", "sedation", "anesthesia"],
            "propofol": ["sedation", "anesthesia"],
            "midazolam": ["sedation", "anxiety", "seizure"],
            "lorazepam": ["anxiety", "sedation", "seizure", "alcohol withdrawal"],
            "haloperidol": ["agitation", "delirium", "psychosis"],
            "olanzapine": ["agitation", "schizophrenia", "bipolar"],
            # Other hospital drugs
            "heparin": ["anticoagulation", "dvt", "pe", "afib", "vte prophylaxis"],
            "enoxaparin": ["anticoagulation", "dvt", "pe", "vte prophylaxis"],
            "insulin": ["diabetes", "hyperglycemia", "dka", "hhs"],
            "norepinephrine": ["septic shock", "hypotension", "shock"],
            "vasopressin": ["septic shock", "hypotension", "shock", "diabetes insipidus"],
            "dobutamine": ["cardiogenic shock", "heart failure"],
            "dopamine": ["shock", "hypotension", "bradycardia"],
            "epinephrine": ["anaphylaxis", "cardiac arrest", "asthma", "shock"],
            "naloxone": ["opioid overdose", "opioid reversal"],
            "flumazenil": ["benzodiazepine overdose", "sedation reversal"],
            "pantoprazole": ["gerd", "stress ulcer prophylaxis", "gi bleed"],
            "famotidine": ["gerd", "stress ulcer prophylaxis"],
            "ondansetron": ["nausea", "vomiting", "chemotherapy"],
            "metoclopramide": ["nausea", "gastroparesis", "ileus"],
            "lactulose": ["hepatic encephalopathy", "constipation"],
            "albumin": ["hypoalbuminemia", "ascites", "spontaneous bacterial peritonitis"],
        }

        # Use pre-indexed drug_entities dict instead of scanning all seen_entities
        for drug_text, drug_node_id in drug_entities.items():
            for drug_pattern, condition_patterns in treatment_map.items():
                if drug_pattern in drug_text:
                    # O(1) dict lookup per condition pattern instead of scanning all entities
                    for cp in condition_patterns:
                        for cond_text, condition_node_id in condition_entities.items():
                            if cp in cond_text:
                                # Determine temporal ordering if both entities have event dates
                                temporal_order = None
                                drug_date = entity_event_dates.get(drug_node_id)
                                condition_date = entity_event_dates.get(condition_node_id)

                                if drug_date and condition_date:
                                    if drug_date > condition_date:
                                        temporal_order = "after"
                                    elif drug_date < condition_date:
                                        temporal_order = "before"
                                    else:
                                        temporal_order = "concurrent"

                                treats_edge = KGEdge(
                                    id=str(uuid4()),
                                    patient_id=patient_id,
                                    source_node_id=drug_node_id,
                                    target_node_id=condition_node_id,
                                    edge_type=EdgeType.DRUG_TREATS,
                                    temporal_order=temporal_order,
                                    properties={
                                        "inferred": True,
                                        "temporal_ordering_source": "event_date_comparison" if temporal_order else None,
                                    },
                                )
                                pending_edges.append(treats_edge)
                                edge_count += 1

    # Create symptom -> condition and measurement -> condition associations
    # P0-008: All synthetic/hardcoded edges are gated by _allow_synthetic_edges
    symptom_condition_map = {
        # Pain symptoms
        "muscle pain": ["myalgia", "fibromyalgia", "statin", "rhabdomyolysis", "polymyalgia"],
        "joint pain": ["arthritis", "rheumatoid", "osteoarthritis", "gout", "lupus"],
        "chest pain": ["angina", "coronary", "cad", "mi", "heart attack", "gerd", "costochondritis"],
        "headache": ["migraine", "tension headache", "hypertension", "intracranial"],
        "back pain": ["degenerative disc", "herniated", "spinal stenosis", "sciatica"],
        "abdominal pain": ["gastritis", "peptic ulcer", "appendicitis", "pancreatitis", "gerd"],
        # Respiratory symptoms
        "shortness of breath": ["heart failure", "chf", "copd", "asthma", "pneumonia", "pulmonary"],
        "dyspnea": ["heart failure", "chf", "copd", "asthma", "pulmonary embolism"],
        "cough": ["pneumonia", "bronchitis", "copd", "asthma", "heart failure", "gerd"],
        "wheezing": ["asthma", "copd", "bronchitis", "allergic"],
        # Cardiovascular symptoms
        "palpitations": ["afib", "atrial fibrillation", "arrhythmia", "anxiety"],
        "edema": ["heart failure", "chf", "kidney", "renal", "venous insufficiency"],
        "syncope": ["arrhythmia", "hypotension", "vasovagal", "cardiac"],
        # GI symptoms
        "nausea": ["gastritis", "gerd", "gastroparesis", "pregnancy", "medication side effect"],
        "vomiting": ["gastroenteritis", "obstruction", "gastroparesis", "pregnancy"],
        "diarrhea": ["gastroenteritis", "ibd", "crohn", "colitis", "c diff"],
        "constipation": ["ibs", "hypothyroid", "medication side effect", "obstruction"],
        # Neurological symptoms
        "dizziness": ["vertigo", "bppv", "hypotension", "anemia", "stroke"],
        "fatigue": ["anemia", "hypothyroid", "depression", "heart failure", "diabetes"],
        "weakness": ["anemia", "neuropathy", "stroke", "myasthenia", "ms"],
        "numbness": ["neuropathy", "stroke", "ms", "diabetes", "carpal tunnel"],
        "tingling": ["neuropathy", "diabetes", "b12 deficiency", "carpal tunnel"],
        # Constitutional symptoms
        "fever": ["infection", "sepsis", "pneumonia", "uti", "viral"],
        "weight loss": ["cancer", "diabetes", "hyperthyroid", "depression", "hiv"],
        "weight gain": ["hypothyroid", "heart failure", "cushing", "medication"],
        "night sweats": ["infection", "tb", "lymphoma", "menopause", "hyperthyroid"],
        # Mental health symptoms
        "anxiety": ["gad", "panic disorder", "ptsd", "depression"],
        "insomnia": ["anxiety", "depression", "sleep apnea", "restless leg"],
        "depression": ["mdd", "bipolar", "adjustment disorder"],
    }

    # Find symptom-condition relationships using pre-indexed condition_entities
    # P0-008: Only create synthetic edges outside production
    for symptom_pattern, condition_patterns in (
        symptom_condition_map.items() if _allow_synthetic_edges else []
    ):
        # Look for the symptom in conditions (symptoms are often extracted as conditions)
        for cond_text, symptom_node_id in condition_entities.items():
            if symptom_pattern in cond_text:
                # Found a symptom, look for associated conditions via dict
                for cp in condition_patterns:
                    for other_cond_text, condition_node_id in condition_entities.items():
                        if other_cond_text == cond_text:  # Skip self
                            continue
                        if cp in other_cond_text:
                            symptom_edge = KGEdge(
                                id=str(uuid4()),
                                patient_id=patient_id,
                                source_node_id=symptom_node_id,
                                target_node_id=condition_node_id,
                                edge_type=EdgeType.SYMPTOM_OF,
                                properties={
                                    "inferred": True,
                                    "source": "symptom_condition_mapping",
                                },
                            )
                            pending_edges.append(symptom_edge)
                            edge_count += 1

    # Create measurement -> condition associations
    measurement_condition_map = {
        "blood pressure": ["hypertension", "htn", "hypotension"],
        "bp": ["hypertension", "htn", "hypotension"],
        "glucose": ["diabetes", "dm", "hyperglycemia", "hypoglycemia"],
        "blood sugar": ["diabetes", "dm", "hyperglycemia", "hypoglycemia"],
        "a1c": ["diabetes", "dm"],
        "hemoglobin a1c": ["diabetes", "dm"],
        "cholesterol": ["hyperlipidemia", "dyslipidemia", "high cholesterol"],
        "ldl": ["hyperlipidemia", "dyslipidemia", "cad"],
        "hdl": ["hyperlipidemia", "dyslipidemia"],
        "triglycerides": ["hyperlipidemia", "dyslipidemia"],
        "creatinine": ["kidney disease", "ckd", "renal", "aki"],
        "gfr": ["kidney disease", "ckd", "renal"],
        "bun": ["kidney disease", "ckd", "renal", "dehydration"],
        "hemoglobin": ["anemia", "bleeding", "polycythemia"],
        "hematocrit": ["anemia", "dehydration", "polycythemia"],
        "platelets": ["thrombocytopenia", "thrombocytosis", "bleeding"],
        "wbc": ["infection", "leukemia", "leukopenia"],
        "inr": ["anticoagulation", "warfarin", "bleeding"],
        "potassium": ["hyperkalemia", "hypokalemia", "arrhythmia"],
        "sodium": ["hyponatremia", "hypernatremia", "dehydration"],
        "tsh": ["hypothyroid", "hyperthyroid", "thyroid"],
        "bmi": ["obesity", "overweight", "underweight"],
        "weight": ["obesity", "weight loss", "weight gain"],
        "oxygen saturation": ["hypoxia", "respiratory failure", "copd", "pneumonia"],
        "o2 sat": ["hypoxia", "respiratory failure", "copd", "pneumonia"],
        "viral load": ["hiv", "hepatitis"],
        "cd4": ["hiv", "aids", "immunodeficiency"],
        "ejection fraction": ["heart failure", "cardiomyopathy", "chf"],
        "ef": ["heart failure", "cardiomyopathy", "chf"],
    }

    for measurement_pattern, condition_patterns in (
        measurement_condition_map.items() if _allow_synthetic_edges else []
    ):
        # Use pre-indexed measurement_entities instead of scanning all seen_entities
        for meas_text, measurement_node_id in measurement_entities.items():
            if measurement_pattern in meas_text:
                for cp in condition_patterns:
                    for cond_text, condition_node_id in condition_entities.items():
                        if cp in cond_text:
                            monitors_edge = KGEdge(
                                id=str(uuid4()),
                                patient_id=patient_id,
                                source_node_id=measurement_node_id,
                                target_node_id=condition_node_id,
                                edge_type=EdgeType.MONITORS,
                                properties={
                                    "inferred": True,
                                    "source": "measurement_condition_mapping",
                                },
                            )
                            pending_edges.append(monitors_edge)
                            edge_count += 1

    # Query OMOP relationships between entities with concept IDs
    # This creates entity-to-entity edges based on OMOP concept_relationship table
    if entity_concept_ids:
        omop_relationships = await _query_omop_relationships(db, entity_concept_ids)

        for source_node_id, target_node_id, rel_type, edge_type in omop_relationships:
            # Avoid duplicate edges (check if already created by treatment_map)
            edge_key = f"{source_node_id}:{target_node_id}:{edge_type}"

            # Calculate temporal ordering if both entities have event dates
            temporal_order = None
            source_date = entity_event_dates.get(source_node_id)
            target_date = entity_event_dates.get(target_node_id)

            if source_date and target_date:
                # For drug_treats: drug started AFTER condition = "after"
                # For condition_treated_by: condition before drug = "before"
                if edge_type == EdgeType.DRUG_TREATS:
                    if source_date > target_date:
                        temporal_order = "after"  # Drug follows condition
                    elif source_date < target_date:
                        temporal_order = "before"  # Drug precedes condition (unusual)
                    else:
                        temporal_order = "concurrent"
                elif edge_type == EdgeType.CONDITION_TREATED_BY:
                    if target_date > source_date:
                        temporal_order = "after"  # Treatment follows condition
                    elif target_date < source_date:
                        temporal_order = "before"
                    else:
                        temporal_order = "concurrent"

            # Create OMOP-derived relationship edge with temporal ordering
            omop_edge = KGEdge(
                id=str(uuid4()),
                patient_id=patient_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                edge_type=edge_type,
                temporal_order=temporal_order,
                properties={
                    "source": "omop_concept_relationship",
                    "relationship_id": rel_type,
                    "inferred": True,
                    "temporal_ordering_source": "event_date_comparison" if temporal_order else None,
                },
            )
            pending_edges.append(omop_edge)
            edge_count += 1

        if omop_relationships:
            logger.info(
                f"Created {len(omop_relationships)} entity-to-entity edges from OMOP relationships"
            )

    # Bulk insert all collected nodes and edges (avoids ~1500 individual db.add() roundtrips)
    db.add_all(pending_nodes)
    db.add_all(pending_edges)

    # Create narrative nodes and edges if narrative data is provided
    if narrative:
        narrative_node_ids = await _create_narrative_nodes(
            db=db,
            patient_id=patient_id,
            patient_node_id=patient_node_id,
            narrative=narrative,
            seen_entities=seen_entities,
            now=now,
        )
        node_count += narrative_node_ids.get("node_count", 0)
        edge_count += narrative_node_ids.get("edge_count", 0)

    return KnowledgeGraphSummary(
        patient_id=patient_id,
        node_count=node_count,
        edge_count=edge_count,
        conditions=list(set(conditions))[:20],
        medications=list(set(medications))[:20],
        measurements=list(set(measurements))[:20],
        procedures=list(set(procedures))[:20],
        negated_conditions=list(set(negated_conditions))[:20],
        extraction_method=extraction_method,
    )


@router.get(
    "/graph/{patient_id}",
    response_model=PatientGraphResponse,
    summary="Get patient knowledge graph",
    description="Retrieve the complete knowledge graph for a patient.",
)
async def get_patient_graph(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.READ_PATIENTS])),
) -> PatientGraphResponse:
    """Get the knowledge graph for a patient."""

    # Get patient-owned nodes
    patient_nodes_result = await db.execute(
        select(KGNode).where(KGNode.patient_id == patient_id)
    )
    patient_nodes = list(patient_nodes_result.scalars().all())

    # Get shared concept nodes connected via edges
    concept_nodes_result = await db.execute(
        select(KGNode)
        .join(
            KGEdge,
            or_(
                KGEdge.target_node_id == KGNode.id,
                KGEdge.source_node_id == KGNode.id,
            ),
        )
        .where(KGEdge.patient_id == patient_id)
        .where(KGNode.patient_id.is_(None))
    )
    concept_nodes = list(concept_nodes_result.scalars().all())

    # Combine and deduplicate
    seen_ids: set[str] = set()
    nodes = []
    for n in patient_nodes + concept_nodes:
        if n.id not in seen_ids:
            seen_ids.add(n.id)
            nodes.append(n)

    if not nodes:
        raise HTTPException(
            status_code=404,
            detail=f"No knowledge graph found for patient {patient_id}"
        )

    # Get all edges for patient
    edges_result = await db.execute(
        select(KGEdge).where(KGEdge.patient_id == patient_id)
    )
    edges = edges_result.scalars().all()

    # Build response
    node_responses = [
        KGNodeResponse(
            id=str(n.id),
            node_type=n.node_type.value if hasattr(n.node_type, 'value') else str(n.node_type),
            label=n.label,
            omop_concept_id=n.omop_concept_id,
            properties=n.properties or {},
        )
        for n in nodes
    ]

    edge_responses = [
        KGEdgeResponse(
            id=str(e.id),
            source_node_id=str(e.source_node_id),
            target_node_id=str(e.target_node_id),
            edge_type=e.edge_type.value if hasattr(e.edge_type, 'value') else str(e.edge_type),
            properties=e.properties or {},
            temporality=e.temporality if hasattr(e, 'temporality') else None,
            temporal_order=e.temporal_order if hasattr(e, 'temporal_order') else None,
            event_date=e.event_date.isoformat() if hasattr(e, 'event_date') and e.event_date else None,
        )
        for e in edges
    ]

    # Build summary
    conditions = [n.label for n in nodes if n.node_type == NodeType.CONDITION]
    medications = [n.label for n in nodes if n.node_type == NodeType.DRUG]
    measurements = [n.label for n in nodes if n.node_type == NodeType.MEASUREMENT]
    procedures = [n.label for n in nodes if n.node_type == NodeType.PROCEDURE]

    summary = KnowledgeGraphSummary(
        patient_id=patient_id,
        node_count=len(nodes),
        edge_count=len(edges),
        conditions=conditions[:20],
        medications=medications[:20],
        measurements=measurements[:20],
        procedures=procedures[:20],
    )

    return PatientGraphResponse(
        patient_id=patient_id,
        nodes=node_responses,
        edges=edge_responses,
        summary=summary,
    )


@router.post(
    "/query/{patient_id}",
    response_model=HybridQueryResponse,
    summary="Query patient data with hybrid reasoning",
    description="Ask natural language questions combining EHR data and knowledge graph.",
)
async def hybrid_query(
    patient_id: str,
    request: HybridQueryRequest,
    provenance_depth: str = Query("summary", regex="^(none|summary|full)$"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.READ_CLINICAL_FACTS])),
) -> HybridQueryResponse:
    """Hybrid query combining EHR and knowledge graph.

    This endpoint:
    1. Searches documents for relevant mentions
    2. Queries the knowledge graph for related entities
    3. Combines results with reasoning
    4. Records provenance traces for each step
    """
    # Generate query_id for provenance tracking
    query_id = str(uuid4())
    step_order = 0
    provenance_svc = get_provenance_db_service()
    reasoning_chain: list[dict] = []
    entity_provenance_data: list[dict] = []

    question = request.question.lower()

    # Get patient's documents (optional - may not exist for hybrid-built graphs)
    docs_result = await db.execute(
        select(DocumentModel).where(DocumentModel.patient_id == patient_id)
    )
    documents = list(docs_result.scalars().all())

    # Get knowledge graph nodes (patient-owned + shared concepts via edges)
    kg_start = time.perf_counter()
    patient_nodes_result = await db.execute(
        select(KGNode).where(KGNode.patient_id == patient_id)
    )
    patient_kg_nodes = list(patient_nodes_result.scalars().all())

    concept_nodes_result = await db.execute(
        select(KGNode)
        .join(
            KGEdge,
            or_(
                KGEdge.target_node_id == KGNode.id,
                KGEdge.source_node_id == KGNode.id,
            ),
        )
        .where(KGEdge.patient_id == patient_id)
        .where(KGNode.patient_id.is_(None))
    )
    concept_kg_nodes = list(concept_nodes_result.scalars().all())

    seen_ids: set[str] = set()
    nodes: list[KGNode] = []
    for n in patient_kg_nodes + concept_kg_nodes:
        if n.id not in seen_ids:
            seen_ids.add(n.id)
            nodes.append(n)

    if not documents and not nodes:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for patient {patient_id}"
        )

    # Simple keyword-based relevance scoring
    relevant_entities: list[ExtractedEntity] = []
    evidence_sources: list[EvidenceSource] = []

    # Determine query intent
    query_keywords = {
        "medication": ["medication", "drug", "taking", "prescribed", "medicine"],
        "condition": ["diagnosis", "condition", "disease", "problem", "have", "has"],
        "lab": ["lab", "test", "result", "level", "value"],
        "vital": ["vital", "blood pressure", "heart rate", "temperature"],
        # Narrative-related queries
        "admission": ["admitted", "admission", "why was", "reason for", "came in", "presented"],
        "course": ["hospital course", "happened during", "hospitalization", "what happened", "timeline", "events"],
        "discharge": ["discharge", "going home", "follow up", "follow-up", "disposition"],
        "causal": ["caused", "led to", "resulted in", "because of", "due to", "after the"],
    }

    query_type = "general"
    for qtype, keywords in query_keywords.items():
        if any(kw in question for kw in keywords):
            query_type = qtype
            break

    # P1-003: Detect workflow type and apply workflow-specific confidence policy
    workflow_type = detect_workflow_type(request.question, query_type)
    workflow_policy = get_policy_for_workflow(workflow_type)
    logger.debug(
        "P1-003 workflow confidence: type=%s policy_version=%s thresholds=%s",
        workflow_type.value, get_policy_version(), workflow_policy.thresholds,
    )

    # Check for narrative-related query
    is_narrative_query = query_type in ["admission", "course", "discharge", "causal"]

    # Filter nodes by query type
    target_node_types = {
        "medication": [NodeType.DRUG],
        "condition": [NodeType.CONDITION],
        "lab": [NodeType.MEASUREMENT],
        "vital": [NodeType.MEASUREMENT],
        "general": [NodeType.CONDITION, NodeType.DRUG, NodeType.MEASUREMENT, NodeType.PROCEDURE],
        # Narrative node types
        "admission": [NodeType.ADMISSION, NodeType.CONDITION],
        "course": [NodeType.HOSPITAL_COURSE, NodeType.CLINICAL_EVENT, NodeType.EPISODE],
        "discharge": [NodeType.DISCHARGE],
        "causal": [NodeType.CLINICAL_EVENT, NodeType.CONDITION, NodeType.PROCEDURE],
    }

    matching_nodes = [
        n for n in nodes
        if n.node_type in target_node_types.get(query_type, [])
    ]

    # Build entities from matching nodes
    for node in matching_nodes[:request.max_results]:
        relevant_entities.append(ExtractedEntity(
            text=node.label,
            entity_type=node.node_type.value if hasattr(node.node_type, 'value') else str(node.node_type),
            confidence=node.properties.get("confidence", 0.9) if node.properties else 0.9,
            # TODO: Read from edge.properties once shared concept migration is complete
            assertion=node.properties.get("assertion", "PRESENT") if node.properties else "PRESENT",
            omop_concept_id=node.omop_concept_id,
            note_id=node.properties.get("source_notes", ["unknown"])[0] if node.properties else "unknown",
        ))

    kg_duration = (time.perf_counter() - kg_start) * 1000

    # Step 4: Record KG_RETRIEVAL reasoning trace
    try:
        step_order += 1
        kg_trace = await provenance_svc.create_reasoning_trace(
            session=db,
            query_id=query_id,
            step_order=step_order,
            step_type=ReasoningStepType.KG_RETRIEVAL.value,
            patient_id=patient_id,
            input_summary=f"Query: '{request.question}', type: {query_type}",
            output_summary=f"Found {len(matching_nodes)} matching nodes from {len(nodes)} total",
            duration_ms=round(kg_duration, 2),
            metadata={
                "total_nodes": len(nodes),
                "matching_nodes": len(matching_nodes),
                "query_type": query_type,
                "entity_labels": [n.label for n in matching_nodes[:10]],
            },
        )
        reasoning_chain.append({
            "step": step_order,
            "type": "kg_retrieval",
            "summary": f"Retrieved {len(matching_nodes)} entities from knowledge graph",
            "duration_ms": round(kg_duration, 2),
            "details": {"total_nodes": len(nodes), "matching": len(matching_nodes)},
        })
    except Exception as e:
        DegradationContext.record_stage_failure("kg_provenance", e, None)
        logger.warning(f"Failed to record KG provenance: {e}")

    # Step: Multi-hop Graph RAG Retrieval for enriched context
    graph_rag_start = time.perf_counter()
    graph_paths_data: list[dict] = []
    graph_context = ""
    try:
        graph_rag_service = GraphAugmentedRAGService(db)
        enriched_context = await graph_rag_service.retrieve_context_async(
            query=request.question,
            patient_id=patient_id,
            max_hops=3,  # Multi-hop traversal for richer context
            max_paths=10,
            include_temporal=True,
            include_policies=True,
        )

        # Format graph context for LLM
        graph_context = enriched_context.to_llm_prompt()

        # Extract path data for provenance
        for path in enriched_context.graph_paths:
            graph_paths_data.append({
                "path_type": path.path_type,
                "nodes": [n.get("label", "?") for n in path.nodes],
                "edges": [e.get("edge_type", "?") for e in path.edges],
                "confidence": path.confidence,
            })

        graph_rag_duration = (time.perf_counter() - graph_rag_start) * 1000

        # Record GRAPH_RAG_RETRIEVAL provenance trace
        step_order += 1
        await provenance_svc.create_reasoning_trace(
            session=db,
            query_id=query_id,
            step_order=step_order,
            step_type=ReasoningStepType.GRAPH_RAG_RETRIEVAL.value,
            patient_id=patient_id,
            input_summary=f"Query: '{request.question}', max_hops: 3",
            output_summary=(
                f"Traversed {len(graph_paths_data)} paths, "
                f"{enriched_context.total_evidence_pieces} total evidence pieces"
            ),
            duration_ms=round(graph_rag_duration, 2),
            metadata={
                "paths_traversed": len(graph_paths_data),
                "total_evidence": enriched_context.total_evidence_pieces,
                "path_types": list(set(p["path_type"] for p in graph_paths_data)),
                "temporal_events": len(enriched_context.temporal_context.event_timeline)
                if enriched_context.temporal_context else 0,
                "sample_paths": graph_paths_data[:3],
            },
        )
        reasoning_chain.append({
            "step": step_order,
            "type": "graph_rag_retrieval",
            "summary": f"Multi-hop graph traversal found {len(graph_paths_data)} paths",
            "duration_ms": round(graph_rag_duration, 2),
            "details": {
                "paths_traversed": len(graph_paths_data),
                "total_evidence": enriched_context.total_evidence_pieces,
                "path_types": list(set(p["path_type"] for p in graph_paths_data)),
            },
        })

        logger.info(
            f"Graph RAG retrieved {len(graph_paths_data)} paths for patient {patient_id}"
        )
    except Exception as e:
        DegradationContext.record_stage_failure("graph_rag", e, [])
        logger.warning(f"Graph RAG retrieval failed, continuing without: {e}")
        graph_rag_duration = (time.perf_counter() - graph_rag_start) * 1000

    # Find evidence in documents (only if documents exist)
    if request.include_evidence and documents:
        search_terms = [n.label.lower() for n in matching_nodes[:5]]

        for doc in documents[:20]:
            doc_text = doc.text.lower()
            relevance = sum(1 for term in search_terms if term in doc_text)

            if relevance > 0:
                # Extract relevant excerpt
                excerpt = doc.text[:300] + "..." if len(doc.text) > 300 else doc.text

                evidence_sources.append(EvidenceSource(
                    note_id=doc.extra_metadata.get("original_note_id", str(doc.id)),
                    note_type=doc.note_type,
                    note_date=doc.extra_metadata.get("note_date", "unknown"),
                    excerpt=excerpt,
                    relevance_score=min(relevance / len(search_terms), 1.0) if search_terms else 0.5,
                ))

        # Sort by relevance
        evidence_sources.sort(key=lambda x: x.relevance_score, reverse=True)
        evidence_sources = evidence_sources[:5]

    # Build clinical context for LLM
    conditions = [n.label for n in nodes if n.node_type == NodeType.CONDITION]
    medications = [n.label for n in nodes if n.node_type == NodeType.DRUG]
    measurements = [n.label for n in nodes if n.node_type == NodeType.MEASUREMENT]
    procedures = [n.label for n in nodes if n.node_type == NodeType.PROCEDURE]

    clinical_context = f"""Patient ID: {patient_id}

Knowledge Graph Summary ({len(nodes)} nodes):
- Conditions ({len(conditions)}): {', '.join(conditions[:30]) if conditions else 'None recorded'}
- Medications ({len(medications)}): {', '.join(medications[:30]) if medications else 'None recorded'}
- Measurements ({len(measurements)}): {', '.join(measurements[:30]) if measurements else 'None recorded'}
- Procedures ({len(procedures)}): {', '.join(procedures[:30]) if procedures else 'None recorded'}"""

    # Add narrative context if this is a narrative-related query or narrative nodes exist
    narrative_context = _get_narrative_context(nodes) if is_narrative_query else ""
    if narrative_context:
        clinical_context += f"\n\n{narrative_context}"

    # Add document evidence if available
    if evidence_sources:
        clinical_context += "\n\nRelevant Clinical Notes:"
        for ev in evidence_sources[:3]:
            clinical_context += f"\n[{ev.note_type} - {ev.note_date}]: {ev.excerpt}"

    # Retrieve relevant clinical guidelines via RAG
    rag_start = time.perf_counter()
    guideline_citations_data: list[dict] = []
    guideline_context = ""
    policy_citations_data: list[dict] = []
    try:
        from app.services.guideline_rag_service import get_guideline_rag_service

        rag_service = get_guideline_rag_service()

        # Two-pool search: topic-relevant (raw question) + patient-relevant (with context)
        topic_citations = rag_service.search(
            query=request.question,
            top_k=3,
            min_score=0.25,
        )
        patient_citations = rag_service.search(
            query=request.question,
            patient_conditions=conditions,
            patient_medications=medications,
            patient_measurements=measurements,
            top_k=5,
            min_score=0.3,
        )
        # Merge: topic results first, then patient results (deduplicated)
        # Filter to only include guidelines relevant to patient's conditions
        # IMPORTANT: Prioritize condition matches over medication-only matches
        patient_conditions_lower = {c.lower() for c in conditions}
        patient_medications_lower = {m.lower() for m in medications}

        # Common medications that shouldn't drive guideline selection alone
        # (too generic - appear in many unrelated guidelines)
        common_medications = {
            "aspirin", "atorvastatin", "metformin", "lisinopril", "amlodipine",
            "omeprazole", "metoprolol", "losartan", "furosemide", "warfarin",
            "clopidogrel", "rivaroxaban", "apixaban", "heparin", "insulin",
        }

        seen_ids: set[str] = set()
        condition_matched_citations = []  # Guidelines matching patient conditions
        medication_only_citations = []    # Guidelines only matching medications

        for c in topic_citations + patient_citations:
            if c.section.section_id not in seen_ids:
                seen_ids.add(c.section.section_id)

                # Relevance filter: guideline must apply to at least one
                # of the patient's conditions or medications.
                # Uses ConditionMatchingService for safe condition matching
                # that prevents false positives (e.g., "anemia" ≠ "sickle cell anemia").
                from app.services.condition_matching_service import match_conditions

                section_conditions = {cond.lower() for cond in c.section.applies_to_conditions}
                section_medications = {med.lower() for med in c.section.applies_to_medications}

                cond_result = match_conditions(
                    list(patient_conditions_lower),
                    list(section_conditions),
                    primary_conditions=getattr(c.section, "primary_conditions", None) or None,
                    use_hierarchy=False,
                )
                has_condition_match = cond_result.has_match

                # Check for medication matches (excluding common medications)
                specific_section_meds = section_medications - common_medications
                specific_patient_meds = patient_medications_lower - common_medications
                has_specific_medication_match = bool(specific_patient_meds & specific_section_meds)

                # Partial medication match for specific drugs
                has_partial_medication_match = any(
                    any(pm in sm or sm in pm for sm in specific_section_meds)
                    for pm in specific_patient_meds
                ) if not has_specific_medication_match else False

                # Categorize the citation
                if has_condition_match:
                    # Strong match: condition-based
                    condition_matched_citations.append(c)
                elif has_specific_medication_match or has_partial_medication_match:
                    # Weaker match: medication-only (specific drugs)
                    medication_only_citations.append(c)
                else:
                    # No relevant match - skip
                    logger.debug(
                        f"Filtered out irrelevant guideline: {c.section.guideline} "
                        f"(applies_to: {c.section.applies_to_conditions})"
                    )
                    continue

        # Prioritize condition-matched guidelines, then add medication-only if needed
        citations = condition_matched_citations[:5]
        remaining_slots = 5 - len(citations)
        if remaining_slots > 0:
            citations.extend(medication_only_citations[:remaining_slots])

        logger.info(
            f"Guideline filtering: {len(condition_matched_citations)} condition matches, "
            f"{len(medication_only_citations)} medication-only matches, returning {len(citations)}"
        )

        if citations:
            guideline_context = "\n\nClinical Guideline References:"
            for i, citation in enumerate(citations, 1):
                sec = citation.section
                guideline_context += (
                    f"\n[Guideline {i}] {sec.guideline} — {sec.section_title} "
                    f"(Evidence: {sec.evidence_grade}, {sec.recommendation_level}): "
                    f"{sec.recommendation_text}"
                )
                guideline_citations_data.append({
                    "guideline_number": i,
                    "section_id": sec.section_id,
                    "guideline": sec.guideline,
                    "section_title": sec.section_title,
                    "recommendation_text": sec.recommendation_text,
                    "evidence_grade": sec.evidence_grade,
                    "recommendation_level": sec.recommendation_level,
                    "relevance_score": citation.score,
                    "match_reasons": citation.match_reasons,
                })

            logger.info(f"Retrieved {len(citations)} guideline sections for query")

    except Exception as e:
        DegradationContext.record_stage_failure("guideline_rag", e, [])
        logger.warning(f"Guideline RAG retrieval failed, proceeding without: {e}")

    # Policy RAG search (Step 25 integration point)
    try:
        from app.services.policy_service import get_policy_service

        policy_svc = get_policy_service()
        policy_results = await policy_svc.search_policy_sections(
            session=db,
            query=request.question,
            patient_conditions=conditions,
            top_k=3,
        )
        if policy_results:
            guideline_context += "\n\nInstitutional Policy References:"
            policy_offset = len(guideline_citations_data)
            for i, pr in enumerate(policy_results, 1):
                guideline_context += (
                    f"\n[Policy {i}] {pr['policy_name']} — {pr['section_title']}: "
                    f"{pr['content_text'][:300]}"
                )
                policy_citations_data.append({
                    "policy_number": i,
                    "policy_id": pr["policy_id"],
                    "policy_name": pr["policy_name"],
                    "section_id": pr["section_id"],
                    "section_title": pr["section_title"],
                    "relevance_score": pr["relevance_score"],
                })
    except Exception as e:
        DegradationContext.record_stage_failure("policy_rag", e, None)
        logger.debug(f"Policy RAG unavailable: {e}")

    rag_duration = (time.perf_counter() - rag_start) * 1000

    # Step 5: Record RAG_SEARCH reasoning trace
    try:
        step_order += 1
        rag_trace = await provenance_svc.create_reasoning_trace(
            session=db,
            query_id=query_id,
            step_order=step_order,
            step_type=ReasoningStepType.RAG_SEARCH.value,
            patient_id=patient_id,
            input_summary=f"Query: '{request.question}', conditions: {conditions[:5]}",
            output_summary=(
                f"Found {len(guideline_citations_data)} guideline citations, "
                f"{len(policy_citations_data)} policy citations"
            ),
            duration_ms=round(rag_duration, 2),
            metadata={
                "guideline_count": len(guideline_citations_data),
                "policy_count": len(policy_citations_data),
                "top_guideline_scores": [
                    gc.get("relevance_score", 0) for gc in guideline_citations_data[:3]
                ],
            },
        )
        reasoning_chain.append({
            "step": step_order,
            "type": "rag_search",
            "summary": f"Found {len(guideline_citations_data)} guidelines, {len(policy_citations_data)} policies",
            "duration_ms": round(rag_duration, 2),
            "details": {
                "guideline_count": len(guideline_citations_data),
                "policy_count": len(policy_citations_data),
            },
        })

        # Record guideline citation provenance
        for gc in guideline_citations_data:
            try:
                await provenance_svc.create_guideline_citation_provenance(
                    session=db,
                    query_id=query_id,
                    section_id=gc.get("section_id", ""),
                    relevance_score=gc.get("relevance_score", 0),
                    match_reasons=gc.get("match_reasons"),
                    evidence_grade=gc.get("evidence_grade"),
                    recommendation_level=gc.get("recommendation_level"),
                )
            except Exception as e:
                DegradationContext.record_stage_failure("rag_provenance_inner", e, None)
                logger.debug(f"Failed to record individual RAG provenance entry: {e}")
    except Exception as e:
        DegradationContext.record_stage_failure("rag_provenance", e, None)
        logger.warning(f"Failed to record RAG provenance: {e}")

    # =============================================================================
    # Multi-Agent Orchestrator: Consensus-based clinical reasoning
    # =============================================================================
    orchestrator_start = time.perf_counter()
    consensus_context = ""
    mdt_session_summary: dict[str, Any] = {}
    try:
        # Build AgentContext from KG nodes
        agent_context = AgentContext(
            patient_id=patient_id,
            clinical_text=request.question,
        )

        # Populate conditions with confidence
        for node in nodes:
            if node.node_type == NodeType.CONDITION:
                agent_context.conditions.append({
                    "name": node.label,
                    "confidence": node.properties.get("confidence", 0.9) if node.properties else 0.9,
                    "source": node.properties.get("source_notes", ["note"])[0] if node.properties else "note",
                })
            elif node.node_type == NodeType.DRUG:
                agent_context.medications.append({
                    "name": node.label,
                    "dose": node.properties.get("dose", "") if node.properties else "",
                })
            elif node.node_type == NodeType.MEASUREMENT:
                # Parse measurement for name/value if available
                agent_context.lab_values.append({
                    "name": node.label,
                    "value": node.properties.get("value", "") if node.properties else "",
                    "unit": node.properties.get("unit", "") if node.properties else "",
                })

        # Add allergies from properties if available
        # TODO: Read from edge.properties once shared concept migration is complete
        for node in nodes:
            if node.properties and node.properties.get("assertion") == "ALLERGY":
                agent_context.allergies.append(node.label)

        # Run multi-agent orchestration
        orchestrator = get_multi_agent_orchestrator()
        session = await orchestrator.create_session(patient_id, agent_context)
        mdt_result = await orchestrator.run_mdt_discussion(session.session_id)

        # Build consensus context for LLM prompt
        if mdt_result.consensus_results:
            consensus_context = "\n\nClinical Agent Consensus (Multi-Disciplinary Team):"
            for i, consensus in enumerate(mdt_result.consensus_results[:5], 1):
                rec = consensus.recommendation
                consensus_context += (
                    f"\n[Agent {i}] {rec.agent_role.value.title()} Agent — "
                    f"{rec.recommendation_type.value}: {rec.content} "
                    f"(Consensus: {consensus.consensus_level.value}, "
                    f"Confidence: {consensus.final_confidence:.2f})"
                )
                if consensus.dissenting_concerns:
                    concerns_str = "; ".join(consensus.dissenting_concerns[:2])
                    consensus_context += f"\n  Concerns: {concerns_str}"

            # Store session summary for provenance
            mdt_session_summary = orchestrator.get_session_summary(session.session_id)

        logger.info(
            f"MDT discussion completed: {len(mdt_result.consensus_results)} "
            f"recommendations from {len(orchestrator.agents)} agents"
        )

    except Exception as e:
        DegradationContext.record_stage_failure("multi_agent_orchestration", e, {})
        logger.warning(f"Multi-agent orchestration failed, proceeding without: {e}")

    orchestrator_duration = (time.perf_counter() - orchestrator_start) * 1000

    # Record ORCHESTRATOR_CONSENSUS reasoning trace
    try:
        step_order += 1
        await provenance_svc.create_reasoning_trace(
            session=db,
            query_id=query_id,
            step_order=step_order,
            step_type=ReasoningStepType.ORCHESTRATOR_CONSENSUS.value,
            patient_id=patient_id,
            input_summary=f"Query: '{request.question}', {len(conditions)} conditions, {len(medications)} medications",
            output_summary=(
                f"Generated {len(mdt_session_summary.get('consensus_results', []))} "
                f"consensus recommendations from MDT discussion"
            ),
            duration_ms=round(orchestrator_duration, 2),
            metadata={
                "session_id": mdt_session_summary.get("session_id", ""),
                "total_recommendations": mdt_session_summary.get("total_recommendations", 0),
                "agents_involved": [str(a) for a in mdt_session_summary.get("agents_involved", [])],
                "consensus_levels": [
                    r.get("consensus_level") for r in mdt_session_summary.get("consensus_results", [])
                ],
            },
        )
        reasoning_chain.append({
            "step": step_order,
            "type": "orchestrator_consensus",
            "summary": (
                f"Multi-agent deliberation: {len(mdt_session_summary.get('consensus_results', []))} "
                f"consensus recommendations"
            ),
            "duration_ms": round(orchestrator_duration, 2),
            "details": {
                "agents": [str(a) for a in mdt_session_summary.get("agents_involved", [])],
                "recommendations": len(mdt_session_summary.get("consensus_results", [])),
            },
        })
    except Exception as e:
        DegradationContext.record_stage_failure("orchestrator_provenance", e, None)
        logger.warning(f"Failed to record orchestrator provenance: {e}")

    # =============================================================================
    # Clinical Calculator Integration: Run applicable calculators
    # =============================================================================
    calculator_start = time.perf_counter()
    calculator_context = ""
    calculator_results_data: list[dict] = []
    try:
        from app.services.calculator_reasoning_service import get_calculator_reasoning_service

        calc_service = get_calculator_reasoning_service()

        # Build measurement list from KG nodes
        patient_measurements = []
        for node in nodes:
            if node.node_type == NodeType.MEASUREMENT:
                measurement = {
                    "label": node.label,
                    "value": node.properties.get("value", "") if node.properties else "",
                    "unit": node.properties.get("unit", "") if node.properties else "",
                }
                patient_measurements.append(measurement)

        # Build demographics from KG (if available)
        patient_demographics = {}
        for node in nodes:
            if node.node_type == NodeType.PATIENT and node.properties:
                if "age" in node.properties:
                    patient_demographics["age"] = node.properties["age"]
                if "sex" in node.properties:
                    patient_demographics["sex"] = node.properties["sex"]

        # Run applicable calculators
        calculator_results = calc_service.run_applicable_calculators(
            conditions=conditions,
            measurements=patient_measurements,
            demographics=patient_demographics,
            clinical_question=request.question,
            min_relevance=1.5,
            min_data_completeness=0.3,
            max_calculators=5,
        )

        if calculator_results:
            calculator_context = calc_service.generate_calculator_context_for_llm(calculator_results)
            calculator_results_data = calculator_results

            logger.info(
                f"Calculator reasoning: ran {len(calculator_results)} calculators for patient {patient_id}"
            )

    except Exception as e:
        DegradationContext.record_stage_failure("calculator_reasoning", e, [])
        logger.warning(f"Calculator reasoning failed, proceeding without: {e}")

    calculator_duration = (time.perf_counter() - calculator_start) * 1000

    # Record CALCULATOR_REASONING reasoning trace
    if calculator_results_data:
        try:
            step_order += 1
            await provenance_svc.create_reasoning_trace(
                session=db,
                query_id=query_id,
                step_order=step_order,
                step_type="calculator_reasoning",
                patient_id=patient_id,
                input_summary=f"Query: '{request.question}', {len(patient_measurements)} measurements",
                output_summary=f"Ran {len(calculator_results_data)} clinical calculators",
                duration_ms=round(calculator_duration, 2),
                metadata={
                    "calculators_run": [c["calculator_id"] for c in calculator_results_data],
                    "scores": {c["calculator_id"]: c["score"] for c in calculator_results_data},
                    "risk_levels": {c["calculator_id"]: c.get("risk_level") for c in calculator_results_data},
                },
            )
            reasoning_chain.append({
                "step": step_order,
                "type": "calculator_reasoning",
                "summary": f"Ran {len(calculator_results_data)} clinical calculators",
                "duration_ms": round(calculator_duration, 2),
                "details": {
                    "calculators": [c["calculator_id"] for c in calculator_results_data],
                    "scores": {c["calculator_id"]: c["score"] for c in calculator_results_data},
                },
            })
        except Exception as e:
            DegradationContext.record_stage_failure("calculator_provenance", e, None)
            logger.warning(f"Failed to record calculator provenance: {e}")

    # Use LLM to generate answer
    llm_available = False
    fallback_used = False
    fallback_reason_code: str | None = None
    llm_start = time.perf_counter()
    try:
        from app.services.llm_service import get_llm_service, LLMProvider

        llm = get_llm_service()

        system_prompt = """You are a clinical decision support assistant analyzing a patient's electronic health record data.
You have access to a knowledge graph built from the patient's clinical notes, including multi-hop relationship paths.
You also have input from a multi-disciplinary clinical team (Diagnostic, Treatment, Safety, Evidence specialists).
You can use clinical calculators (risk scores, physiologic equations) to quantify patient risk and status.

Guidelines:
- Answer questions based ONLY on the provided clinical data, graph evidence, guideline references, calculator results, and agent consensus
- Be specific and cite relevant entities from the knowledge graph
- When graph evidence paths are provided, use them to explain relationships between clinical entities
- When clinical guideline references are provided, incorporate them into your answer using [Guideline N] citation format
- When institutional policy references are provided, incorporate them using [Policy N] citation format
- When clinical calculator results are provided, use them to quantify risk levels and support recommendations
- When agent consensus is provided, synthesize their recommendations and note any dissenting concerns
- Distinguish between patient-specific data (from the knowledge graph) and general recommendations (from guidelines)
- If agents have conflicting views, acknowledge the disagreement and explain the reasoning
- If the data is insufficient, say so clearly
- Use clinical terminology appropriately
- Keep answers concise but thorough (2-4 sentences for simple questions, more for complex ones)
- Never fabricate information not present in the data, guidelines, calculators, or agent consensus"""

        # Include graph RAG context if available (multi-hop traversal paths and temporal context)
        full_context = clinical_context
        if graph_context:
            full_context += "\n\n" + graph_context
        full_context += guideline_context + consensus_context
        if calculator_context:
            full_context += "\n\n" + calculator_context

        user_prompt = f"""{full_context}

Question: {request.question}

Provide a clear, evidence-based answer synthesizing the clinical data, graph relationships, and agent consensus above."""
        if guideline_citations_data:
            user_prompt += " Reference relevant guidelines using [Guideline N] citations where applicable."
        if policy_citations_data:
            user_prompt += " Reference relevant policies using [Policy N] citations where applicable."
        if calculator_results_data:
            user_prompt += " Include relevant calculator scores and risk levels in your assessment."
        if consensus_context:
            user_prompt += " Note any significant agent consensus or dissenting opinions."

        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            # Uses BYOK config — whatever provider/model is set in Settings > AI / LLM
            model=settings.llm_model,
            max_tokens=1024,
            temperature=0.2,
        )

        answer = response.content
        model_used = response.model
        llm_available = True
        confidence = min(0.95, 0.6 + len(relevant_entities) * 0.03 + len(evidence_sources) * 0.08)
        # Boost confidence for guideline matches
        confidence = min(0.95, confidence + len(guideline_citations_data) * 0.05)
        # Boost confidence for graph RAG multi-hop paths
        confidence = min(0.95, confidence + len(graph_paths_data) * 0.02)
        # Boost confidence for strong/unanimous agent consensus
        consensus_results = mdt_session_summary.get("consensus_results", [])
        strong_consensus_count = sum(
            1 for r in consensus_results
            if r.get("consensus_level") in ("unanimous", "strong")
        )
        confidence = min(0.95, confidence + strong_consensus_count * 0.04)
        # Boost confidence for calculator results
        confidence = min(0.95, confidence + len(calculator_results_data) * 0.03)

        guideline_info = f", {len(guideline_citations_data)} guideline references" if guideline_citations_data else ""
        graph_rag_info = f", {len(graph_paths_data)} graph paths" if graph_paths_data else ""
        orchestrator_info = (
            f", {len(consensus_results)} agent recommendations "
            f"({strong_consensus_count} strong/unanimous)"
            if consensus_results else ""
        )
        calculator_info = f", {len(calculator_results_data)} calculators" if calculator_results_data else ""
        reasoning = (
            f"Answered using {model_used} with {len(nodes)} KG nodes, "
            f"{len(evidence_sources)} evidence sources{graph_rag_info}{guideline_info}{calculator_info}{orchestrator_info}. "
            f"Latency: {response.latency_ms:.0f}ms, "
            f"Tokens: {response.token_usage.total_tokens}"
        )

        llm_duration = (time.perf_counter() - llm_start) * 1000

        # Step 6: Record LLM_INFERENCE reasoning trace
        try:
            step_order += 1
            llm_trace = await provenance_svc.create_reasoning_trace(
                session=db,
                query_id=query_id,
                step_order=step_order,
                step_type=ReasoningStepType.LLM_INFERENCE.value,
                patient_id=patient_id,
                input_summary=f"Model: {model_used}, prompt tokens ~{len(user_prompt.split())}",
                output_summary=f"Generated answer, confidence: {confidence:.2f}",
                duration_ms=round(llm_duration, 2),
                metadata={
                    "model": model_used,
                    "latency_ms": response.latency_ms,
                    "total_tokens": response.token_usage.total_tokens,
                    "confidence": round(confidence, 4),
                },
            )
            reasoning_chain.append({
                "step": step_order,
                "type": "llm_inference",
                "summary": f"Generated answer using {model_used}",
                "duration_ms": round(llm_duration, 2),
                "details": {
                    "model": model_used,
                    "tokens": response.token_usage.total_tokens,
                    "confidence": round(confidence, 4),
                },
            })
        except Exception as e:
            DegradationContext.record_stage_failure("llm_provenance", e, None)
            logger.warning(f"Failed to record LLM provenance: {e}")

    except Exception as e:
        DegradationContext.record_stage_failure("llm_generation", e, None)
        logger.warning(f"LLM query failed, falling back to template: {e}")
        # P1-019: Record fallback usage
        fallback_used = True
        fallback_reason_code = "llm_unavailable"
        # Fallback to simple template if LLM fails
        if query_type == "medication":
            meds_list = [e.text for e in relevant_entities if e.entity_type.upper() == "DRUG"]
            answer = f"The patient is taking: {', '.join(meds_list[:10])}." if meds_list else "No medications found."
        elif query_type == "condition":
            conds_list = [e.text for e in relevant_entities if e.entity_type.upper() == "CONDITION"]
            answer = f"The patient has: {', '.join(conds_list[:10])}." if conds_list else "No conditions found."
        else:
            answer = f"Found {len(relevant_entities)} relevant findings." if relevant_entities else "No relevant information found."
        confidence = 0.5
        reasoning = f"Fallback template (LLM error: {e}). Query type: '{query_type}'."

    # Step 7: Record confidence contributions per step
    try:
        kg_confidence = len(relevant_entities) * 0.03
        graph_rag_confidence = len(graph_paths_data) * 0.02  # Multi-hop graph paths
        rag_confidence = len(guideline_citations_data) * 0.05
        evidence_confidence = len(evidence_sources) * 0.08
        # Calculate orchestrator confidence contribution from strong/unanimous consensus
        mdt_consensus_results = mdt_session_summary.get("consensus_results", [])
        orchestrator_confidence = sum(
            0.04 for r in mdt_consensus_results
            if r.get("consensus_level") in ("unanimous", "strong")
        )
        base_confidence = 0.6

        traces = await provenance_svc.get_reasoning_for_query(db, query_id)
        for trace in traces:
            if trace.step_type == ReasoningStepType.KG_RETRIEVAL.value:
                await provenance_svc.update_reasoning_trace_confidence(
                    db, trace.id, round(kg_confidence, 4)
                )
            elif trace.step_type == ReasoningStepType.GRAPH_RAG_RETRIEVAL.value:
                await provenance_svc.update_reasoning_trace_confidence(
                    db, trace.id, round(graph_rag_confidence, 4)
                )
            elif trace.step_type == ReasoningStepType.RAG_SEARCH.value:
                await provenance_svc.update_reasoning_trace_confidence(
                    db, trace.id, round(rag_confidence + evidence_confidence, 4)
                )
            elif trace.step_type == ReasoningStepType.ORCHESTRATOR_CONSENSUS.value:
                await provenance_svc.update_reasoning_trace_confidence(
                    db, trace.id, round(orchestrator_confidence, 4)
                )
            elif trace.step_type == ReasoningStepType.LLM_INFERENCE.value:
                await provenance_svc.update_reasoning_trace_confidence(
                    db, trace.id, round(base_confidence, 4)
                )
    except Exception as e:
        DegradationContext.record_stage_failure("confidence_update", e, None)
        logger.warning(f"Failed to update confidence contributions: {e}")

    # Build entity provenance (if depth != none)
    if provenance_depth != "none":
        for entity in relevant_entities[:10]:
            entity_provenance_data.append({
                "text": entity.text,
                "entity_type": entity.entity_type,
                "confidence": entity.confidence,
                "note_id": entity.note_id,
            })

    # Build sources list including both documents and guidelines
    sources = [f"Document: {e.note_id}" for e in evidence_sources]
    for gc in guideline_citations_data:
        sources.append(f"Guideline: {gc['guideline']} — {gc['section_title']}")
    for pc in policy_citations_data:
        sources.append(f"Policy: {pc['policy_name']} — {pc['section_title']}")

    # P0-023: Collect source document IDs from documents and KG node provenance
    source_document_ids: list[str] = []
    for ev in evidence_sources:
        if ev.note_id and ev.note_id not in source_document_ids:
            source_document_ids.append(ev.note_id)
    for node in matching_nodes:
        if node.properties:
            for src_note in node.properties.get("source_notes", []):
                if src_note and src_note not in source_document_ids:
                    source_document_ids.append(src_note)
    # Also include document model IDs used in evidence search
    for doc in documents:
        doc_id = doc.extra_metadata.get("original_note_id", str(doc.id)) if doc.extra_metadata else str(doc.id)
        if doc_id not in source_document_ids and any(
            ev.note_id == doc_id for ev in evidence_sources
        ):
            source_document_ids.append(doc_id)

    # P0-023: Determine provenance completeness
    provenance_complete = True
    if answer and answer.strip() and not source_document_ids:
        provenance_complete = False
        logger.warning(
            f"P0-023: Query {query_id} produced non-empty answer but has no source_document_ids. "
            "Provenance incomplete."
        )

    # P0-022: Decline behavior — decline when evidence is insufficient
    declined = False
    decline_reason: str | None = None
    escalation_path: str | None = None

    if confidence < 0.3 or (len(evidence_sources) == 0 and len(matching_nodes) == 0):
        declined = True
        if confidence < 0.3 and len(evidence_sources) == 0 and len(matching_nodes) == 0:
            decline_reason = (
                "Insufficient evidence: no matching clinical documents or knowledge graph "
                "entities found, and confidence is below the safety threshold (0.3)."
            )
        elif confidence < 0.3:
            decline_reason = (
                f"Confidence ({confidence:.2f}) is below the safety threshold (0.3). "
                "The available evidence is not sufficient to support a reliable answer."
            )
        else:
            decline_reason = (
                "No supporting evidence found in clinical documents or knowledge graph. "
                "Cannot provide an evidence-bound answer."
            )
        escalation_path = "Consult clinical team"
        # Override answer for declined responses
        answer = ""
        reasoning = (reasoning or "") + f" [DECLINED: {decline_reason}]"
        logger.info(
            f"P0-022: Query {query_id} declined — confidence={confidence:.2f}, "
            f"evidence_sources={len(evidence_sources)}, matching_nodes={len(matching_nodes)}"
        )

    # Commit provenance records
    try:
        await db.flush()
    except Exception as e:
        DegradationContext.record_stage_failure("provenance_flush", e, None)
        logger.warning(f"Failed to flush provenance records: {e}")

    # P0-021: Confidence-to-action policy gate
    gate_result = check_action_gate(confidence, "recommendation")

    # P1-001: Compute evidence-weighted confidence with rationale
    avg_extraction_quality = (
        sum(e.confidence for e in relevant_entities) / len(relevant_entities)
        if relevant_entities else 0.5
    )
    mdt_consensus_for_score = mdt_session_summary.get("consensus_results", [])
    strong_consensus_for_score = sum(
        1 for r in mdt_consensus_for_score
        if r.get("consensus_level") in ("unanimous", "strong")
    )
    ew_score, ew_rationale = compute_evidence_weighted_confidence(
        kg_node_count=len(matching_nodes),
        document_count=len(evidence_sources),
        guideline_count=len(guideline_citations_data),
        extraction_quality=avg_extraction_quality,
        graph_path_count=len(graph_paths_data),
        consensus_strong_count=strong_consensus_for_score,
        calculator_count=len(calculator_results_data),
    )

    # P1-002: Build structured confidence breakdown
    confidence_components = [
        ConfidenceComponent(
            source=ConfidenceSource.EXTRACTION,
            score=round(min(len(relevant_entities) * 0.03, 1.0), 4),
            weight=0.25,
            method="entity_count_heuristic",
        ),
        ConfidenceComponent(
            source=ConfidenceSource.KG,
            score=round(min(len(graph_paths_data) * 0.10, 1.0), 4),
            weight=0.25,
            method="graph_path_count",
        ),
        ConfidenceComponent(
            source=ConfidenceSource.REASONING,
            score=round(min(len(guideline_citations_data) * 0.25, 1.0), 4),
            weight=0.25,
            method="guideline_match_count",
        ),
        ConfidenceComponent(
            source=ConfidenceSource.FINAL,
            score=round(confidence, 4),
            weight=0.25,
            method="aggregate_heuristic",
        ),
    ]
    confidence_bd = ConfidenceBreakdown(
        components=confidence_components,
        aggregate_score=round(confidence, 4),
        aggregate_method="weighted_mean",
    )

    # P1-005: Compute note processing coverage metrics
    total_docs = len(documents)
    processed_docs = sum(
        1 for d in documents if d.processed_at is not None
    )
    failed_docs = total_docs - processed_docs
    coverage_pct = (processed_docs / total_docs * 100.0) if total_docs > 0 else 100.0

    # P1-006: Determine data freshness from document metadata
    data_freshness: str | None = None
    last_ingestion: str | None = None
    if documents:
        # Find the most recently processed document
        processed_timestamps = [
            d.processed_at for d in documents if d.processed_at is not None
        ]
        if processed_timestamps:
            latest = max(processed_timestamps)
            data_freshness = latest.isoformat()
            last_ingestion = latest.isoformat()

    # P2-007: Classify uncertainty reasons
    _dep_state = {
        "kg_available": len(nodes) > 0,
        "documents_available": len(documents) > 0,
        "llm_available": llm_available,
    }
    uncertainty_reasons = classify_uncertainty(
        confidence=confidence,
        evidence_count=len(evidence_sources),
        kg_node_count=len(matching_nodes),
        dependency_state=_dep_state,
        fallback_used=fallback_used,
    )

    return HybridQueryResponse(
        question=request.question,
        answer=answer,
        confidence=round(confidence, 2),
        sources=sources,
        entities_found=relevant_entities[:request.max_results],
        evidence=evidence_sources if request.include_evidence else [],
        knowledge_graph_paths=graph_paths_data,  # Multi-hop graph traversal paths
        reasoning=reasoning,
        guideline_citations=guideline_citations_data,
        query_id=query_id,
        reasoning_chain=reasoning_chain if provenance_depth != "none" else [],
        entity_provenance=entity_provenance_data if provenance_depth == "full" else [],
        policy_citations=policy_citations_data,
        provenance_url=f"/api/v1/clinical-agent/provenance/{query_id}",
        # P0-022: Decline behavior
        declined=declined,
        decline_reason=decline_reason,
        escalation_path=escalation_path,
        # P0-023: Source document provenance
        source_document_ids=source_document_ids,
        provenance_complete=provenance_complete,
        # P0-004: Surface dependency availability in all query responses
        dependency_state=_dep_state,
        # P0-021: Confidence-to-action gate
        action_gate=gate_result.model_dump(),
        # P1-001: Evidence-weighted confidence rationale
        confidence_rationale=ew_rationale,
        # P1-002: Structured confidence breakdown
        confidence_breakdown=confidence_bd,
        # P1-005: Note processing coverage
        notes_processed=processed_docs,
        notes_failed=failed_docs,
        coverage_percent=round(coverage_pct, 2),
        # P1-006: Data freshness
        data_freshness_iso=data_freshness,
        last_ingestion_ts=last_ingestion,
        # P1-019: Fallback indicators
        fallback_used=fallback_used,
        fallback_reason_code=fallback_reason_code,
        # P2-007: Uncertainty reasons
        uncertainty_reasons=uncertainty_reasons,
        # Phase 1 Safety Envelope: Degradation snapshot
        degradation=DegradationContext.snapshot(),
    )


@router.delete(
    "/graph/{patient_id}",
    summary="Delete patient knowledge graph",
    description="Remove all knowledge graph data for a patient.",
)
async def delete_patient_graph(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.WRITE_CLINICAL_FACTS])),
) -> dict:
    """Delete a patient's knowledge graph.

    VP-Transactions-1: Uses nested transaction (savepoint) to ensure
    atomicity of edge and node deletion. If any operation fails,
    both are rolled back.
    """
    # VP-Transactions-1: Use nested transaction for atomic cleanup
    async with db.begin_nested():
        # Delete edges first (foreign key constraint)
        edges_result = await db.execute(
            delete(KGEdge).where(KGEdge.patient_id == patient_id)
        )
        edges_deleted = edges_result.rowcount

        # Delete nodes
        nodes_result = await db.execute(
            delete(KGNode).where(KGNode.patient_id == patient_id)
        )
        nodes_deleted = nodes_result.rowcount

    # Note: get_db() dependency handles final commit/rollback

    return {
        "patient_id": patient_id,
        "nodes_deleted": nodes_deleted,
        "edges_deleted": edges_deleted,
    }


@router.get(
    "/patients",
    summary="List patients with knowledge graphs",
    description="Get list of patients that have knowledge graphs.",
)
async def list_patients_with_graphs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.READ_PATIENTS])),
) -> dict:
    """List patients with knowledge graphs."""

    # Get distinct patient IDs with node counts
    result = await db.execute(
        select(
            KGNode.patient_id,
            func.count(KGNode.id).label("node_count")
        )
        .group_by(KGNode.patient_id)
        .order_by(func.count(KGNode.id).desc())
        .offset(offset)
        .limit(limit)
    )

    patients = [
        {"patient_id": row[0], "node_count": row[1]}
        for row in result.all()
    ]

    return {
        "total": len(patients),
        "patients": patients,
    }


# =============================================================================
# Provenance Endpoints (Steps 8, 17, 19)
# =============================================================================


@router.get(
    "/provenance/{query_id}",
    summary="Get provenance for a query",
    description="Retrieve reasoning traces and provenance records for a specific query.",
)
async def get_query_provenance(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.READ_LINEAGE])),
) -> dict:
    """Get reasoning traces for a hybrid query."""
    provenance_svc = get_provenance_db_service()

    traces = await provenance_svc.get_reasoning_for_query(db, query_id)
    if not traces:
        raise HTTPException(status_code=404, detail=f"No provenance found for query {query_id}")

    return {
        "query_id": query_id,
        "reasoning_traces": [
            {
                "id": t.id,
                "step_order": t.step_order,
                "step_type": t.step_type,
                "input_summary": t.input_summary,
                "output_summary": t.output_summary,
                "confidence_contribution": t.confidence_contribution,
                "duration_ms": t.duration_ms,
                "metadata": t.extra_metadata,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in traces
        ],
        "total_steps": len(traces),
        "total_duration_ms": round(sum(t.duration_ms or 0 for t in traces), 2),
    }


@router.get(
    "/lineage/{patient_id}/{node_id}",
    summary="Get fact lineage for a KG node",
    description="Trace a KG node back to its source document and original text.",
)
async def get_fact_lineage(
    patient_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm: None = Depends(PermissionChecker([Permission.READ_LINEAGE])),
) -> dict:
    """Get the lineage chain: KG node → ProvenanceRecord → SourceDocument → text."""
    HOP_DECAY = 0.9

    # Get the KG node
    node_result = await db.execute(
        select(KGNode).where(KGNode.id == node_id, KGNode.patient_id == patient_id)
    )
    node = node_result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    provenance_svc = get_provenance_db_service()
    chain = await provenance_svc.get_provenance_chain(db, "kg_node", node_id)

    # If no explicit provenance records, create one from node.properties
    if not chain.get("provenance_records") and node.properties:
        props = node.properties
        # Build provenance record from node properties
        fallback_record = {
            "extraction_method": props.get("extraction_method", "unknown"),
            "confidence_score": props.get("extraction_confidence") or props.get("confidence"),
            "confidence_level": "high" if (props.get("extraction_confidence") or props.get("confidence", 0)) >= 0.8 else "medium",
            "extracted_text": node.label,
            "recorded_at": props.get("recorded_at"),
            "source_notes": props.get("source_notes", []),
            # TODO: Read from edge.properties once shared concept migration is complete
            "assertion": props.get("assertion"),
            "negation_trigger": props.get("negation_trigger"),
            "negation_trigger_confidence": props.get("negation_trigger_confidence"),
        }
        # Remove None values
        fallback_record = {k: v for k, v in fallback_record.items() if v is not None}
        chain["provenance_records"] = [fallback_record]

    # Enrich with source document info
    for record in chain.get("provenance_records", []):
        doc_id = record.get("source_document_id")
        if doc_id:
            doc_result = await db.execute(
                select(DocumentModel).where(DocumentModel.id == doc_id)
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                record["source_document"] = {
                    "id": str(doc.id),
                    "note_type": doc.note_type,
                    "note_date": doc.extra_metadata.get("note_date", "unknown") if doc.extra_metadata else "unknown",
                    "text_length": len(doc.text) if doc.text else 0,
                }

    return {
        "patient_id": patient_id,
        "node": {
            "id": str(node.id),
            "label": node.label,
            "node_type": node.node_type.value if hasattr(node.node_type, 'value') else str(node.node_type),
            "omop_concept_id": node.omop_concept_id,
        },
        "provenance_chain": chain,
        "hop_decay": HOP_DECAY,
    }


@router.get(
    "/provenance-chain/{query_id}",
    summary="Get full provenance chain for a query",
    description="Returns nested traversal: Query → Steps → Entities/Guidelines → Source Docs.",
)
async def get_full_provenance_chain(
    query_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the complete provenance chain with nested entity/guideline details."""
    provenance_svc = get_provenance_db_service()

    traces = await provenance_svc.get_reasoning_for_query(db, query_id)
    if not traces:
        raise HTTPException(status_code=404, detail=f"No provenance found for query {query_id}")

    patient_id = traces[0].patient_id if traces else None

    steps = []
    for trace in traces:
        step_data: dict[str, Any] = {
            "step_order": trace.step_order,
            "step_type": trace.step_type,
            "input_summary": trace.input_summary,
            "output_summary": trace.output_summary,
            "confidence_contribution": trace.confidence_contribution,
            "duration_ms": trace.duration_ms,
            "metadata": trace.extra_metadata,
        }

        # For KG steps, include entity provenance
        if trace.step_type == ReasoningStepType.KG_RETRIEVAL.value and trace.extra_metadata:
            entity_labels = trace.extra_metadata.get("entity_labels", [])
            step_data["entities"] = entity_labels

        # For RAG steps, include guideline citation provenance
        if trace.step_type == ReasoningStepType.RAG_SEARCH.value:
            guideline_prov = await provenance_svc.get_provenance_for_entity(
                db, "guideline_citation", ""
            )
            # Filter to this query
            step_data["guideline_provenance"] = [
                {
                    "section_id": p.entity_id,
                    "relevance_score": p.confidence_score,
                    "evidence_grade": (p.extra_metadata or {}).get("evidence_grade"),
                    "recommendation_level": (p.extra_metadata or {}).get("recommendation_level"),
                }
                for p in guideline_prov
                if p.extra_metadata and p.extra_metadata.get("query_id") == query_id
            ]

        steps.append(step_data)

    return {
        "query_id": query_id,
        "patient_id": patient_id,
        "steps": steps,
        "total_steps": len(steps),
        "total_duration_ms": round(sum(t.duration_ms or 0 for t in traces), 2),
        "total_confidence": round(sum(t.confidence_contribution or 0 for t in traces), 4),
    }
