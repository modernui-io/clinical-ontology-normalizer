"""Policy service for managing institutional policies and RAG search.

Handles upload, parsing, embedding, searching, and lifecycle management
of institutional policy documents.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.policy import Policy, PolicyAlertRule, PolicySection, PolicyStatus

logger = logging.getLogger(__name__)


class PolicyService:
    """Service for managing institutional policies."""

    async def upload_policy(
        self,
        session: AsyncSession,
        name: str,
        content_text: str,
        source_org: str | None = None,
        version: str | None = None,
        effective_date: datetime | None = None,
        uploaded_by: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Policy:
        """Upload a new policy, parse into sections, and compute embeddings."""
        content_hash = hashlib.sha256(content_text.encode()).hexdigest()

        policy = Policy(
            id=str(uuid4()),
            name=name,
            description=description,
            source_organization=source_org,
            version=version,
            effective_date=effective_date,
            uploaded_at=datetime.now(timezone.utc),
            uploaded_by=uploaded_by,
            status=PolicyStatus.DRAFT.value,
            content_text=content_text,
            content_hash=content_hash,
            extra_metadata=metadata,
        )
        session.add(policy)

        # Parse into sections
        sections = self._parse_sections(content_text)
        section_texts = [s["content"] for s in sections]

        # Compute embeddings
        embeddings = self._compute_embeddings(section_texts)

        for i, sec_data in enumerate(sections):
            section = PolicySection(
                id=str(uuid4()),
                policy_id=policy.id,
                section_number=sec_data.get("number", str(i + 1)),
                title=sec_data.get("title", f"Section {i + 1}"),
                content_text=sec_data["content"],
                keywords=sec_data.get("keywords", []),
                embedding=embeddings[i] if i < len(embeddings) else None,
            )
            session.add(section)

        await session.flush()
        return policy

    async def get_policy(
        self,
        session: AsyncSession,
        policy_id: str,
    ) -> Policy | None:
        """Get a policy with its sections."""
        result = await session.execute(
            select(Policy)
            .options(selectinload(Policy.sections))
            .where(Policy.id == policy_id)
        )
        return result.scalar_one_or_none()

    async def list_policies(
        self,
        session: AsyncSession,
        status_filter: str | None = None,
    ) -> list[Policy]:
        """List policies with optional status filter."""
        stmt = select(Policy).order_by(Policy.created_at.desc())
        if status_filter:
            stmt = stmt.where(Policy.status == status_filter)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_policy_status(
        self,
        session: AsyncSession,
        policy_id: str,
        new_status: str,
    ) -> Policy | None:
        """Update the status of a policy."""
        result = await session.execute(
            select(Policy).where(Policy.id == policy_id)
        )
        policy = result.scalar_one_or_none()
        if policy:
            policy.status = new_status
            await session.flush()
        return policy

    async def search_policy_sections(
        self,
        session: AsyncSession,
        query: str,
        patient_conditions: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search active policy sections using embedding similarity."""
        # Get active policy sections
        result = await session.execute(
            select(PolicySection)
            .join(Policy)
            .where(Policy.status == PolicyStatus.ACTIVE.value)
            .where(PolicySection.embedding.is_not(None))
        )
        sections = list(result.scalars().all())
        if not sections:
            return []

        # Compute query embedding
        try:
            from app.services.embedding_service import get_embedding_service
            embed_svc = get_embedding_service()
            query_embedding = embed_svc.encode(query)
        except Exception as e:
            logger.warning(f"Embedding service unavailable for policy search: {e}")
            return []

        # Score and rank
        scored = []
        for section in sections:
            if not section.embedding:
                continue
            try:
                from app.services.embedding_service import get_embedding_service
                similarity = get_embedding_service().cosine_similarity(
                    query_embedding, section.embedding
                )
            except Exception:
                continue

            # Boost for condition match
            boost = 0.0
            if patient_conditions and section.applies_to_conditions:
                for cond in patient_conditions:
                    if any(
                        cond.lower() in ac.lower()
                        for ac in section.applies_to_conditions
                    ):
                        boost += 0.1

            final_score = similarity + boost

            scored.append({
                "section_id": section.id,
                "policy_id": section.policy_id,
                "policy_name": "",  # Will fill after
                "section_title": section.title or f"Section {section.section_number}",
                "content_text": section.content_text,
                "relevance_score": round(final_score, 4),
            })

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_results = scored[:top_k]

        # Fill policy names
        policy_ids = {r["policy_id"] for r in top_results}
        if policy_ids:
            policies_result = await session.execute(
                select(Policy).where(Policy.id.in_(policy_ids))
            )
            policy_map = {str(p.id): p.name for p in policies_result.scalars().all()}
            for r in top_results:
                r["policy_name"] = policy_map.get(r["policy_id"], "Unknown Policy")

        return top_results

    async def link_policy_to_rules(
        self,
        session: AsyncSession,
        policy_id: str,
    ) -> list[PolicyAlertRule]:
        """Link policy sections to alert rules via semantic similarity."""
        from app.services.alert_rules_service import get_alert_rules_service

        policy = await self.get_policy(session, policy_id)
        if not policy or not policy.sections:
            return []

        alert_svc = get_alert_rules_service()
        rules = alert_svc.list_rules()
        if not rules:
            return []

        # Build rule embeddings
        try:
            from app.services.embedding_service import get_embedding_service
            embed_svc = get_embedding_service()
        except Exception:
            return []

        rule_texts = [f"{r.name}: {r.description}" for r in rules]
        rule_embeddings = embed_svc.encode_batch(rule_texts)

        mappings = []
        for section in policy.sections:
            if not section.embedding:
                continue

            for j, rule in enumerate(rules):
                if j >= len(rule_embeddings):
                    continue
                similarity = embed_svc.cosine_similarity(
                    section.embedding, rule_embeddings[j]
                )
                if similarity >= 0.5:
                    mapping = PolicyAlertRule(
                        id=str(uuid4()),
                        policy_section_id=section.id,
                        alert_rule_id=rule.id,
                        mapping_confidence=round(similarity, 4),
                        mapping_rationale=(
                            f"Semantic match: section '{section.title}' ↔ "
                            f"rule '{rule.name}' (score: {similarity:.3f})"
                        ),
                    )
                    session.add(mapping)
                    mappings.append(mapping)

        await session.flush()
        return mappings

    async def get_policy_rule_mappings(
        self,
        session: AsyncSession,
        policy_id: str,
    ) -> list[dict[str, Any]]:
        """Get alert rules linked to a policy."""
        result = await session.execute(
            select(PolicyAlertRule)
            .join(PolicySection)
            .where(PolicySection.policy_id == policy_id)
            .order_by(PolicyAlertRule.mapping_confidence.desc())
        )
        mappings = list(result.scalars().all())

        return [
            {
                "id": m.id,
                "policy_section_id": m.policy_section_id,
                "alert_rule_id": m.alert_rule_id,
                "mapping_confidence": m.mapping_confidence,
                "mapping_rationale": m.mapping_rationale,
            }
            for m in mappings
        ]

    def _parse_sections(self, content: str) -> list[dict[str, Any]]:
        """Parse policy text into numbered sections."""
        sections: list[dict[str, Any]] = []
        # Split on numbered sections or headings
        pattern = r'(?:^|\n)(?:(?:Section\s+)?(\d+(?:\.\d+)*)[.:\s]+|#{1,3}\s+)(.*?)(?=\n(?:(?:Section\s+)?\d+(?:\.\d+)*[.:\s]+|#{1,3}\s+)|\Z)'
        matches = list(re.finditer(pattern, content, re.DOTALL | re.IGNORECASE))

        if matches:
            for match in matches:
                number = match.group(1) or str(len(sections) + 1)
                title = match.group(2).strip().split('\n')[0].strip() if match.group(2) else ""
                body = match.group(0).strip()
                keywords = self._extract_keywords(body)
                sections.append({
                    "number": number,
                    "title": title[:500],
                    "content": body[:5000],
                    "keywords": keywords[:20],
                })
        else:
            # No sections found — split by paragraphs
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            for i, para in enumerate(paragraphs[:50]):
                sections.append({
                    "number": str(i + 1),
                    "title": para[:80].strip(),
                    "content": para[:5000],
                    "keywords": self._extract_keywords(para)[:20],
                })

        return sections or [{"number": "1", "title": "Full Policy", "content": content[:5000], "keywords": []}]

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract simple keywords from text."""
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will", "would", "shall",
                      "should", "may", "might", "must", "can", "could", "to", "of", "in",
                      "for", "on", "with", "at", "by", "from", "or", "and", "not", "no",
                      "but", "if", "this", "that", "these", "those", "it", "its", "as"}
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return list(dict.fromkeys(w for w in words if w not in stop_words))

    def _compute_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for a list of texts."""
        try:
            from app.services.embedding_service import get_embedding_service
            embed_svc = get_embedding_service()
            return cast(list[list[float]], embed_svc.encode_batch(texts))
        except Exception as e:
            logger.warning(f"Embedding computation failed: {e}")
            return []


# Singleton
_policy_service: PolicyService | None = None
_policy_lock = threading.Lock()


def get_policy_service() -> PolicyService:
    """Get the singleton PolicyService instance."""
    global _policy_service
    if _policy_service is None:
        with _policy_lock:
            if _policy_service is None:
                logger.info("Creating singleton PolicyService instance")
                _policy_service = PolicyService()
    return _policy_service
