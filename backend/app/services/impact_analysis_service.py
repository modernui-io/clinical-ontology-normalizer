"""Impact analysis service for vocabulary version changes.

Analyzes the downstream effects of concept retirements, deprecations,
and version updates on KG nodes, alert rules, and policy sections.
"""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocabulary import Concept, ConceptStatus

logger = logging.getLogger(__name__)


async def analyze_concept_retirement(
    session: AsyncSession,
    concept_id: int,
) -> dict[str, Any]:
    """Analyze the impact of retiring a specific concept.

    Returns affected KG nodes, alert rules, policy sections, and risk level.
    """
    # Look up the concept
    result = await session.execute(
        select(Concept).where(Concept.concept_id == concept_id)
    )
    concept = result.scalar_one_or_none()
    if not concept:
        return {"error": "Concept not found"}

    # Find affected KG nodes
    affected_kg_nodes = []
    try:
        from app.models.knowledge_graph import KGNode
        kg_result = await session.execute(
            select(KGNode).where(KGNode.omop_concept_id == concept_id)
        )
        for node in kg_result.scalars().all():
            affected_kg_nodes.append({
                "node_id": node.id,
                "patient_id": node.patient_id,
                "node_type": node.node_type,
                "label": node.label,
            })
    except Exception:
        logger.debug("Could not query KG nodes for impact analysis")

    # Find affected alert rules (via PolicyAlertRule → PolicySection)
    affected_rules = []
    try:
        from app.models.policy import PolicyAlertRule, PolicySection
        # Find policy sections with keywords matching the concept name
        section_result = await session.execute(
            select(PolicySection).where(
                PolicySection.keywords.any(concept.concept_name.lower())
            )
        )
        for section in section_result.scalars().all():
            rule_result = await session.execute(
                select(PolicyAlertRule).where(
                    PolicyAlertRule.policy_section_id == section.id
                )
            )
            for rule in rule_result.scalars().all():
                affected_rules.append({
                    "alert_rule_id": rule.alert_rule_id,
                    "section_id": section.id,
                    "section_title": section.title,
                })
    except Exception:
        logger.debug("Could not query policy rules for impact analysis")

    # Determine risk level
    total_affected = len(affected_kg_nodes) + len(affected_rules)
    unique_patients = len(set(n["patient_id"] for n in affected_kg_nodes))

    if total_affected == 0:
        risk_level = "none"
    elif unique_patients > 10 or len(affected_rules) > 2:
        risk_level = "high"
    elif unique_patients > 3 or len(affected_rules) > 0:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Find suggested replacement (look for "Maps to" or similar relationships)
    suggested_replacement = None
    try:
        from app.models.vocabulary import ConceptRelationship
        rel_result = await session.execute(
            select(ConceptRelationship).where(
                ConceptRelationship.concept_id_1 == concept_id,
                ConceptRelationship.relationship_id == "Maps to",
                ConceptRelationship.invalid_reason.is_(None),
            )
        )
        rel = rel_result.scalar_one_or_none()
        if rel:
            repl_result = await session.execute(
                select(Concept).where(Concept.concept_id == rel.concept_id_2)
            )
            repl_concept = repl_result.scalar_one_or_none()
            if repl_concept:
                suggested_replacement = {
                    "concept_id": repl_concept.concept_id,
                    "concept_name": repl_concept.concept_name,
                    "vocabulary_id": repl_concept.vocabulary_id,
                }
    except Exception:
        logger.debug("Could not find replacement concept")

    return {
        "concept_id": concept_id,
        "concept_name": concept.concept_name,
        "vocabulary_id": concept.vocabulary_id,
        "current_status": concept.status.value if concept.status else "active",
        "affected_kg_nodes": affected_kg_nodes,
        "affected_patients": unique_patients,
        "affected_rules": affected_rules,
        "risk_level": risk_level,
        "suggested_replacement": suggested_replacement,
        "total_affected_items": total_affected,
    }


async def analyze_version_update(
    session: AsyncSession,
    vocabulary_id: str,
    new_concepts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze the aggregate impact of a version update.

    Examines all concepts in the update and summarizes the impact.
    """
    total_new = 0
    total_updated = 0
    total_deprecated = 0
    total_retired = 0
    high_risk_retirements = []

    for concept_data in new_concepts:
        cid = concept_data.get("concept_id")
        status = concept_data.get("status", "active")

        result = await session.execute(
            select(Concept).where(Concept.concept_id == cid)
        )
        existing = result.scalar_one_or_none()

        if not existing:
            total_new += 1
        elif status in ("deprecated", "retired"):
            if status == "retired":
                total_retired += 1
            else:
                total_deprecated += 1

            # Quick impact check
            try:
                from app.models.knowledge_graph import KGNode
                kg_count_result = await session.execute(
                    select(func.count(KGNode.id)).where(KGNode.omop_concept_id == cid)
                )
                kg_count = kg_count_result.scalar() or 0
                if kg_count > 0:
                    high_risk_retirements.append({
                        "concept_id": cid,
                        "concept_name": existing.concept_name,
                        "affected_kg_nodes": kg_count,
                    })
            except Exception:
                pass
        else:
            total_updated += 1

    overall_risk = "high" if len(high_risk_retirements) > 3 else (
        "medium" if high_risk_retirements else "low"
    )

    return {
        "vocabulary_id": vocabulary_id,
        "total_concepts_in_update": len(new_concepts),
        "new_concepts": total_new,
        "updated_concepts": total_updated,
        "deprecated_concepts": total_deprecated,
        "retired_concepts": total_retired,
        "high_risk_retirements": high_risk_retirements,
        "overall_risk": overall_risk,
    }


async def generate_impact_report(
    session: AsyncSession,
    vocabulary_id: str,
) -> dict[str, Any]:
    """Generate an impact report for a vocabulary's current state.

    Summarizes concepts by status and identifies items needing attention.
    """
    # Count by status
    status_result = await session.execute(
        select(
            Concept.status,
            func.count(Concept.id),
        )
        .where(Concept.vocabulary_id == vocabulary_id)
        .group_by(Concept.status)
    )
    status_counts = {}
    for row in status_result.all():
        status_val = row[0].value if hasattr(row[0], "value") else str(row[0])
        status_counts[status_val] = row[1]

    # Find recently changed concepts (those with status_changed_at)
    recent_changes = []
    changed_result = await session.execute(
        select(Concept)
        .where(
            Concept.vocabulary_id == vocabulary_id,
            Concept.status_changed_at.is_not(None),
        )
        .order_by(Concept.status_changed_at.desc())
        .limit(20)
    )
    for c in changed_result.scalars().all():
        recent_changes.append({
            "concept_id": c.concept_id,
            "concept_name": c.concept_name,
            "status": c.status.value if c.status else "active",
            "changed_at": c.status_changed_at.isoformat() if c.status_changed_at else None,
        })

    # Find retired/deprecated concepts still referenced in KG
    stale_references = []
    try:
        from app.models.knowledge_graph import KGNode
        stale_result = await session.execute(
            select(Concept.concept_id, Concept.concept_name, func.count(KGNode.id))
            .join(KGNode, KGNode.omop_concept_id == Concept.concept_id)
            .where(
                Concept.vocabulary_id == vocabulary_id,
                Concept.status.in_([ConceptStatus.retired, ConceptStatus.deprecated]),
            )
            .group_by(Concept.concept_id, Concept.concept_name)
        )
        for row in stale_result.all():
            stale_references.append({
                "concept_id": row[0],
                "concept_name": row[1],
                "kg_node_count": row[2],
            })
    except Exception:
        logger.debug("Could not check for stale KG references")

    return {
        "vocabulary_id": vocabulary_id,
        "status_breakdown": status_counts,
        "recent_changes": recent_changes,
        "stale_references": stale_references,
        "needs_attention": len(stale_references) > 0,
    }
