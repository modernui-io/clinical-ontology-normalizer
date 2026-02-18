"""Knowledge Graph schemas (KGNode, KGEdge)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Types of nodes in the knowledge graph."""

    PATIENT = "patient"
    CONDITION = "condition"
    DRUG = "drug"
    MEASUREMENT = "measurement"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    # Provenance nodes
    CLINICAL_NOTE = "clinical_note"
    # Temporal nodes
    DATE = "date"
    # Narrative nodes (clinical course tracking)
    ADMISSION = "admission"
    CLINICAL_EVENT = "clinical_event"
    HOSPITAL_COURSE = "hospital_course"
    DISCHARGE = "discharge"
    EPISODE = "episode"


class EdgeType(str, Enum):
    """Types of edges in the knowledge graph."""

    # Patient -> Entity edges
    HAS_CONDITION = "has_condition"
    TAKES_DRUG = "takes_drug"
    HAS_MEASUREMENT = "has_measurement"
    HAS_PROCEDURE = "has_procedure"
    HAS_OBSERVATION = "has_observation"

    # Entity -> Entity edges (clinical relationships)
    CONDITION_TREATED_BY = "condition_treated_by"
    DRUG_TREATS = "drug_treats"
    SYMPTOM_OF = "symptom_of"  # Symptom -> Condition relationship
    MONITORS = "monitors"  # Measurement -> Condition relationship
    RELATED_TO = "related_to"  # Generic entity relationship
    MAY_CAUSE = "may_cause"  # Drug -> Side effect relationship
    CONTRAINDICATED_WITH = "contraindicated_with"  # Drug -> Drug/Condition contraindication
    DRUG_INTERACTION = "drug_interaction"  # Drug -> Drug interaction (OMOP)

    # OMOP lateral relationship edges (concept -> concept)
    HAS_FINDING_SITE = "has_finding_site"  # Condition -> Anatomy
    HAS_MORPHOLOGY = "has_morphology"  # Condition -> Morphology

    # Provenance edges (Entity -> Note)
    EXTRACTED_FROM = "extracted_from"  # Entity was extracted from this clinical note

    # Temporal edges (Entity -> Date)
    OCCURRED_ON = "occurred_on"  # Entity occurred/was recorded on this date

    # Narrative edges (clinical course relationships)
    ADMITTED_FOR = "admitted_for"  # Admission -> Condition (reason for admission)
    HAS_EPISODE = "has_episode"  # Patient -> Episode (hospitalization episode)
    PART_OF_EPISODE = "part_of_episode"  # Event/Node -> Episode (belongs to episode)
    PRECEDES = "precedes"  # Event -> Event (temporal ordering)
    FOLLOWS = "follows"  # Event -> Event (temporal ordering, inverse of PRECEDES)
    CAUSED_BY = "caused_by"  # Event -> Event/Condition (causal relationship)
    RESULTED_IN = "resulted_in"  # Event/Condition -> Event/Condition (causal outcome)
    DISCHARGED_WITH = "discharged_with"  # Discharge -> Condition/Plan (discharge outcome)


class TemporalOrder(str, Enum):
    """Temporal ordering relationships based on Allen's interval algebra.

    Used to express temporal relationships between events/facts:
    - BEFORE: Event A ends before event B starts
    - AFTER: Event A starts after event B ends
    - DURING: Event A occurs within the timespan of event B
    - CONTAINS: Event A contains event B (inverse of DURING)
    - OVERLAPS: Event A overlaps with the start of event B
    - STARTS: Event A starts at the same time as event B
    - FINISHES: Event A ends at the same time as event B
    - CONCURRENT: Events A and B occur at approximately the same time
    - UNKNOWN: Temporal relationship cannot be determined
    """

    BEFORE = "before"
    AFTER = "after"
    DURING = "during"
    CONTAINS = "contains"
    OVERLAPS = "overlaps"
    STARTS = "starts"
    FINISHES = "finishes"
    CONCURRENT = "concurrent"
    UNKNOWN = "unknown"


class KGNodeCreate(BaseModel):
    """Schema for creating a knowledge graph node.

    Base schema with core node fields. Used for node creation
    and as a base class for the full KGNode response schema.

    patient_id is None for shared concept nodes (conditions, drugs, etc.)
    that are deduplicated across patients. Patient nodes always have patient_id set.
    """

    patient_id: str | None = Field(None, description="Patient this node belongs to (None for shared concept nodes)")
    node_type: NodeType = Field(..., description="Type of node")
    omop_concept_id: int | None = Field(
        None, description="OMOP concept ID (null for patient nodes)"
    )
    label: str = Field(..., description="Human-readable label")
    properties: dict = Field(default_factory=dict, description="Node-specific properties")


class KGNode(KGNodeCreate):
    """Schema for a knowledge graph node response.

    Extends KGNodeCreate with server-generated fields (id, created_at).

    Nodes represent entities in the patient's clinical knowledge graph:
    - Patient node: Central node for the patient
    - Condition nodes: Diagnoses, symptoms, findings
    - Drug nodes: Medications
    - Measurement nodes: Lab values, vitals
    - Procedure nodes: Surgeries, interventions

    Properties contain node-specific data like assertion status for conditions.
    """

    id: UUID = Field(..., description="Unique node identifier")
    created_at: datetime = Field(..., description="When node was created")

    model_config = {"from_attributes": True}


class Temporality(str, Enum):
    """Temporal assertion from NLP extraction."""

    CURRENT = "current"  # Happening now / ongoing
    PAST = "past"  # Historical / happened before
    FUTURE = "future"  # Planned / anticipated


class KGEdgeCreate(BaseModel):
    """Schema for creating a knowledge graph edge.

    Base schema with core edge fields. Used for edge creation
    and as a base class for the full KGEdge response schema.
    """

    patient_id: str = Field(..., description="Patient this edge belongs to")
    source_node_id: UUID = Field(..., description="Source node ID")
    target_node_id: UUID = Field(..., description="Target node ID")
    edge_type: EdgeType = Field(..., description="Type of relationship")
    fact_id: UUID | None = Field(None, description="Source clinical fact ID")
    properties: dict = Field(default_factory=dict, description="Edge-specific properties")

    # Valid Time: When the clinical event happened in the real world
    event_date: datetime | None = Field(
        None, description="When this clinical event occurred (point in time)"
    )
    valid_from: datetime | None = Field(
        None, description="When this relationship became true (start of validity)"
    )
    valid_to: datetime | None = Field(
        None, description="When this relationship ceased to be true (null = ongoing)"
    )

    # Transaction Time: Provenance - when/where we learned about it
    recorded_at: datetime | None = Field(
        None, description="When this was recorded in the source system"
    )
    source_document_date: datetime | None = Field(
        None, description="Date of the source document (note date, lab date)"
    )

    # Temporal Assertion from NLP
    temporality: Temporality | None = Field(
        None, description="Temporal assertion: current, past, future"
    )

    # Temporal ordering and confidence
    temporal_order: TemporalOrder | None = Field(
        None, description="Temporal ordering vs related events"
    )
    temporal_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence in temporal assertions (0-1)"
    )


class KGEdge(KGEdgeCreate):
    """Schema for a knowledge graph edge response.

    Extends KGEdgeCreate with server-generated fields (id, created_at).

    Edges represent relationships between nodes:
    - has_condition: Patient -> Condition
    - takes_drug: Patient -> Drug
    - has_measurement: Patient -> Measurement
    - condition_treated_by: Condition -> Drug

    Bi-Temporal Fields:
    1. Valid Time (Event Time): When the clinical event happened
       - event_date: Point in time (e.g., "diagnosed on 2023-03-15")
       - valid_from/to: Validity period (e.g., "on med from Jan-June 2023")

    2. Transaction Time (Record Time): Provenance - when we learned about it
       - recorded_at: When recorded in source system
       - source_document_date: Date of the source document
       - created_at: When created in our KG

    3. Temporal Assertion: From NLP extraction
       - temporality: current, past, future
    """

    id: UUID = Field(..., description="Unique edge identifier")
    created_at: datetime = Field(..., description="When edge was created in KG")

    model_config = {"from_attributes": True}


class PatientGraph(BaseModel):
    """Schema for a complete patient knowledge graph.

    Used for API responses when fetching a patient's full graph.
    """

    patient_id: str = Field(..., description="Patient identifier")
    nodes: list[KGNode] = Field(default_factory=list, description="All nodes in the graph")
    edges: list[KGEdge] = Field(default_factory=list, description="All edges in the graph")
    node_count: int = Field(0, description="Total number of nodes")
    edge_count: int = Field(0, description="Total number of edges")

    def model_post_init(self, __context: dict) -> None:
        """Update counts after initialization."""
        object.__setattr__(self, "node_count", len(self.nodes))
        object.__setattr__(self, "edge_count", len(self.edges))


class ConceptPatientsResponse(BaseModel):
    """Response for cross-patient concept query."""

    omop_concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="Human-readable concept name")
    node_type: str = Field(..., description="Node type (condition, drug, etc.)")
    patient_ids: list[str] = Field(default_factory=list, description="Patient IDs with this concept")
    patient_count: int = Field(0, description="Number of patients with this concept")


class GlobalConceptEntry(BaseModel):
    """A single shared concept in the global graph."""

    node_id: str = Field(..., description="Shared node UUID")
    omop_concept_id: int | None = Field(None, description="OMOP concept ID")
    node_type: str = Field(..., description="Node type")
    label: str = Field(..., description="Concept label")
    patient_count: int = Field(0, description="Number of patients connected")


class GlobalGraphResponse(BaseModel):
    """Response for global concept graph query."""

    concepts: list[GlobalConceptEntry] = Field(default_factory=list)
    total_concepts: int = Field(0, description="Total shared concepts returned")


class ConceptStatisticsResponse(BaseModel):
    """Statistics for a shared concept across patients."""

    omop_concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="Human-readable concept name")
    node_type: str = Field(..., description="Node type")
    patient_count: int = Field(0, description="Number of patients")
    assertion_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Count of each assertion type (present, absent, possible)",
    )
