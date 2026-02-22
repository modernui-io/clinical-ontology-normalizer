#!/usr/bin/env python3
"""Compute gold-standard answers for Task C (calculator) benchmark questions.

Replaces vague expected answers like "The Wells PE score is computed from
clinical signs..." with actual computed scores from the calculator pipeline.

For each Task C question:
1. Identify the calculator type from question metadata
2. Attempt to run the calculator against the patient's KG data
3. If computable, store the numerical score + risk category + component breakdown
4. If not computable (missing data), mark as computable=false

Usage:
    cd backend
    uv run python scripts/compute_task_c_gold_standards.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.calculator_definitions import (
    CALCULATOR_DEFINITIONS,
    get_calculator_definition,
    calculate_point_based_score,
    calculate_equation_score,
    CalculatorType,
)
from app.services.calculator_kg_integration import CalculatorKGIntegration

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TASK_C_PATH = Path("data/benchmarks/task_c.json")
TASK_C_BACKUP_PATH = Path("data/benchmarks/task_c.json.bak")

# Map benchmark subtypes to calculator definition IDs
SUBTYPE_TO_CALCULATOR_ID = {
    "wells_pe": "wells_pe",
    "wells_dvt": "wells_dvt",
    "heart": "heart_score",
    "heart_score": "heart_score",
    "chadsvasc": "chadsvasc",
    "cha2ds2_vasc": "chadsvasc",
    "hasbled": "hasbled",
    "has_bled": "hasbled",
    "meld": "meld",
    "child_pugh": "child_pugh",
    "apache": "apache_ii",
    "apache_ii": "apache_ii",
    "sofa": "sofa",
    "curb65": "curb_65",
    "curb_65": "curb_65",
    "ascvd": "ascvd",
    "framingham": "framingham",
    "gfr": "ckd_epi_gfr",
    "ckd_epi": "ckd_epi_gfr",
    "bmi": "bmi",
    "corrected_calcium": "corrected_calcium",
    "anion_gap": "anion_gap",
    "timi": "timi",
    "grace": "grace_score",
    "glasgow": "gcs",
    "gcs": "gcs",
    "nihss": "nihss",
    "other": None,  # Handled separately
}


def _format_score_answer(
    calculator_name: str,
    score: float | int,
    interpretation: str,
    components: dict[str, float | int | str] | None = None,
    risk_category: str | None = None,
) -> str:
    """Format a computed score into a gold-standard expected answer string."""
    parts = [f"{calculator_name}: {score}"]

    if risk_category:
        parts[0] += f" ({risk_category})"

    if interpretation:
        parts.append(interpretation)

    if components:
        component_strs = []
        for k, v in components.items():
            if isinstance(v, (int, float)) and v != 0:
                component_strs.append(f"{k}: {v}")
            elif isinstance(v, str) and v:
                component_strs.append(f"{k}: {v}")
        if component_strs:
            parts.append(f"Components: {', '.join(component_strs)}")

    return ". ".join(parts) + "."


def compute_gold_standard(
    question: dict,
    kg_integration: CalculatorKGIntegration | None,
) -> dict:
    """Compute gold-standard answer for a single Task C question.

    Returns:
        Updated question dict with computed expected_answer and computable flag.
    """
    subtype = question.get("subtype", "other")
    calculator_id = SUBTYPE_TO_CALCULATOR_ID.get(subtype)
    patient_id = f"MIMIC-{question['mimic_subject_id']}"
    metadata = question.get("metadata", {})

    # If no known calculator, mark non-computable with reasoning-based scoring
    if calculator_id is None:
        question["computable"] = False
        question["expected_answer"] = (
            f"This question requires clinical interpretation of the patient's data. "
            f"The answer should reference specific values from the patient's clinical record "
            f"and provide appropriate clinical context."
        )
        question["scoring_rubric"] = {
            "reasoning_quality": 0.5,
            "value_correct": 0.3,
            "interpretation_correct": 0.2,
        }
        return question

    # Look up calculator definition
    definition = get_calculator_definition(calculator_id)
    if definition is None:
        logger.warning(
            "Calculator definition not found: %s (question %s)",
            calculator_id, question["question_id"],
        )
        question["computable"] = False
        return question

    # Try to compute using KG data
    calc_result = None
    if kg_integration is not None:
        try:
            calc_result = kg_integration.calculate_for_patient(
                calculator_id=calculator_id,
                patient_id=patient_id,
            )
        except Exception as exc:
            logger.info(
                "Calculator %s failed for patient %s: %s",
                calculator_id, patient_id, exc,
            )

    if calc_result and calc_result.get("score") is not None:
        # Successfully computed — build rich gold-standard answer
        score = calc_result["score"]
        interpretation = calc_result.get("interpretation", "")
        risk_category = calc_result.get("risk_category", "")
        components = calc_result.get("component_scores", {})
        calculator_name = calc_result.get("calculator_name", definition.name)

        question["expected_answer"] = _format_score_answer(
            calculator_name=calculator_name,
            score=score,
            interpretation=interpretation,
            components=components,
            risk_category=risk_category,
        )
        question["computable"] = True
        question["computed_score"] = score
        question["computed_risk_category"] = risk_category
        question["computed_interpretation"] = interpretation

        logger.info(
            "Computed %s for %s: score=%s (%s)",
            calculator_id, patient_id, score, risk_category,
        )
    else:
        # Could not compute — likely missing KG data
        # Build a template answer describing what the correct computation would look like
        question["computable"] = False

        # Build expected answer from calculator definition
        param_names = [p.name for p in definition.parameters] if definition.parameters else []
        param_str = ", ".join(param_names[:6])

        question["expected_answer"] = (
            f"The {definition.name} should be computed using the following parameters: "
            f"{param_str}. The score requires extraction of these values from the patient's "
            f"clinical data. If data is insufficient, state which values are missing."
        )
        question["scoring_rubric"] = {
            "reasoning_quality": 0.6,
            "parameter_identification": 0.4,
        }

        logger.info(
            "Could not compute %s for %s — marked as non-computable",
            calculator_id, patient_id,
        )

    return question


def main():
    """Process all Task C questions and update gold standards."""
    if not TASK_C_PATH.exists():
        print(f"Task C file not found: {TASK_C_PATH}")
        sys.exit(1)

    # Load existing questions
    with open(TASK_C_PATH) as f:
        data = json.load(f)

    questions = data.get("questions", [])
    print(f"Processing {len(questions)} Task C questions...")

    # Try to initialize KG integration (may fail if Neo4j not available)
    kg_integration = None
    try:
        kg_integration = CalculatorKGIntegration()
        if kg_integration.driver is None:
            logger.warning("Neo4j not available — will mark all questions as non-computable")
            kg_integration = None
    except Exception as exc:
        logger.warning("KG integration init failed: %s", exc)

    # Backup original file
    if not TASK_C_BACKUP_PATH.exists():
        import shutil
        shutil.copy2(TASK_C_PATH, TASK_C_BACKUP_PATH)
        print(f"Backed up original to {TASK_C_BACKUP_PATH}")

    # Process each question
    computable_count = 0
    non_computable_count = 0

    for question in questions:
        question = compute_gold_standard(question, kg_integration)
        if question.get("computable", False):
            computable_count += 1
        else:
            non_computable_count += 1

    # Update the data
    data["questions"] = questions
    data["version"] = "1.1.0"
    data["gold_standard_computed"] = True

    # Write updated file
    with open(TASK_C_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nDone! Updated {TASK_C_PATH}")
    print(f"  Computable: {computable_count}")
    print(f"  Non-computable: {non_computable_count}")
    print(f"  Total: {len(questions)}")


if __name__ == "__main__":
    main()
