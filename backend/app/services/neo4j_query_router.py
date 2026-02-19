"""Multi-hop graph traversal via PostgreSQL.

Traverses both patient edges (kg_edges) and OMOP vocabulary
relationships (concept_relationships) in a single recursive CTE.
No Neo4j required — all 3M+ relationships queried directly in PG.
"""
# MODULE: graph_rag
# MATURITY: pilot

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.models.knowledge_graph import KGEdge, KGNode

logger = logging.getLogger(__name__)

# Scale-safety guardrails: clamp unbounded queries
MAX_HOPS_LIMIT = 10
MAX_PATHS_LIMIT = 100

# Map OMOP relationship_id to our EdgeType values
OMOP_REL_TO_EDGE_TYPE: dict[str, str] = {
    # Treatment relationships
    "May treat": "drug_treats",
    "May be treated by": "condition_treated_by",
    "May cause": "may_cause",
    "May prevent": "may_prevent",
    "May be prevented by": "prevented_by",
    "May diagnose": "may_diagnose",
    "Diagnosed through": "diagnosed_through",
    # Safety relationships
    "CI by": "contraindicated_with",
    "CI to": "contraindicated_with",
    "Drug-drug inter for": "interacts_with",
    "Has drug-drug inter": "interacts_with",
    "Induces": "induces",
    "Induced by": "induced_by",
    "Inhibits effect": "inhibits_effect",
    "May be inhibited by": "inhibited_by",
    # Pharmacology
    "Has MoA": "has_mechanism_of_action",
    "MoA of": "mechanism_of_action_of",
    "Has physio effect": "has_physiologic_effect",
    "Physiol effect by": "physiologic_effect_of",
    "Has PK": "has_pharmacokinetics",
    "PK of": "pharmacokinetics_of",
    "Has metabolism": "has_metabolism",
    "Metabolism of": "metabolism_of",
    "Has metabolites": "has_metabolites",
    "Metabolite of": "metabolite_of",
    # Drug composition
    "NDFRT has ing": "has_ingredient",
    "NDFRT ing of": "ingredient_of",
    "NDFRT has dose form": "has_dose_form",
    "NDFRT dose form of": "dose_form_of",
    "Has product comp": "has_product_component",
    "Product comp of": "product_component_of",
    "Has chem structure": "has_chemical_structure",
    "Chem structure of": "chemical_structure_of",
    # Classification
    "Has therap class": "has_therapeutic_class",
    "Therap class of": "therapeutic_class_of",
    "Has CI chem class": "has_ci_chemical_class",
    "CI chem class of": "ci_chemical_class_of",
    "Has CI MoA": "has_ci_mechanism",
    "CI MoA of": "ci_mechanism_of",
    "Has CI physio effect": "has_ci_physiologic_effect",
    "CI physiol effect by": "ci_physiologic_effect_of",
    # Equivalence
    "Prep to Chem eq": "preparation_to_chemical",
    "Chem to Prep eq": "chemical_to_preparation",
    # Clinical anatomy (UMLS)
    "Has finding site": "has_finding_site",
    "Finding site of": "finding_site_of",
    "Has asso morph": "has_associated_morphology",
    "Asso morph of": "associated_morphology_of",
    "Has causative agent": "has_causative_agent",
    "Causative agent of": "causative_agent_of",
    "Has dir morph": "has_direct_morphology",
    "Dir morph of": "direct_morphology_of",
    "Has dir subst": "has_direct_substance",
    "Dir subst of": "direct_substance_of",
    "Has dir device": "has_direct_device",
    "Dir device of": "direct_device_of",
    "Has dir proc site": "has_direct_procedure_site",
    "Dir proc site of": "direct_procedure_site_of",
    # Clinical context (UMLS)
    "Has method": "has_method",
    "Method of": "method_of",
    "Has component": "has_component",
    "Component of": "component_of",
    "Has access": "has_access",
    "Access of": "access_of",
    "Has interprets": "has_interprets",
    "Interprets of": "interprets_of",
    "Has property": "has_property",
    "Property of": "property_of",
    "Has severity": "has_severity",
    "Severity of": "severity_of",
    # Associated findings (UMLS)
    "Has asso finding": "has_associated_finding",
    "Asso finding of": "associated_finding_of",
    "Has finding context": "has_finding_context",
    "Finding context of": "finding_context_of",
    # Temporal (UMLS)
    "Has occurrence": "has_occurrence",
    "Occurrence of": "occurrence_of",
    "Occurs before": "occurs_before",
    "Occurs after": "occurs_after",
    # Pathology and causation (UMLS)
    "Has pathology": "has_pathology",
    "Pathology of": "pathology_of",
    "Has due to": "has_due_to",
    "Due to of": "due_to_of",
    "Has manifestation": "has_manifestation",
    "Manifestation of": "manifestation_of",
    "Has complication": "has_complication",
    # Procedure details (UMLS)
    "Has proc site": "has_procedure_site",
    "Proc site of": "procedure_site_of",
    "Has indir proc site": "has_indirect_procedure_site",
    "Indir proc site of": "indirect_procedure_site_of",
    "Has intent": "has_intent",
    "Intent of": "intent_of",
    "Has focus": "has_focus",
    "Focus of": "focus_of",
    "Has surgical appr": "has_surgical_approach",
    "Surgical appr of": "surgical_approach_of",
    "Has proc device": "has_procedure_device",
    "Proc device of": "procedure_device_of",
    "Has approach": "has_approach",
    "Approach of": "approach_of",
    # Lab interpretation (UMLS)
    "Has interpretation": "has_interpretation",
    "Interpretation of": "interpretation_of",
    # Device and substance usage (UMLS)
    "Using device": "using_device",
    "Device used by": "device_used_by",
    "Using subst": "using_substance",
    "Subst used by": "substance_used_by",
    "Using acc device": "using_accessory_device",
    "Acc device used by": "accessory_device_used_by",
    # Clinical course and context (UMLS)
    "Has clinical course": "has_clinical_course",
    "Clinical course of": "clinical_course_of",
    "Has temporal context": "has_temporal_context",
    "Temporal context of": "temporal_context_of",
    "Has relat context": "has_relational_context",
    "Relat context of": "relational_context_of",
    "Has proc context": "has_procedure_context",
    "Proc context of": "procedure_context_of",
    # Anatomical detail (UMLS)
    "Has laterality": "has_laterality",
    "Laterality of": "laterality_of",
    "Has direct site": "has_direct_site",
    "Direct site of": "direct_site_of",
    # Drug details (RxNorm/UMLS)
    "Has active ing": "has_active_ingredient",
    "Active ing of": "active_ingredient_of",
    "Has route": "has_route",
    "Route of": "route_of",
    "Has disposition": "has_disposition",
    "Disposition of": "disposition_of",
    "Has dose form group": "has_dose_form_group",
    "Dose form group of": "dose_form_group_of",
    "RxNorm has ing": "rxnorm_has_ingredient",
    "RxNorm ing of": "rxnorm_ingredient_of",
    "RxNorm has dose form": "rxnorm_has_dose_form",
    "RxNorm dose form of": "rxnorm_dose_form_of",
    "Has brand name": "has_brand_name",
    "Brand name of": "brand_name_of",
    "Tradename of": "tradename_of",
    "Has tradename": "has_tradename",
    "Has marketed form": "has_marketed_form",
    "Marketed form of": "marketed_form_of",
    "Drug has drug class": "drug_has_drug_class",
    "Drug class of drug": "drug_class_of_drug",
    # Associations and sequences (UMLS)
    "Has asso proc": "has_associated_procedure",
    "Asso proc of": "associated_procedure_of",
    "Follows": "follows",
    "Followed by": "followed_by",
    "Has specimen": "has_specimen",
    "Specimen of": "specimen_of",
    "Using finding method": "using_finding_method",
    "Finding method of": "finding_method_of",
    "Using finding inform": "using_finding_inform",
    "Finding inform of": "finding_inform_of",
    "Asso with finding": "associated_with_finding",
    "Finding asso with": "finding_associated_with",
    # Cross-vocabulary mappings
    "SNOMED - RxNorm eq": "snomed_rxnorm_equivalent",
    "RxNorm - SNOMED eq": "rxnorm_snomed_equivalent",
}

OMOP_REL_NAMES = list(OMOP_REL_TO_EDGE_TYPE.keys())


@dataclass
class MultiHopQuery:
    """Query parameters for multi-hop graph traversal."""

    patient_id: str
    start_concept_ids: list[int]
    edge_type_filter: list[str] | None = None
    max_hops: int = 3
    min_confidence: float = 0.3
    max_paths: int = 20


@dataclass
class PathNode:
    """A node in a traversal path."""

    node_id: str
    label: str
    node_type: str
    omop_concept_id: int | None = None


@dataclass
class PathEdge:
    """An edge in a traversal path."""

    edge_type: str
    confidence: float = 1.0
    temporality: str | None = None
    event_date: str | None = None


@dataclass
class GraphPath:
    """A traversal path through the knowledge graph."""

    nodes: list[PathNode]
    edges: list[PathEdge]
    hops: int
    path_confidence: float = 1.0
    source: str = "pg"


class GraphQueryRouter:
    """Multi-hop graph traversal using PostgreSQL as the primary engine.

    Three-phase traversal per query:
    1. kg_edges — patient-scoped clinical relationships (recursive CTE)
    2. concept_relationships → kg_nodes — vocab edges between known graph nodes
    3. concept_relationships → concepts — virtual node expansion into full
       OMOP vocabulary (anatomy, morphology, pharmacology, causative agents)

    3M+ vocabulary relationships (Athena + UMLS) across 78 relationship types.
    No Neo4j required.

    Usage:
        router = GraphQueryRouter(session)
        paths = router.execute_multi_hop(query)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute_multi_hop(self, query: MultiHopQuery) -> list[GraphPath]:
        """Execute a multi-hop traversal query using PostgreSQL."""
        if query.max_hops <= 1:
            return self._pg_single_hop(query)
        return self._pg_recursive_cte(query)

    def _pg_recursive_cte(self, query: MultiHopQuery) -> list[GraphPath]:
        """Multi-hop traversal via PostgreSQL recursive CTE.

        Three-phase approach for full vocabulary coverage:
        1. Clinical paths: traverse kg_edges from start concepts
        2. KG vocab paths: traverse concept_relationships between existing kg_nodes
        3. Extended vocab paths: traverse concept_relationships into the full
           concepts table (virtual nodes), reaching anatomy, morphology,
           causative agents, etc. that aren't materialized as kg_nodes

        Vocabulary edges live on NDFRT concept IDs while patient KG nodes
        use SNOMED standards. Phases 2-3 bridge this gap by treating all
        patient concepts as starting points for vocabulary traversal.
        """
        safe_max_hops = min(int(query.max_hops), MAX_HOPS_LIMIT)
        safe_max_paths = min(int(query.max_paths), MAX_PATHS_LIMIT)

        if query.edge_type_filter:
            omop_rels = [
                rel_name
                for rel_name, edge_type in OMOP_REL_TO_EDGE_TYPE.items()
                if edge_type in query.edge_type_filter
            ]
        else:
            omop_rels = OMOP_REL_NAMES

        sql = text(f"""
        WITH RECURSIVE
        -- All shared concept nodes connected to this patient's graph
        patient_concept_ids AS (
            SELECT DISTINCT n.id, n.omop_concept_id
            FROM kg_edges e
            JOIN kg_nodes n ON (n.id = e.source_node_id OR n.id = e.target_node_id)
            WHERE e.patient_id = :patient_id
              AND n.patient_id IS NULL
              AND n.deleted_at IS NULL
              AND n.omop_concept_id IS NOT NULL
        ),

        -- Clinical edges (patient-scoped kg_edges, bidirectional)
        clinical_edges AS (
            SELECT e.source_node_id AS from_id, e.target_node_id AS to_id,
                   e.edge_type::text AS edge_label,
                   COALESCE(e.temporal_confidence, 1.0)::float AS confidence
            FROM kg_edges e
            WHERE e.patient_id = :patient_id
            UNION ALL
            SELECT e.target_node_id, e.source_node_id, e.edge_type::text,
                   COALESCE(e.temporal_confidence, 1.0)::float
            FROM kg_edges e
            WHERE e.patient_id = :patient_id
        ),

        -- Phase 1: Clinical traversal from start concepts via kg_edges
        clinical_traversal AS (
            SELECT
                n.id AS node_id, n.omop_concept_id, n.label,
                n.node_type::text AS node_type, 0 AS depth,
                ARRAY[n.id::text]::text[] AS visited_ids,
                ARRAY[n.label::text]::text[] AS path_labels,
                ARRAY[n.node_type::text]::text[] AS path_types,
                ARRAY[n.omop_concept_id]::bigint[] AS path_concepts,
                ARRAY[]::text[] AS edge_types,
                ARRAY[]::float[] AS edge_confidences,
                1.0::float AS path_confidence
            FROM kg_nodes n
            WHERE n.omop_concept_id = ANY(:start_concept_ids)
              AND n.patient_id IS NULL AND n.deleted_at IS NULL
              AND n.id IN (SELECT id FROM patient_concept_ids)

            UNION ALL

            SELECT
                n2.id, n2.omop_concept_id, n2.label, n2.node_type::text,
                t.depth + 1, t.visited_ids || n2.id::text,
                t.path_labels || n2.label, t.path_types || n2.node_type::text,
                t.path_concepts || n2.omop_concept_id,
                t.edge_types || ce.edge_label,
                t.edge_confidences || ce.confidence,
                t.path_confidence * ce.confidence
            FROM clinical_traversal t
            JOIN clinical_edges ce ON ce.from_id = t.node_id
            JOIN kg_nodes n2 ON n2.id = ce.to_id AND n2.deleted_at IS NULL
            WHERE t.depth < {safe_max_hops}
              AND NOT (n2.id::text = ANY(t.visited_ids))
        ),

        -- Phase 2: Vocabulary 1-hop from patient concepts via concept_relationships
        -- Reaches into the full concepts table (virtual nodes) for anatomy,
        -- morphology, causative agents, pharmacology targets, etc.
        vocab_hop1 AS (
            SELECT
                pc.omop_concept_id AS start_concept_id,
                n.label AS start_label,
                n.node_type::text AS start_type,
                cr.concept_id_2 AS end_concept_id,
                c2.concept_name AS end_label,
                CASE c2.domain_id
                    WHEN 'Condition' THEN 'condition'
                    WHEN 'Drug' THEN 'drug'
                    WHEN 'Measurement' THEN 'measurement'
                    WHEN 'Procedure' THEN 'procedure'
                    WHEN 'Observation' THEN 'observation'
                    WHEN 'Spec Anatomic Site' THEN 'anatomy'
                    WHEN 'Meas Value' THEN 'measurement'
                    WHEN 'Device' THEN 'device'
                    ELSE LOWER(COALESCE(c2.domain_id, 'concept'))
                END AS end_type,
                cr.relationship_id AS edge_label
            FROM patient_concept_ids pc
            JOIN kg_nodes n ON n.id = pc.id
            JOIN concept_relationships cr
                ON cr.concept_id_1 = pc.omop_concept_id
                AND cr.relationship_id = ANY(:omop_rels)
                AND cr.invalid_reason IS NULL
            JOIN concepts c2 ON c2.concept_id = cr.concept_id_2
            WHERE cr.concept_id_2 <> pc.omop_concept_id
        ),

        -- Phase 3: Vocabulary 2-hop (hop1 targets -> their concept_relationships)
        -- Only computed when max_hops >= 2, otherwise empty
        vocab_hop2 AS (
            SELECT
                h1.start_concept_id,
                h1.start_label,
                h1.start_type,
                h1.end_concept_id AS mid_concept_id,
                h1.end_label AS mid_label,
                h1.end_type AS mid_type,
                h1.edge_label AS edge1,
                cr2.concept_id_2 AS end_concept_id,
                c3.concept_name AS end_label,
                CASE c3.domain_id
                    WHEN 'Condition' THEN 'condition'
                    WHEN 'Drug' THEN 'drug'
                    WHEN 'Measurement' THEN 'measurement'
                    WHEN 'Procedure' THEN 'procedure'
                    WHEN 'Observation' THEN 'observation'
                    WHEN 'Spec Anatomic Site' THEN 'anatomy'
                    WHEN 'Meas Value' THEN 'measurement'
                    WHEN 'Device' THEN 'device'
                    ELSE LOWER(COALESCE(c3.domain_id, 'concept'))
                END AS end_type,
                cr2.relationship_id AS edge2
            FROM vocab_hop1 h1
            JOIN concept_relationships cr2
                ON cr2.concept_id_1 = h1.end_concept_id
                AND cr2.relationship_id = ANY(:omop_rels)
                AND cr2.invalid_reason IS NULL
            JOIN concepts c3 ON c3.concept_id = cr2.concept_id_2
            WHERE cr2.concept_id_2 <> h1.start_concept_id
              AND cr2.concept_id_2 <> h1.end_concept_id
              AND {safe_max_hops} >= 2
        ),

        -- Combine all path sources
        combined AS (
            -- Clinical paths (kg_edges traversal)
            SELECT visited_ids AS path_ids, path_labels, path_types, path_concepts,
                   edge_types, edge_confidences, depth, path_confidence
            FROM clinical_traversal
            WHERE depth > 0

            UNION ALL

            -- Vocab 1-hop paths
            SELECT
                ARRAY[start_concept_id::text, end_concept_id::text],
                ARRAY[start_label, end_label],
                ARRAY[start_type, end_type],
                ARRAY[start_concept_id, end_concept_id],
                ARRAY[edge_label],
                ARRAY[1.0::float],
                1,
                1.0::float
            FROM vocab_hop1

            UNION ALL

            -- Vocab 2-hop paths
            SELECT
                ARRAY[start_concept_id::text, mid_concept_id::text, end_concept_id::text],
                ARRAY[start_label, mid_label, end_label],
                ARRAY[start_type, mid_type, end_type],
                ARRAY[start_concept_id, mid_concept_id, end_concept_id],
                ARRAY[edge1, edge2],
                ARRAY[1.0::float, 1.0::float],
                2,
                1.0::float
            FROM vocab_hop2
        )
        SELECT path_ids, path_labels, path_types, path_concepts,
               edge_types, edge_confidences, depth, path_confidence
        FROM combined
        WHERE path_confidence >= :min_confidence
        ORDER BY path_confidence DESC, depth ASC
        LIMIT {safe_max_paths}
        """)

        try:
            self._session.execute(text("SET LOCAL statement_timeout = '10s'"))
        except Exception:
            pass  # SQLite or non-PG backends don't support SET LOCAL

        rows = self._session.execute(sql, {
            "patient_id": query.patient_id,
            "start_concept_ids": query.start_concept_ids,
            "min_confidence": query.min_confidence,
            "omop_rels": omop_rels,
        }).fetchall()

        paths: list[GraphPath] = []
        for row in rows:
            visited_ids = row[0]
            path_labels = row[1]
            path_types = row[2]
            path_concepts = row[3]
            edge_types = row[4]
            edge_confs = row[5]
            depth = row[6]
            path_conf = row[7]

            nodes = [
                PathNode(
                    node_id=visited_ids[i],
                    label=path_labels[i],
                    node_type=path_types[i],
                    omop_concept_id=path_concepts[i],
                )
                for i in range(len(visited_ids))
            ]
            edges = [
                PathEdge(
                    edge_type=OMOP_REL_TO_EDGE_TYPE.get(edge_types[i], edge_types[i]),
                    confidence=edge_confs[i] if i < len(edge_confs) else 1.0,
                )
                for i in range(len(edge_types))
            ]

            paths.append(GraphPath(
                nodes=nodes,
                edges=edges,
                hops=depth,
                path_confidence=path_conf,
                source="pg_cte",
            ))

        return paths

    def _pg_single_hop(self, query: MultiHopQuery) -> list[GraphPath]:
        """Single-hop traversal (simple JOIN, no CTE needed)."""
        start_stmt = (
            select(KGNode)
            .join(
                KGEdge,
                or_(
                    KGEdge.target_node_id == KGNode.id,
                    KGEdge.source_node_id == KGNode.id,
                ),
            )
            .where(KGEdge.patient_id == query.patient_id)
            .where(KGNode.omop_concept_id.in_(query.start_concept_ids))
            .distinct()
        )
        result = self._session.execute(start_stmt)
        start_nodes = list(result.scalars().all())

        if not start_nodes:
            return []

        all_paths: list[GraphPath] = []
        visited: set[str] = set()

        for start_node in start_nodes[:5]:
            edge_stmt = (
                select(KGEdge)
                .where(KGEdge.patient_id == query.patient_id)
                .where(
                    or_(
                        KGEdge.source_node_id == str(start_node.id),
                        KGEdge.target_node_id == str(start_node.id),
                    )
                )
            )
            if query.edge_type_filter:
                edge_stmt = edge_stmt.where(KGEdge.edge_type.in_(query.edge_type_filter))

            edges = list(self._session.execute(edge_stmt).scalars().all())

            neighbor_ids = set()
            for edge in edges:
                if edge.source_node_id != str(start_node.id):
                    neighbor_ids.add(edge.source_node_id)
                if edge.target_node_id != str(start_node.id):
                    neighbor_ids.add(edge.target_node_id)

            neighbor_map: dict[str, KGNode] = {}
            if neighbor_ids:
                neighbor_stmt = select(KGNode).where(KGNode.id.in_(list(neighbor_ids)))
                neighbor_map = {
                    n.id: n
                    for n in self._session.execute(neighbor_stmt).scalars().all()
                }

            start_path_node = PathNode(
                node_id=str(start_node.id),
                label=start_node.label,
                node_type=start_node.node_type.value,
                omop_concept_id=start_node.omop_concept_id,
            )

            for edge in edges:
                if edge.source_node_id == str(start_node.id):
                    neighbor = neighbor_map.get(edge.target_node_id)
                else:
                    neighbor = neighbor_map.get(edge.source_node_id)

                if neighbor is None or neighbor.id in visited:
                    continue

                edge_conf = edge.temporal_confidence or 1.0
                if edge_conf < query.min_confidence:
                    continue

                all_paths.append(GraphPath(
                    nodes=[
                        start_path_node,
                        PathNode(
                            node_id=str(neighbor.id),
                            label=neighbor.label,
                            node_type=neighbor.node_type.value,
                            omop_concept_id=neighbor.omop_concept_id,
                        ),
                    ],
                    edges=[
                        PathEdge(
                            edge_type=edge.edge_type.value,
                            confidence=edge_conf,
                            temporality=edge.temporality,
                            event_date=edge.event_date.isoformat() if edge.event_date else None,
                        ),
                    ],
                    hops=1,
                    path_confidence=edge_conf,
                    source="pg",
                ))
                visited.add(neighbor.id)

            if len(all_paths) >= query.max_paths:
                break

        return all_paths[:query.max_paths]


# Backward-compatible alias
Neo4jQueryRouter = GraphQueryRouter
