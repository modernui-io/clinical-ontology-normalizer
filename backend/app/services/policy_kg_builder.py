"""Policy Knowledge Graph Builder Service.

Extracts structured clinical decision rules from policy documents
and builds the Policy Knowledge Graph.

Pipeline:
1. Parse policy sections from existing PolicySection records
2. Use LLM to extract IF-THEN-ELSE rule structures
3. Create PolicyKGNode and PolicyKGEdge entries
4. Create PolicyRule entries with structured data
5. Compute embeddings for semantic search

Based on research from Decision Knowledge Graphs for Clinical Practice Guidelines.
"""

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy, PolicySection
from app.models.policy_kg import (
    EvidenceGrade,
    PolicyEdgeType,
    PolicyKGEdge,
    PolicyKGNode,
    PolicyNodeType,
    PolicyRule,
    RecommendationStrength,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedCondition:
    """A condition extracted from a policy rule."""

    text: str
    condition_type: str  # "patient_has", "lab_value", "age", "medication", etc.
    value: str | None = None
    operator: str | None = None  # ">", "<", ">=", "<=", "=", "between"
    threshold: float | None = None
    threshold_unit: str | None = None
    omop_concept_ids: list[int] = field(default_factory=list)


@dataclass
class ExtractedAction:
    """An action extracted from a policy rule."""

    text: str
    action_type: str  # "prescribe", "order_test", "refer", "monitor", "educate"
    target: str | None = None  # medication name, test name, etc.
    frequency: str | None = None
    dosage: str | None = None
    omop_concept_ids: list[int] = field(default_factory=list)


@dataclass
class ExtractedRule:
    """A structured rule extracted from policy text."""

    rule_id: str
    name: str
    description: str
    source_text: str
    conditions: list[ExtractedCondition]
    actions: list[ExtractedAction]
    exceptions: list[ExtractedCondition]
    evidence_grade: str | None = None
    recommendation_strength: str | None = None
    applies_to_conditions: list[str] = field(default_factory=list)
    applies_to_medications: list[str] = field(default_factory=list)
    applies_to_measurements: list[str] = field(default_factory=list)
    extraction_confidence: float = 0.0


# LLM prompt for rule extraction
RULE_EXTRACTION_PROMPT = """You are a clinical policy analyst. Extract structured decision rules from the following policy section.

For each rule you find, identify:
1. IF conditions (what triggers the rule)
2. THEN actions (what should be done)
3. UNLESS exceptions (contraindications or special cases)
4. Evidence grade if mentioned (A, B, C, D, or Expert)
5. Recommendation strength if mentioned (Strong, Moderate, Weak)

Return a JSON array of rules. Each rule should have:
{
  "name": "Brief rule name",
  "description": "Full description of the rule",
  "conditions": [
    {
      "text": "Original condition text",
      "type": "patient_has|lab_value|age|medication|procedure|timeframe|other",
      "value": "specific value if applicable",
      "operator": ">|<|>=|<=|=|between (if numeric)",
      "threshold": numeric_value_if_applicable,
      "unit": "unit if applicable"
    }
  ],
  "actions": [
    {
      "text": "Original action text",
      "type": "prescribe|order_test|refer|monitor|educate|document|other",
      "target": "medication/test/specialist name",
      "frequency": "how often",
      "dosage": "if medication"
    }
  ],
  "exceptions": [
    {
      "text": "Exception condition text",
      "type": "same as conditions"
    }
  ],
  "evidence_grade": "A|B|C|D|Expert or null",
  "recommendation_strength": "Strong|Moderate|Weak or null",
  "applies_to_conditions": ["condition names this applies to"],
  "applies_to_medications": ["medication names referenced"],
  "applies_to_measurements": ["lab/vital names referenced"],
  "confidence": 0.0-1.0
}

If no clear rules can be extracted, return an empty array [].

Policy section:
---
{section_text}
---

Extract rules as JSON:"""


class PolicyKGBuilder:
    """Service for building the Policy Knowledge Graph from policy documents."""

    def __init__(self) -> None:
        """Initialize the PolicyKGBuilder."""
        self._llm_client = None

    async def build_policy_kg(
        self,
        session: AsyncSession,
        policy_id: str,
        use_llm: bool = True,
    ) -> dict[str, Any]:
        """Build PolicyKG nodes and edges from a policy document.

        Args:
            session: Database session.
            policy_id: ID of the policy to process.
            use_llm: Whether to use LLM for extraction (default True).

        Returns:
            Summary of created nodes, edges, and rules.
        """
        # Get policy with sections
        result = await session.execute(
            select(Policy).where(Policy.id == policy_id)
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        # Get sections
        sections_result = await session.execute(
            select(PolicySection).where(PolicySection.policy_id == policy_id)
        )
        sections = list(sections_result.scalars().all())

        if not sections:
            logger.warning(f"No sections found for policy {policy_id}")
            return {"nodes": 0, "edges": 0, "rules": 0}

        created_nodes = []
        created_edges = []
        created_rules = []

        for section in sections:
            try:
                if use_llm:
                    extracted_rules = await self._extract_rules_with_llm(section.content_text)
                else:
                    extracted_rules = self._extract_rules_heuristic(section.content_text)

                for rule in extracted_rules:
                    # Create PolicyKG nodes and edges
                    nodes, edges = await self._create_kg_from_rule(
                        session, rule, section.id
                    )
                    created_nodes.extend(nodes)
                    created_edges.extend(edges)

                    # Create PolicyRule record
                    policy_rule = await self._create_policy_rule(
                        session, rule, section.id, nodes
                    )
                    if policy_rule:
                        created_rules.append(policy_rule)

            except Exception as e:
                logger.error(f"Error processing section {section.id}: {e}")
                continue

        await session.flush()

        return {
            "nodes": len(created_nodes),
            "edges": len(created_edges),
            "rules": len(created_rules),
        }

    async def _extract_rules_with_llm(self, section_text: str) -> list[ExtractedRule]:
        """Extract rules from section text using LLM.

        Args:
            section_text: The policy section content.

        Returns:
            List of extracted rules.
        """
        try:
            from app.services.llm_service import get_llm_service

            llm = get_llm_service()

            prompt = RULE_EXTRACTION_PROMPT.format(section_text=section_text[:4000])
            response = await llm.generate(prompt, max_tokens=2000)

            # Parse JSON response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON array found in LLM response")
                return []

            rules_data = json.loads(json_match.group())
            return self._parse_extracted_rules(rules_data, section_text)

        except Exception as e:
            logger.error(f"LLM rule extraction failed: {e}")
            # Fall back to heuristic extraction
            return self._extract_rules_heuristic(section_text)

    def _extract_rules_heuristic(self, section_text: str) -> list[ExtractedRule]:
        """Extract rules using heuristic pattern matching.

        Args:
            section_text: The policy section content.

        Returns:
            List of extracted rules.
        """
        rules = []

        # Pattern for common rule structures
        patterns = [
            # "If X, then Y" patterns
            r"(?:If|When|For patients? (?:with|who))\s+(.+?)[,;]\s*(?:then\s+)?(.+?)(?:\.|$)",
            # "X should Y" patterns
            r"(?:Patients?|Individuals?)\s+(?:with|who have)\s+(.+?)\s+should\s+(.+?)(?:\.|$)",
            # "Recommend X for Y" patterns
            r"(?:Recommend|Consider|Initiate)\s+(.+?)\s+(?:for|in)\s+(.+?)(?:\.|$)",
            # "X is indicated for Y" patterns
            r"(.+?)\s+is\s+(?:indicated|recommended|suggested)\s+(?:for|in|when)\s+(.+?)(?:\.|$)",
        ]

        for i, pattern in enumerate(patterns):
            matches = re.finditer(pattern, section_text, re.IGNORECASE | re.MULTILINE)
            for j, match in enumerate(matches):
                try:
                    condition_text = match.group(1).strip() if len(match.groups()) > 0 else ""
                    action_text = match.group(2).strip() if len(match.groups()) > 1 else match.group(1).strip()

                    rule = ExtractedRule(
                        rule_id=f"RULE_{i}_{j}",
                        name=f"Rule from pattern {i+1}",
                        description=match.group(0).strip(),
                        source_text=match.group(0).strip(),
                        conditions=[
                            ExtractedCondition(
                                text=condition_text,
                                condition_type="other",
                            )
                        ] if condition_text else [],
                        actions=[
                            ExtractedAction(
                                text=action_text,
                                action_type="other",
                            )
                        ],
                        exceptions=[],
                        extraction_confidence=0.5,  # Lower confidence for heuristic
                    )
                    rules.append(rule)
                except Exception as e:
                    logger.debug(f"Pattern match failed: {e}")

        return rules

    def _parse_extracted_rules(
        self, rules_data: list[dict], source_text: str
    ) -> list[ExtractedRule]:
        """Parse LLM-extracted rule data into ExtractedRule objects.

        Args:
            rules_data: List of rule dictionaries from LLM.
            source_text: Original source text.

        Returns:
            List of ExtractedRule objects.
        """
        rules = []

        for i, data in enumerate(rules_data):
            try:
                conditions = [
                    ExtractedCondition(
                        text=c.get("text", ""),
                        condition_type=c.get("type", "other"),
                        value=c.get("value"),
                        operator=c.get("operator"),
                        threshold=c.get("threshold"),
                        threshold_unit=c.get("unit"),
                    )
                    for c in data.get("conditions", [])
                ]

                actions = [
                    ExtractedAction(
                        text=a.get("text", ""),
                        action_type=a.get("type", "other"),
                        target=a.get("target"),
                        frequency=a.get("frequency"),
                        dosage=a.get("dosage"),
                    )
                    for a in data.get("actions", [])
                ]

                exceptions = [
                    ExtractedCondition(
                        text=e.get("text", ""),
                        condition_type=e.get("type", "other"),
                    )
                    for e in data.get("exceptions", [])
                ]

                rule = ExtractedRule(
                    rule_id=f"LLM_RULE_{i}",
                    name=data.get("name", f"Extracted Rule {i+1}"),
                    description=data.get("description", ""),
                    source_text=source_text[:500],
                    conditions=conditions,
                    actions=actions,
                    exceptions=exceptions,
                    evidence_grade=data.get("evidence_grade"),
                    recommendation_strength=data.get("recommendation_strength"),
                    applies_to_conditions=data.get("applies_to_conditions", []),
                    applies_to_medications=data.get("applies_to_medications", []),
                    applies_to_measurements=data.get("applies_to_measurements", []),
                    extraction_confidence=data.get("confidence", 0.8),
                )
                rules.append(rule)

            except Exception as e:
                logger.warning(f"Failed to parse rule {i}: {e}")

        return rules

    async def _create_kg_from_rule(
        self,
        session: AsyncSession,
        rule: ExtractedRule,
        section_id: str,
    ) -> tuple[list[PolicyKGNode], list[PolicyKGEdge]]:
        """Create PolicyKG nodes and edges from an extracted rule.

        Args:
            session: Database session.
            rule: The extracted rule.
            section_id: Source policy section ID.

        Returns:
            Tuple of (created_nodes, created_edges).
        """
        nodes = []
        edges = []
        now = datetime.now(timezone.utc)

        # Create rule node
        rule_node = PolicyKGNode(
            id=str(uuid4()),
            policy_section_id=section_id,
            node_type=PolicyNodeType.RULE.value,
            label=rule.name,
            description=rule.description,
            evidence_grade=rule.evidence_grade,
            recommendation_strength=rule.recommendation_strength,
            extraction_confidence=rule.extraction_confidence,
            source_text=rule.source_text,
            effective_from=now,
            created_at=now,
        )
        session.add(rule_node)
        nodes.append(rule_node)

        # Create condition nodes and edges
        for condition in rule.conditions:
            cond_node = PolicyKGNode(
                id=str(uuid4()),
                policy_section_id=section_id,
                node_type=PolicyNodeType.CONDITION.value,
                label=condition.text[:200],
                description=condition.text,
                rule_logic={
                    "condition_type": condition.condition_type,
                    "value": condition.value,
                    "operator": condition.operator,
                    "threshold": condition.threshold,
                    "threshold_unit": condition.threshold_unit,
                },
                omop_concept_ids=condition.omop_concept_ids or None,
                effective_from=now,
                created_at=now,
            )
            session.add(cond_node)
            nodes.append(cond_node)

            # Edge: Condition -> Rule (IF_THEN relationship)
            edge = PolicyKGEdge(
                id=str(uuid4()),
                source_node_id=cond_node.id,
                target_node_id=rule_node.id,
                edge_type=PolicyEdgeType.IF_THEN.value,
                confidence=rule.extraction_confidence,
                effective_from=now,
                created_at=now,
            )
            session.add(edge)
            edges.append(edge)

        # Create action nodes and edges
        for action in rule.actions:
            action_node = PolicyKGNode(
                id=str(uuid4()),
                policy_section_id=section_id,
                node_type=PolicyNodeType.ACTION.value,
                label=action.text[:200],
                description=action.text,
                rule_logic={
                    "action_type": action.action_type,
                    "target": action.target,
                    "frequency": action.frequency,
                    "dosage": action.dosage,
                },
                omop_concept_ids=action.omop_concept_ids or None,
                effective_from=now,
                created_at=now,
            )
            session.add(action_node)
            nodes.append(action_node)

            # Edge: Rule -> Action (RECOMMENDS relationship)
            edge = PolicyKGEdge(
                id=str(uuid4()),
                source_node_id=rule_node.id,
                target_node_id=action_node.id,
                edge_type=PolicyEdgeType.RECOMMENDS.value,
                confidence=rule.extraction_confidence,
                effective_from=now,
                created_at=now,
            )
            session.add(edge)
            edges.append(edge)

        # Create exception nodes and edges
        for exception in rule.exceptions:
            exc_node = PolicyKGNode(
                id=str(uuid4()),
                policy_section_id=section_id,
                node_type=PolicyNodeType.EXCEPTION.value,
                label=exception.text[:200],
                description=exception.text,
                rule_logic={
                    "condition_type": exception.condition_type,
                },
                effective_from=now,
                created_at=now,
            )
            session.add(exc_node)
            nodes.append(exc_node)

            # Edge: Rule -> Exception (UNLESS relationship)
            edge = PolicyKGEdge(
                id=str(uuid4()),
                source_node_id=rule_node.id,
                target_node_id=exc_node.id,
                edge_type=PolicyEdgeType.UNLESS.value,
                confidence=rule.extraction_confidence,
                effective_from=now,
                created_at=now,
            )
            session.add(edge)
            edges.append(edge)

        # Compute embeddings for nodes
        await self._add_embeddings_to_nodes(nodes)

        return nodes, edges

    async def _create_policy_rule(
        self,
        session: AsyncSession,
        rule: ExtractedRule,
        section_id: str,
        nodes: list[PolicyKGNode],
    ) -> PolicyRule | None:
        """Create a PolicyRule record from an extracted rule.

        Args:
            session: Database session.
            rule: The extracted rule.
            section_id: Source policy section ID.
            nodes: Created KG nodes for this rule.

        Returns:
            Created PolicyRule or None.
        """
        try:
            # Find the rule node
            rule_node = next(
                (n for n in nodes if n.node_type == PolicyNodeType.RULE.value),
                None
            )

            # Build structured IF/THEN/UNLESS dicts
            if_conditions = {
                "conditions": [
                    {
                        "text": c.text,
                        "type": c.condition_type,
                        "value": c.value,
                        "operator": c.operator,
                        "threshold": c.threshold,
                        "unit": c.threshold_unit,
                    }
                    for c in rule.conditions
                ],
                "logic": "AND",  # Default to AND logic
            }

            then_actions = {
                "actions": [
                    {
                        "text": a.text,
                        "type": a.action_type,
                        "target": a.target,
                        "frequency": a.frequency,
                        "dosage": a.dosage,
                    }
                    for a in rule.actions
                ]
            }

            unless_exceptions = None
            if rule.exceptions:
                unless_exceptions = {
                    "exceptions": [
                        {
                            "text": e.text,
                            "type": e.condition_type,
                        }
                        for e in rule.exceptions
                    ]
                }

            # Generate unique rule_id
            rule_id = f"{rule.rule_id}_{section_id[:8]}"

            # Check if rule already exists
            existing = await session.execute(
                select(PolicyRule).where(PolicyRule.rule_id == rule_id)
            )
            if existing.scalar_one_or_none():
                logger.debug(f"Rule {rule_id} already exists, skipping")
                return None

            now = datetime.now(timezone.utc)

            policy_rule = PolicyRule(
                id=str(uuid4()),
                rule_id=rule_id,
                name=rule.name,
                description=rule.description,
                policy_section_id=section_id,
                policy_kg_node_id=rule_node.id if rule_node else None,
                if_conditions=if_conditions,
                then_actions=then_actions,
                unless_exceptions=unless_exceptions,
                applies_to_conditions=rule.applies_to_conditions or None,
                applies_to_medications=rule.applies_to_medications or None,
                applies_to_measurements=rule.applies_to_measurements or None,
                evidence_grade=rule.evidence_grade,
                recommendation_strength=rule.recommendation_strength,
                effective_from=now,
                is_active=True,
                created_at=now,
            )

            # Compute embedding
            try:
                from app.services.embedding_service import get_embedding_service

                embed_svc = get_embedding_service()
                rule_text = f"{rule.name} {rule.description}"
                policy_rule.embedding = embed_svc.encode(rule_text)
            except Exception as e:
                logger.warning(f"Failed to compute rule embedding: {e}")

            session.add(policy_rule)
            return policy_rule

        except Exception as e:
            logger.error(f"Failed to create PolicyRule: {e}")
            return None

    async def _add_embeddings_to_nodes(self, nodes: list[PolicyKGNode]) -> None:
        """Add embeddings to PolicyKG nodes.

        Args:
            nodes: List of nodes to add embeddings to.
        """
        try:
            from app.services.embedding_service import get_embedding_service

            embed_svc = get_embedding_service()

            texts = [f"{n.label} {n.description or ''}" for n in nodes]
            embeddings = embed_svc.encode_batch(texts)

            for node, embedding in zip(nodes, embeddings):
                node.embedding = embedding

        except Exception as e:
            logger.warning(f"Failed to compute node embeddings: {e}")

    async def search_policy_rules(
        self,
        session: AsyncSession,
        query: str,
        patient_conditions: list[str] | None = None,
        top_k: int = 5,
    ) -> list[PolicyRule]:
        """Search policy rules using semantic similarity.

        Args:
            session: Database session.
            query: Search query.
            patient_conditions: Optional list of patient conditions for boosting.
            top_k: Number of results to return.

        Returns:
            List of matching PolicyRule records.
        """
        # Get active rules with embeddings
        result = await session.execute(
            select(PolicyRule)
            .where(PolicyRule.is_active == True)
            .where(PolicyRule.embedding.is_not(None))
        )
        rules = list(result.scalars().all())

        if not rules:
            return []

        try:
            from app.services.embedding_service import get_embedding_service

            embed_svc = get_embedding_service()
            query_embedding = embed_svc.encode(query)

            scored = []
            for rule in rules:
                if not rule.embedding:
                    continue

                similarity = embed_svc.cosine_similarity(query_embedding, rule.embedding)

                # Boost for condition match
                boost = 0.0
                if patient_conditions and rule.applies_to_conditions:
                    for cond in patient_conditions:
                        if any(
                            cond.lower() in ac.lower()
                            for ac in rule.applies_to_conditions
                        ):
                            boost += 0.1

                scored.append((rule, similarity + boost))

            scored.sort(key=lambda x: x[1], reverse=True)
            return [r for r, _ in scored[:top_k]]

        except Exception as e:
            logger.error(f"Policy rule search failed: {e}")
            return []

    async def get_rules_for_condition(
        self,
        session: AsyncSession,
        condition_name: str,
    ) -> list[PolicyRule]:
        """Get all policy rules that apply to a specific condition.

        Args:
            session: Database session.
            condition_name: Name of the condition.

        Returns:
            List of applicable PolicyRule records.
        """
        result = await session.execute(
            select(PolicyRule)
            .where(PolicyRule.is_active == True)
            .where(PolicyRule.applies_to_conditions.any(condition_name))
        )
        return list(result.scalars().all())

    async def get_rules_for_medication(
        self,
        session: AsyncSession,
        medication_name: str,
    ) -> list[PolicyRule]:
        """Get all policy rules that reference a specific medication.

        Args:
            session: Database session.
            medication_name: Name of the medication.

        Returns:
            List of applicable PolicyRule records.
        """
        result = await session.execute(
            select(PolicyRule)
            .where(PolicyRule.is_active == True)
            .where(PolicyRule.applies_to_medications.any(medication_name))
        )
        return list(result.scalars().all())


# Singleton
_policy_kg_builder: PolicyKGBuilder | None = None
_builder_lock = threading.Lock()


def get_policy_kg_builder() -> PolicyKGBuilder:
    """Get the singleton PolicyKGBuilder instance."""
    global _policy_kg_builder
    if _policy_kg_builder is None:
        with _builder_lock:
            if _policy_kg_builder is None:
                logger.info("Creating singleton PolicyKGBuilder instance")
                _policy_kg_builder = PolicyKGBuilder()
    return _policy_kg_builder
