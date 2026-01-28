"""Policy diff service for comparing policy versions and detecting conflicts.

Provides version comparison, change detection, and conflict analysis
between active policies.
"""

import logging
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.policy import Policy, PolicyAlertRule, PolicySection

logger = logging.getLogger(__name__)


async def compare_versions(
    session: AsyncSession,
    old_policy_id: str,
    new_policy_id: str,
) -> dict[str, Any]:
    """Compare two policy versions and identify changes.

    Returns added, removed, and modified sections along with affected rules.
    """
    old_policy = await session.execute(
        select(Policy).options(selectinload(Policy.sections)).where(Policy.id == old_policy_id)
    )
    old = old_policy.scalar_one_or_none()

    new_policy = await session.execute(
        select(Policy).options(selectinload(Policy.sections)).where(Policy.id == new_policy_id)
    )
    new = new_policy.scalar_one_or_none()

    if not old or not new:
        return {"error": "One or both policies not found"}

    old_sections = {s.section_number: s for s in (old.sections or [])}
    new_sections = {s.section_number: s for s in (new.sections or [])}

    old_keys = set(old_sections.keys())
    new_keys = set(new_sections.keys())

    added = []
    removed = []
    modified = []

    for key in new_keys - old_keys:
        sec = new_sections[key]
        added.append({
            "section_number": key,
            "title": sec.title,
            "content_preview": sec.content_text[:200],
        })

    for key in old_keys - new_keys:
        sec = old_sections[key]
        removed.append({
            "section_number": key,
            "title": sec.title,
            "content_preview": sec.content_text[:200],
        })

    for key in old_keys & new_keys:
        old_sec = old_sections[key]
        new_sec = new_sections[key]
        if old_sec.content_text != new_sec.content_text:
            similarity = SequenceMatcher(
                None, old_sec.content_text, new_sec.content_text
            ).ratio()
            modified.append({
                "section_number": key,
                "old_title": old_sec.title,
                "new_title": new_sec.title,
                "similarity": round(similarity, 3),
                "change_magnitude": "major" if similarity < 0.5 else "minor" if similarity > 0.8 else "moderate",
            })

    # Find affected alert rules
    affected_section_ids = [
        old_sections[k].id for k in (old_keys - new_keys)  # removed
    ] + [
        old_sections[k].id for k in old_keys & new_keys  # modified
        if old_sections[k].content_text != new_sections[k].content_text
    ]

    affected_rules: list[dict] = []
    if affected_section_ids:
        rules_result = await session.execute(
            select(PolicyAlertRule).where(
                PolicyAlertRule.policy_section_id.in_(affected_section_ids)
            )
        )
        for rule_mapping in rules_result.scalars().all():
            affected_rules.append({
                "alert_rule_id": rule_mapping.alert_rule_id,
                "section_id": rule_mapping.policy_section_id,
                "confidence": rule_mapping.mapping_confidence,
            })

    return {
        "old_policy": {"id": old_policy_id, "name": old.name, "version": old.version},
        "new_policy": {"id": new_policy_id, "name": new.name, "version": new.version},
        "added_sections": added,
        "removed_sections": removed,
        "modified_sections": modified,
        "affected_rules": affected_rules,
        "summary": {
            "sections_added": len(added),
            "sections_removed": len(removed),
            "sections_modified": len(modified),
            "rules_affected": len(affected_rules),
        },
    }


async def detect_conflicts(
    session: AsyncSession,
    policy_id: str,
) -> dict[str, Any]:
    """Detect sections in a policy that conflict with other active policies.

    Uses embedding similarity to find potentially contradictory content.
    """
    target_policy = await session.execute(
        select(Policy).options(selectinload(Policy.sections)).where(Policy.id == policy_id)
    )
    target = target_policy.scalar_one_or_none()
    if not target:
        return {"error": "Policy not found"}

    # Get other active policies
    other_result = await session.execute(
        select(PolicySection)
        .join(Policy)
        .where(Policy.status == "active", Policy.id != policy_id)
        .where(PolicySection.embedding.is_not(None))
    )
    other_sections = list(other_result.scalars().all())

    conflicts = []
    for target_section in (target.sections or []):
        if not target_section.embedding:
            continue

        for other_section in other_sections:
            if not other_section.embedding:
                continue

            try:
                from app.services.embedding_service import get_embedding_service
                similarity = get_embedding_service().cosine_similarity(
                    target_section.embedding, other_section.embedding
                )
            except Exception:
                continue

            # High similarity between different policies may indicate conflict
            if similarity >= 0.75:
                conflicts.append({
                    "target_section": {
                        "id": target_section.id,
                        "title": target_section.title,
                        "section_number": target_section.section_number,
                    },
                    "conflicting_section": {
                        "id": other_section.id,
                        "title": other_section.title,
                        "policy_id": other_section.policy_id,
                    },
                    "similarity": round(similarity, 3),
                    "risk": "high" if similarity >= 0.9 else "medium",
                })

    return {
        "policy_id": policy_id,
        "policy_name": target.name,
        "conflicts": conflicts,
        "total_conflicts": len(conflicts),
    }
