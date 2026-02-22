#!/usr/bin/env python3
"""Compute gold-standard answers for Task D (multi-source fusion) benchmark questions.

Replaces metadata descriptions like "Multi-source analysis required. Patient has
22 Vital Signs mentions..." with actual clinical content extracted from the
patient's ingested data.

For each Task D question:
1. Load the patient's mentions from the database (grouped by section)
2. Extract vital signs, physical exam findings, and narrative mentions
3. Build a gold-standard answer describing actual clinical picture:
   consistency, discrepancies, and trending
4. Store the rich answer as expected_answer

Usage:
    cd backend
    uv run python scripts/compute_task_d_gold_standards.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TASK_D_PATH = Path("data/benchmarks/task_d.json")
TASK_D_BACKUP_PATH = Path("data/benchmarks/task_d.json.bak")


def _get_patient_mentions_by_section(
    session, patient_id: str,
) -> dict[str, list[dict]]:
    """Query mentions for a patient, grouped by document section.

    Returns:
        Dict mapping section name -> list of mention dicts.
    """
    from sqlalchemy import select
    from app.models.mention import Mention
    from app.models.document import Document

    stmt = (
        select(Mention)
        .join(Document, Document.id == Mention.document_id)
        .where(Document.patient_id == patient_id)
        .order_by(Mention.section, Mention.start_offset)
    )
    result = session.execute(stmt)
    mentions = result.scalars().all()

    by_section: dict[str, list[dict]] = defaultdict(list)
    for m in mentions:
        section = m.section or "Unknown"
        by_section[section].append({
            "text": m.text,
            "lexical_variant": m.lexical_variant,
            "assertion": m.assertion.value if hasattr(m.assertion, "value") else str(m.assertion),
            "temporality": m.temporality.value if hasattr(m.temporality, "value") else str(m.temporality),
            "section": section,
        })

    return dict(by_section)


def _get_patient_documents(session, patient_id: str) -> list[dict]:
    """Get patient documents with text excerpts."""
    from sqlalchemy import select
    from app.models.document import Document

    stmt = (
        select(Document)
        .where(Document.patient_id == patient_id)
        .order_by(Document.created_at.desc())
        .limit(5)
    )
    result = session.execute(stmt)
    docs = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "note_type": d.note_type,
            "text_excerpt": (d.text[:1000] if d.text else ""),
        }
        for d in docs
    ]


# Vital sign patterns for extraction from free text
_VITAL_PATTERNS = {
    "heart_rate": r"(?:HR|heart\s+rate|pulse)\s*[:=]?\s*(\d{2,3})",
    "blood_pressure_systolic": r"(?:BP|blood\s+pressure|SBP)\s*[:=]?\s*(\d{2,3})/",
    "blood_pressure_diastolic": r"/(\d{2,3})",
    "temperature": r"(?:Temp|temperature|T)\s*[:=]?\s*(\d{2,3}\.?\d?)",
    "respiratory_rate": r"(?:RR|resp(?:iratory)?\s+rate)\s*[:=]?\s*(\d{1,2})",
    "o2_saturation": r"(?:SpO2|O2\s*sat|SaO2)\s*[:=]?\s*(\d{2,3})%?",
}


def _extract_vital_signs_from_mentions(
    mentions: list[dict],
) -> list[str]:
    """Extract vital sign findings from a list of mentions.

    Returns list of formatted vital sign strings.
    """
    import re

    vitals = []
    seen = set()

    for m in mentions:
        text = m.get("text", "") or m.get("lexical_variant", "")
        text_lower = text.lower()

        # Check for vital sign keywords
        for vital_name, pattern in _VITAL_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                key = f"{vital_name}:{value}"
                if key not in seen:
                    seen.add(key)
                    assertion = m.get("assertion", "present")
                    label = vital_name.replace("_", " ").title()
                    vitals.append(f"{label}: {value} ({assertion})")

        # Also capture qualitative vital sign descriptions
        vital_keywords = [
            "tachycardia", "bradycardia", "hypotension", "hypertension",
            "tachypnea", "bradypnea", "fever", "febrile", "afebrile",
            "hypothermia", "hypoxia", "hypoxic", "normotensive",
            "hemodynamically stable", "hemodynamically unstable",
        ]
        for kw in vital_keywords:
            if kw in text_lower and kw not in seen:
                seen.add(kw)
                assertion = m.get("assertion", "present")
                vitals.append(f"{kw.title()} ({assertion})")

    return vitals


def _find_discrepancies(
    target_mentions: list[dict],
    narrative_mentions: list[dict],
) -> list[str]:
    """Find discrepancies between structured (target) and narrative sections.

    Returns list of discrepancy descriptions.
    """
    discrepancies = []

    # Build sets of key findings per source
    target_findings = set()
    for m in target_mentions:
        text = (m.get("text", "") or "").lower()
        for kw in ["tachycardia", "bradycardia", "hypotension", "hypertension",
                    "fever", "febrile", "afebrile", "hypoxia", "stable", "unstable"]:
            if kw in text:
                target_findings.add((kw, m.get("assertion", "present")))

    narrative_findings = set()
    for m in narrative_mentions:
        text = (m.get("text", "") or "").lower()
        for kw in ["tachycardia", "bradycardia", "hypotension", "hypertension",
                    "fever", "febrile", "afebrile", "hypoxia", "stable", "unstable"]:
            if kw in text:
                narrative_findings.add((kw, m.get("assertion", "present")))

    # Check for contradictions
    for finding, assertion in target_findings:
        for n_finding, n_assertion in narrative_findings:
            if finding == n_finding and assertion != n_assertion:
                discrepancies.append(
                    f"'{finding}' is {assertion} in structured data but {n_assertion} in narrative"
                )

    # Check for conflicting qualitative assessments
    stable_in_target = any(
        "stable" in (m.get("text", "") or "").lower()
        and m.get("assertion", "present") == "present"
        for m in target_mentions
    )
    unstable_in_narrative = any(
        "unstable" in (m.get("text", "") or "").lower()
        and m.get("assertion", "present") == "present"
        for m in narrative_mentions
    )
    if stable_in_target and unstable_in_narrative:
        discrepancies.append(
            "Structured data indicates 'stable' but narrative describes 'unstable'"
        )

    return discrepancies


def compute_gold_standard(
    question: dict,
    session,
) -> dict:
    """Compute gold-standard answer for a single Task D question."""
    patient_id = f"MIMIC-{question['mimic_subject_id']}"
    metadata = question.get("metadata", {})
    sections_compared = metadata.get("sections_compared", [])

    try:
        # Get patient mentions by section
        mentions_by_section = _get_patient_mentions_by_section(session, patient_id)

        if not mentions_by_section:
            # No DB data — build answer from question metadata
            question["computable"] = False
            question["expected_answer"] = (
                f"Insufficient data to determine vital sign consistency for patient {patient_id}. "
                f"The analysis requires comparison of {', '.join(sections_compared)} sections."
            )
            return question

        # Identify target and narrative sections
        target_section_names = []
        narrative_section_names = []
        for section in sections_compared:
            if section in mentions_by_section:
                if section in ("Vital Signs", "Physical Exam", "Labs"):
                    target_section_names.append(section)
                else:
                    narrative_section_names.append(section)

        # Gather mentions from each group
        target_mentions = []
        for s in target_section_names:
            target_mentions.extend(mentions_by_section.get(s, []))

        narrative_mentions = []
        for s in narrative_section_names:
            narrative_mentions.extend(mentions_by_section.get(s, []))

        # If no structured sections found, use all non-narrative sections
        if not target_mentions:
            for s, ms in mentions_by_section.items():
                if s in ("Vital Signs", "Physical Exam", "Labs", "Assessment"):
                    target_mentions.extend(ms)
                elif s not in sections_compared:
                    narrative_mentions.extend(ms)

        # Extract vital signs
        vital_signs = _extract_vital_signs_from_mentions(target_mentions)

        # Find discrepancies
        discrepancies = _find_discrepancies(target_mentions, narrative_mentions)

        # Build the gold-standard answer
        answer_parts = []

        if vital_signs:
            answer_parts.append(
                f"Documented vital signs and findings: {'; '.join(vital_signs[:8])}"
            )

        if discrepancies:
            answer_parts.append(
                f"Discrepancies identified: {'; '.join(discrepancies[:4])}"
            )
            answer_parts.append(
                "The vital signs and narrative sections show inconsistencies "
                "that require clinical reconciliation."
            )
        elif vital_signs:
            answer_parts.append(
                "The vital signs are generally consistent with the clinical "
                "picture described in the narrative sections."
            )

        if not answer_parts:
            answer_parts.append(
                f"Limited structured vital sign data available for patient {patient_id}. "
                f"Clinical assessment should rely primarily on narrative documentation."
            )

        question["expected_answer"] = " ".join(answer_parts)
        question["computable"] = bool(vital_signs)
        question["extracted_vital_signs"] = vital_signs[:10]
        question["discrepancies"] = discrepancies[:5]

        logger.info(
            "Processed %s: %d vital signs, %d discrepancies",
            patient_id, len(vital_signs), len(discrepancies),
        )

    except Exception as exc:
        logger.warning("Failed to process %s: %s", patient_id, exc)
        question["computable"] = False
        question["expected_answer"] = (
            f"Analysis of vital sign consistency requires comparing "
            f"{', '.join(sections_compared)} sections for patient {patient_id}. "
            f"The answer should identify specific vital sign values and assess "
            f"whether they are consistent with the clinical narrative."
        )

    return question


def main():
    """Process all Task D questions and update gold standards."""
    if not TASK_D_PATH.exists():
        print(f"Task D file not found: {TASK_D_PATH}")
        sys.exit(1)

    # Load existing questions
    with open(TASK_D_PATH) as f:
        data = json.load(f)

    questions = data.get("questions", [])
    print(f"Processing {len(questions)} Task D questions...")

    # Backup original file
    if not TASK_D_BACKUP_PATH.exists():
        import shutil
        shutil.copy2(TASK_D_PATH, TASK_D_BACKUP_PATH)
        print(f"Backed up original to {TASK_D_BACKUP_PATH}")

    # Try to get a DB session
    session = None
    try:
        from app.core.database import get_sync_engine
        from sqlalchemy.orm import Session

        engine = get_sync_engine()
        session = Session(engine)
        print("Connected to database for mention extraction.")
    except Exception as exc:
        logger.warning("Database not available: %s", exc)
        logger.warning("Will generate template answers from metadata only.")

    # Process each question
    computable_count = 0
    non_computable_count = 0

    for question in questions:
        question = compute_gold_standard(question, session)
        if question.get("computable", False):
            computable_count += 1
        else:
            non_computable_count += 1

    if session:
        session.close()

    # Update the data
    data["questions"] = questions
    data["version"] = "1.1.0"
    data["gold_standard_computed"] = True

    # Write updated file
    with open(TASK_D_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nDone! Updated {TASK_D_PATH}")
    print(f"  Computable: {computable_count}")
    print(f"  Non-computable: {non_computable_count}")
    print(f"  Total: {len(questions)}")


if __name__ == "__main__":
    main()
