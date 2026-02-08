"""Agent tool schemas (Anthropic ToolParam format) and async handler functions.

Each tool handler queries existing tables (ClinicalFact, KGNode, KGEdge,
ClinicalValue) and returns a plain dict that gets serialised as a
tool_result for Claude.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.models.clinical_value import ClinicalValue
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain
from app.schemas.knowledge_graph import EdgeType, NodeType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas in Anthropic ToolParam format
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_patient_summary",
        "description": (
            "Get a high-level summary for a patient: demographics, fact counts "
            "by domain, top conditions, and top medications."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "The patient identifier.",
                },
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "query_patient_conditions",
        "description": (
            "List clinical conditions (diagnoses) for a patient from the "
            "ClinicalFact table.  Supports assertion and temporality filters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "Patient identifier."},
                "assertion": {
                    "type": "string",
                    "enum": ["present", "absent", "possible", "all"],
                    "description": "Filter by assertion status.  Default: all.",
                },
                "temporality": {
                    "type": "string",
                    "enum": ["current", "past", "all"],
                    "description": "Filter by temporality.  Default: all.",
                },
                "limit": {"type": "integer", "description": "Max results (default 50)."},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "query_patient_medications",
        "description": "List medications for a patient from ClinicalFact (domain=drug).",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "assertion": {
                    "type": "string",
                    "enum": ["present", "absent", "possible", "all"],
                },
                "temporality": {
                    "type": "string",
                    "enum": ["current", "past", "all"],
                },
                "limit": {"type": "integer"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "query_patient_labs",
        "description": (
            "List lab/measurement results for a patient.  Joins ClinicalFact "
            "(domain=measurement) with ClinicalValue for numeric data. "
            "Supports name_filter for text search (e.g. 'HbA1c')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "name_filter": {
                    "type": "string",
                    "description": "Case-insensitive text match on lab name.",
                },
                "assertion": {
                    "type": "string",
                    "enum": ["present", "absent", "possible", "all"],
                },
                "limit": {"type": "integer"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "query_patient_procedures",
        "description": "List procedures for a patient from ClinicalFact (domain=procedure).",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "assertion": {
                    "type": "string",
                    "enum": ["present", "absent", "possible", "all"],
                },
                "limit": {"type": "integer"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "query_patient_encounters",
        "description": "List encounters/visits for a patient from ClinicalFact (domain=visit).",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "search_clinical_concepts",
        "description": (
            "Search across all patients' clinical facts by concept name "
            "(case-insensitive text match).  Useful for finding patients "
            "with a specific condition or medication."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search in concept names.",
                },
                "domain": {
                    "type": "string",
                    "enum": ["condition", "drug", "measurement", "procedure", "visit", "all"],
                    "description": "Restrict search to a domain.  Default: all.",
                },
                "patient_id": {
                    "type": "string",
                    "description": "Optionally restrict to a single patient.",
                },
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_trial_eligibility",
        "description": (
            "Check whether a patient meets the eligibility criteria for a "
            "clinical trial.  Returns per-criterion pass/fail details and "
            "an overall eligibility score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "Patient identifier."},
                "trial_id": {"type": "string", "description": "Trial identifier."},
            },
            "required": ["patient_id", "trial_id"],
        },
    },
    {
        "name": "query_knowledge_graph",
        "description": (
            "Query the knowledge graph for a patient.  Returns nodes and "
            "edges, optionally filtered by node_type and/or edge_type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "node_type": {
                    "type": "string",
                    "enum": [
                        "patient", "condition", "drug", "measurement",
                        "procedure", "observation", "clinical_note",
                    ],
                    "description": "Filter nodes by type.",
                },
                "edge_type": {
                    "type": "string",
                    "description": "Filter edges by type (e.g. has_condition, takes_drug).",
                },
                "limit": {"type": "integer", "description": "Max nodes to return (default 50)."},
            },
            "required": ["patient_id"],
        },
    },
]

# Build a name -> schema lookup for the /tools endpoint
TOOL_SCHEMAS_BY_NAME: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOL_SCHEMAS}

# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


def _fact_to_dict(fact: ClinicalFact) -> dict[str, Any]:
    """Serialise a ClinicalFact row to a plain dict for tool results."""
    return {
        "id": str(fact.id),
        "concept_name": fact.concept_name,
        "omop_concept_id": fact.omop_concept_id,
        "domain": fact.domain.value if hasattr(fact.domain, "value") else str(fact.domain),
        "assertion": fact.assertion.value if hasattr(fact.assertion, "value") else str(fact.assertion),
        "temporality": fact.temporality.value if hasattr(fact.temporality, "value") else str(fact.temporality),
        "confidence": fact.confidence,
        "value": fact.value,
        "unit": fact.unit,
        "start_date": fact.start_date.isoformat() if fact.start_date else None,
        "end_date": fact.end_date.isoformat() if fact.end_date else None,
    }


async def _query_facts(
    session: AsyncSession,
    patient_id: str,
    domain: Domain,
    *,
    assertion: str | None = None,
    temporality: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Shared helper to query ClinicalFact by patient + domain."""
    stmt = (
        select(ClinicalFact)
        .where(ClinicalFact.patient_id == patient_id)
        .where(ClinicalFact.domain == domain)
        .where(ClinicalFact.deleted_at.is_(None))
    )
    if assertion and assertion != "all":
        stmt = stmt.where(ClinicalFact.assertion == assertion)
    if temporality and temporality != "all":
        stmt = stmt.where(ClinicalFact.temporality == temporality)
    stmt = stmt.order_by(ClinicalFact.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    return [_fact_to_dict(f) for f in result.scalars().all()]


# ---- 1. get_patient_summary ----

async def handle_get_patient_summary(params: dict, session: AsyncSession) -> dict:
    pid = params["patient_id"]

    # Patient KGNode
    node_q = (
        select(KGNode)
        .where(KGNode.patient_id == pid)
        .where(KGNode.node_type == NodeType.PATIENT.value)
        .where(KGNode.deleted_at.is_(None))
        .limit(1)
    )
    patient_node = (await session.execute(node_q)).scalars().first()

    # Fact counts by domain
    count_q = (
        select(ClinicalFact.domain, func.count(ClinicalFact.id))
        .where(ClinicalFact.patient_id == pid)
        .where(ClinicalFact.deleted_at.is_(None))
        .group_by(ClinicalFact.domain)
    )
    counts = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
        for row in (await session.execute(count_q)).all()
    }

    # Top 5 conditions
    cond_q = (
        select(KGNode.label)
        .where(KGNode.patient_id == pid)
        .where(KGNode.node_type == NodeType.CONDITION.value)
        .where(KGNode.deleted_at.is_(None))
        .limit(5)
    )
    conditions = [r[0] for r in (await session.execute(cond_q)).all()]

    # Top 5 medications
    drug_q = (
        select(KGNode.label)
        .where(KGNode.patient_id == pid)
        .where(KGNode.node_type == NodeType.DRUG.value)
        .where(KGNode.deleted_at.is_(None))
        .limit(5)
    )
    medications = [r[0] for r in (await session.execute(drug_q)).all()]

    props = (patient_node.properties or {}) if patient_node else {}
    return {
        "patient_id": pid,
        "name": patient_node.label if patient_node else pid,
        "gender": props.get("gender", ""),
        "birth_date": props.get("birth_date", ""),
        "mrn": props.get("mrn", props.get("fhir_id", "")),
        "fact_counts_by_domain": counts,
        "total_facts": sum(counts.values()),
        "top_conditions": conditions,
        "top_medications": medications,
    }


# ---- 2. query_patient_conditions ----

async def handle_query_patient_conditions(params: dict, session: AsyncSession) -> dict:
    facts = await _query_facts(
        session,
        params["patient_id"],
        Domain.CONDITION,
        assertion=params.get("assertion"),
        temporality=params.get("temporality"),
        limit=params.get("limit", 50),
    )
    return {"patient_id": params["patient_id"], "domain": "condition", "count": len(facts), "facts": facts}


# ---- 3. query_patient_medications ----

async def handle_query_patient_medications(params: dict, session: AsyncSession) -> dict:
    facts = await _query_facts(
        session,
        params["patient_id"],
        Domain.DRUG,
        assertion=params.get("assertion"),
        temporality=params.get("temporality"),
        limit=params.get("limit", 50),
    )
    return {"patient_id": params["patient_id"], "domain": "drug", "count": len(facts), "facts": facts}


# ---- 4. query_patient_labs ----

async def handle_query_patient_labs(params: dict, session: AsyncSession) -> dict:
    pid = params["patient_id"]
    name_filter = params.get("name_filter")
    assertion = params.get("assertion")
    limit = params.get("limit", 50)

    # Query ClinicalFact for measurements
    stmt = (
        select(ClinicalFact)
        .where(ClinicalFact.patient_id == pid)
        .where(ClinicalFact.domain == Domain.MEASUREMENT)
        .where(ClinicalFact.deleted_at.is_(None))
    )
    if assertion and assertion != "all":
        stmt = stmt.where(ClinicalFact.assertion == assertion)
    if name_filter:
        stmt = stmt.where(ClinicalFact.concept_name.ilike(f"%{name_filter}%"))
    stmt = stmt.order_by(ClinicalFact.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    facts = result.scalars().all()

    # Also fetch ClinicalValues for richer numeric data
    val_stmt = (
        select(ClinicalValue)
        .where(ClinicalValue.patient_id == pid)
    )
    if name_filter:
        val_stmt = val_stmt.where(ClinicalValue.name.ilike(f"%{name_filter}%"))
    val_stmt = val_stmt.order_by(ClinicalValue.created_at.desc()).limit(limit)

    val_result = await session.execute(val_stmt)
    values = val_result.scalars().all()

    fact_dicts = [_fact_to_dict(f) for f in facts]
    value_dicts = [
        {
            "name": v.name,
            "value": v.value,
            "value_secondary": v.value_secondary,
            "unit": v.unit,
            "interpretation": v.interpretation,
            "reference_low": v.reference_low,
            "reference_high": v.reference_high,
            "value_type": v.value_type.value if hasattr(v.value_type, "value") else str(v.value_type),
        }
        for v in values
    ]

    return {
        "patient_id": pid,
        "domain": "measurement",
        "fact_count": len(fact_dicts),
        "facts": fact_dicts,
        "clinical_values_count": len(value_dicts),
        "clinical_values": value_dicts,
    }


# ---- 5. query_patient_procedures ----

async def handle_query_patient_procedures(params: dict, session: AsyncSession) -> dict:
    facts = await _query_facts(
        session,
        params["patient_id"],
        Domain.PROCEDURE,
        assertion=params.get("assertion"),
        limit=params.get("limit", 50),
    )
    return {"patient_id": params["patient_id"], "domain": "procedure", "count": len(facts), "facts": facts}


# ---- 6. query_patient_encounters ----

async def handle_query_patient_encounters(params: dict, session: AsyncSession) -> dict:
    facts = await _query_facts(
        session,
        params["patient_id"],
        Domain.VISIT,
        limit=params.get("limit", 50),
    )
    return {"patient_id": params["patient_id"], "domain": "visit", "count": len(facts), "facts": facts}


# ---- 7. search_clinical_concepts ----

async def handle_search_clinical_concepts(params: dict, session: AsyncSession) -> dict:
    query = params["query"]
    domain = params.get("domain")
    patient_id = params.get("patient_id")
    limit = params.get("limit", 30)

    stmt = (
        select(ClinicalFact)
        .where(ClinicalFact.concept_name.ilike(f"%{query}%"))
        .where(ClinicalFact.deleted_at.is_(None))
    )
    if domain and domain != "all":
        stmt = stmt.where(ClinicalFact.domain == domain)
    if patient_id:
        stmt = stmt.where(ClinicalFact.patient_id == patient_id)
    stmt = stmt.order_by(ClinicalFact.confidence.desc()).limit(limit)

    result = await session.execute(stmt)
    facts = result.scalars().all()

    return {
        "query": query,
        "count": len(facts),
        "results": [
            {**_fact_to_dict(f), "patient_id": f.patient_id}
            for f in facts
        ],
    }


# ---- 8. check_trial_eligibility ----

async def handle_check_trial_eligibility(params: dict, session: AsyncSession) -> dict:
    from app.services.trial_eligibility_service import get_trial_service

    svc = get_trial_service()
    result = await svc.check_patient_eligibility(
        trial_id=params["trial_id"],
        patient_id=params["patient_id"],
        session=session,
    )
    if result is None:
        return {"error": f"Trial '{params['trial_id']}' not found or patient has no data."}

    # Serialise the Pydantic model (or dataclass) to dict
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    elif hasattr(result, "dict"):
        return result.dict()
    else:
        return {"status": str(result)}


# ---- 9. query_knowledge_graph ----

async def handle_query_knowledge_graph(params: dict, session: AsyncSession) -> dict:
    pid = params["patient_id"]
    node_type = params.get("node_type")
    edge_type = params.get("edge_type")
    limit = params.get("limit", 50)

    # Nodes
    node_stmt = (
        select(KGNode)
        .where(KGNode.patient_id == pid)
        .where(KGNode.deleted_at.is_(None))
    )
    if node_type:
        node_stmt = node_stmt.where(KGNode.node_type == node_type)
    node_stmt = node_stmt.limit(limit)

    nodes = (await session.execute(node_stmt)).scalars().all()

    node_ids = {n.id for n in nodes}

    # Edges
    edge_stmt = (
        select(KGEdge)
        .where(KGEdge.patient_id == pid)
        .where(KGEdge.deleted_at.is_(None))
    )
    if edge_type:
        edge_stmt = edge_stmt.where(KGEdge.edge_type == edge_type)
    edge_stmt = edge_stmt.limit(limit * 2)

    edges = (await session.execute(edge_stmt)).scalars().all()

    return {
        "patient_id": pid,
        "node_count": len(nodes),
        "nodes": [
            {
                "id": str(n.id),
                "node_type": n.node_type.value if hasattr(n.node_type, "value") else str(n.node_type),
                "label": n.label,
                "omop_concept_id": n.omop_concept_id,
                "properties": n.properties,
            }
            for n in nodes
        ],
        "edge_count": len(edges),
        "edges": [
            {
                "id": str(e.id),
                "edge_type": e.edge_type.value if hasattr(e.edge_type, "value") else str(e.edge_type),
                "source_node_id": str(e.source_node_id),
                "target_node_id": str(e.target_node_id),
                "properties": e.properties,
            }
            for e in edges
        ],
    }


# ---------------------------------------------------------------------------
# Dispatch map: tool_name -> handler function
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict[str, Any] = {
    "get_patient_summary": handle_get_patient_summary,
    "query_patient_conditions": handle_query_patient_conditions,
    "query_patient_medications": handle_query_patient_medications,
    "query_patient_labs": handle_query_patient_labs,
    "query_patient_procedures": handle_query_patient_procedures,
    "query_patient_encounters": handle_query_patient_encounters,
    "search_clinical_concepts": handle_search_clinical_concepts,
    "check_trial_eligibility": handle_check_trial_eligibility,
    "query_knowledge_graph": handle_query_knowledge_graph,
}
