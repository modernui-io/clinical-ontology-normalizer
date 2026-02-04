"""Calculator Reasoning Service for Clinical Agents.

This service integrates clinical calculators into the clinical reasoning workflow:
1. Analyzes patient data to identify applicable calculators
2. Auto-populates calculator inputs from KG measurements
3. Runs calculators and returns results for agent reasoning
4. Provides structured context for LLM-based clinical reasoning
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.services.calculator_definitions import (
    CALCULATOR_DEFINITIONS,
    CalculatorCategory,
    CalculatorType,
    get_calculator_definition,
    calculate_point_based_score,
    calculate_equation_score,
)
from app.services.kg_calculator_mapper import (
    build_calculator_inputs_from_measurements,
    get_measurements_for_calculator,
)

logger = logging.getLogger(__name__)


class CalculatorReasoningService:
    """Service for integrating calculators into clinical agent reasoning."""

    # Map clinical contexts to relevant calculator categories
    CONTEXT_CALCULATOR_MAP: dict[str, list[CalculatorCategory]] = {
        "cardiovascular": [CalculatorCategory.CARDIOVASCULAR],
        "cardiac": [CalculatorCategory.CARDIOVASCULAR],
        "heart": [CalculatorCategory.CARDIOVASCULAR],
        "stroke": [CalculatorCategory.CARDIOVASCULAR, CalculatorCategory.NEUROLOGICAL],
        "atrial fibrillation": [CalculatorCategory.CARDIOVASCULAR],
        "afib": [CalculatorCategory.CARDIOVASCULAR],
        "bleeding": [CalculatorCategory.CARDIOVASCULAR, CalculatorCategory.HEMATOLOGY],
        "anticoagulation": [CalculatorCategory.CARDIOVASCULAR],
        "renal": [CalculatorCategory.RENAL],
        "kidney": [CalculatorCategory.RENAL],
        "gfr": [CalculatorCategory.RENAL],
        "creatinine": [CalculatorCategory.RENAL],
        "liver": [CalculatorCategory.HEPATIC],
        "hepatic": [CalculatorCategory.HEPATIC],
        "cirrhosis": [CalculatorCategory.HEPATIC],
        "sepsis": [CalculatorCategory.CRITICAL_CARE, CalculatorCategory.INFECTIOUS],
        "icu": [CalculatorCategory.CRITICAL_CARE],
        "critical": [CalculatorCategory.CRITICAL_CARE],
        "sofa": [CalculatorCategory.CRITICAL_CARE],
        "pulmonary": [CalculatorCategory.PULMONARY],
        "pe": [CalculatorCategory.PULMONARY],
        "dvt": [CalculatorCategory.PULMONARY],
        "pneumonia": [CalculatorCategory.INFECTIOUS, CalculatorCategory.PULMONARY],
        "infection": [CalculatorCategory.INFECTIOUS],
        "diabetic": [CalculatorCategory.METABOLIC],
        "diabetes": [CalculatorCategory.METABOLIC],
        "sodium": [CalculatorCategory.METABOLIC, CalculatorCategory.RENAL],
        "potassium": [CalculatorCategory.METABOLIC, CalculatorCategory.RENAL],
        "electrolyte": [CalculatorCategory.METABOLIC],
        "acid-base": [CalculatorCategory.METABOLIC],
        "metabolic": [CalculatorCategory.METABOLIC],
        "neurologic": [CalculatorCategory.NEUROLOGICAL],
        "stroke scale": [CalculatorCategory.NEUROLOGICAL],
        "gi bleed": [CalculatorCategory.EMERGENCY],
        "emergency": [CalculatorCategory.EMERGENCY],
        "oncology": [CalculatorCategory.ONCOLOGY],
        "cancer": [CalculatorCategory.ONCOLOGY],
        "hematology": [CalculatorCategory.HEMATOLOGY],
        "anemia": [CalculatorCategory.HEMATOLOGY],
        "coagulation": [CalculatorCategory.HEMATOLOGY],
        "fall": [CalculatorCategory.GERIATRIC],
        "frailty": [CalculatorCategory.GERIATRIC],
        "dementia": [CalculatorCategory.GERIATRIC, CalculatorCategory.NEUROLOGICAL],
        "surgical": [CalculatorCategory.SURGICAL],
        "preoperative": [CalculatorCategory.SURGICAL],
        "obstetric": [CalculatorCategory.OBSTETRIC],
        "pregnancy": [CalculatorCategory.OBSTETRIC],
        "pediatric": [CalculatorCategory.PEDIATRIC],
    }

    def __init__(self):
        """Initialize the calculator reasoning service."""
        self._calculator_cache: dict[str, Any] = {}

    def identify_applicable_calculators(
        self,
        conditions: list[str],
        measurements: list[dict[str, Any]],
        clinical_question: str | None = None,
        demographics: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Identify calculators relevant to the patient's clinical context.

        Args:
            conditions: List of patient condition names
            measurements: List of measurement dicts with 'label', 'value', 'unit'
            clinical_question: Optional clinical question for context-based filtering
            demographics: Optional demographics with 'age', 'sex', etc.
            limit: Maximum number of calculators to return

        Returns:
            List of applicable calculator suggestions with relevance scores
        """
        suggestions: list[dict[str, Any]] = []
        conditions_lower = [c.lower() for c in conditions]
        measurement_labels_lower = [m.get("label", "").lower() for m in measurements]

        # Determine relevant categories from clinical context
        relevant_categories: set[CalculatorCategory] = set()

        # From conditions
        for condition in conditions_lower:
            for keyword, categories in self.CONTEXT_CALCULATOR_MAP.items():
                if keyword in condition:
                    relevant_categories.update(categories)

        # From clinical question
        if clinical_question:
            question_lower = clinical_question.lower()
            for keyword, categories in self.CONTEXT_CALCULATOR_MAP.items():
                if keyword in question_lower:
                    relevant_categories.update(categories)

        # Score each calculator
        for calc_id, definition in CALCULATOR_DEFINITIONS.items():
            relevance_score = 0.0
            reasons: list[str] = []
            data_completeness = 0.0

            # Category relevance
            if relevant_categories and definition.category in relevant_categories:
                relevance_score += 3.0
                reasons.append(f"Category match: {definition.category.value}")

            # Condition-based relevance
            for condition in conditions_lower:
                # Check if calculator name/description mentions the condition
                if condition in definition.name.lower() or condition in definition.description.lower():
                    relevance_score += 2.0
                    reasons.append(f"Condition match: {condition}")
                    break

            # Data availability scoring
            if definition.calc_type == CalculatorType.EQUATION and definition.formula:
                needed_params = [p.name.lower() for p in definition.formula.parameters]
                available = sum(1 for p in needed_params if any(p in ml for ml in measurement_labels_lower))
                total = len(needed_params)
                if total > 0:
                    data_completeness = available / total
                    if data_completeness >= 0.5:
                        relevance_score += data_completeness * 2.0
                        reasons.append(f"Data availability: {available}/{total} parameters")
            elif definition.calc_type == CalculatorType.CRITERIA:
                # Criteria calculators often use demographics + conditions
                needed_measurements = get_measurements_for_calculator(calc_id)
                if needed_measurements:
                    available = sum(
                        1 for m in needed_measurements
                        if any(m.lower() in ml for ml in measurement_labels_lower)
                    )
                    total = len(needed_measurements)
                    if total > 0:
                        data_completeness = available / total
                        if data_completeness > 0:
                            relevance_score += data_completeness
                            reasons.append(f"Measurements: {available}/{total} available")

            # Age-appropriate calculator boost
            age = demographics.get("age") if demographics else None
            if age:
                if age >= 65 and "65" in definition.name:
                    relevance_score += 1.0
                    reasons.append("Age-appropriate (65+)")
                elif age < 18 and "pediatric" in definition.name.lower():
                    relevance_score += 1.0
                    reasons.append("Age-appropriate (pediatric)")

            if relevance_score > 0:
                suggestions.append({
                    "calculator_id": calc_id,
                    "calculator_name": definition.name,
                    "short_name": definition.short_name,
                    "category": definition.category.value,
                    "calc_type": definition.calc_type.value,
                    "description": definition.description,
                    "relevance_score": round(relevance_score, 2),
                    "data_completeness": round(data_completeness, 2),
                    "reasons": reasons,
                })

        # Sort by relevance and return top N
        suggestions.sort(key=lambda x: (x["relevance_score"], x["data_completeness"]), reverse=True)
        return suggestions[:limit]

    def calculate_with_patient_data(
        self,
        calculator_id: str,
        measurements: list[dict[str, Any]],
        demographics: dict[str, Any] | None = None,
        conditions: list[str] | None = None,
        additional_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a calculator using patient measurement data.

        Args:
            calculator_id: Calculator to execute
            measurements: List of measurement dicts with 'label', 'value', 'unit'
            demographics: Optional demographics with 'age', 'sex', etc.
            conditions: Optional list of condition names for criteria-based calculators
            additional_inputs: Additional/override inputs

        Returns:
            Calculator result with score, interpretation, and provenance
        """
        definition = get_calculator_definition(calculator_id)
        if definition is None:
            raise ValueError(f"Calculator not found: {calculator_id}")

        # Build inputs from measurements
        inputs, mapping_info = build_calculator_inputs_from_measurements(
            calculator_id, measurements
        )

        # Add demographics
        if demographics:
            if demographics.get("age"):
                inputs["age"] = demographics["age"]
            if demographics.get("sex"):
                inputs["female"] = 1 if str(demographics["sex"]).lower() in ["f", "female"] else 0

        # Map conditions to criteria (for criteria-based calculators)
        if conditions and definition.calc_type == CalculatorType.CRITERIA:
            inputs = self._map_conditions_to_criteria(definition, conditions, inputs)

        # Merge additional inputs (overrides)
        if additional_inputs:
            inputs.update(additional_inputs)

        # Execute calculation
        if definition.calc_type == CalculatorType.CRITERIA:
            # For criteria calculators, age is passed separately for scoring
            age = inputs.pop("age", None)
            result = calculate_point_based_score(definition, inputs, age)
        elif definition.calc_type == CalculatorType.EQUATION:
            # For equation calculators, keep age in inputs (it's a formula parameter)
            result = calculate_equation_score(definition, inputs)
        else:
            raise ValueError(f"Unsupported calculator type: {definition.calc_type}")

        # Build response with provenance
        return {
            "calculator_id": calculator_id,
            "calculator_name": result.calculator_name,
            "score": result.score,
            "score_unit": result.score_unit,
            "risk_level": result.risk_level.value if result.risk_level else None,
            "interpretation": result.interpretation,
            "recommendations": result.recommendations,
            "components": result.components,
            "references": result.references,
            "inputs_used": inputs,
            "inputs_from_measurements": list(mapping_info.keys()) if mapping_info else [],
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _map_conditions_to_criteria(
        self,
        definition,
        conditions: list[str],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Map patient conditions to calculator criteria."""
        condition_keywords = {
            "diabetes": ["diabetes", "dm", "type 2 diabetes", "type 1 diabetes", "diabetic"],
            "hypertension": ["hypertension", "htn", "high blood pressure", "elevated bp"],
            "congestive_heart_failure": ["heart failure", "chf", "hf", "cardiomyopathy", "lvef reduced"],
            "stroke_tia_thromboembolism": ["stroke", "tia", "transient ischemic", "cva", "thromboembolism"],
            "vascular_disease": ["coronary artery disease", "cad", "mi", "myocardial infarction", "pad", "peripheral arterial", "aortic plaque"],
            "renal_disease": ["chronic kidney disease", "ckd", "renal failure", "esrd", "aki"],
            "liver_disease": ["cirrhosis", "liver disease", "hepatic", "hepatitis"],
            "confusion": ["delirium", "altered mental status", "confusion", "encephalopathy"],
            "malignancy": ["cancer", "malignancy", "carcinoma", "tumor", "neoplasm", "oncology"],
            "copd": ["copd", "chronic obstructive", "emphysema"],
            "immobility": ["immobil", "bedbound", "paralysis", "paresis"],
            "recent_surgery": ["surgery", "postoperative", "post-op"],
        }

        conditions_lower = [c.lower() for c in conditions]

        for criterion in definition.criteria:
            criterion_name = criterion.name.lower()
            keywords = condition_keywords.get(criterion_name, [criterion_name])

            for condition in conditions_lower:
                for keyword in keywords:
                    if keyword in condition:
                        inputs[criterion.name] = True
                        break

        return inputs

    def generate_calculator_context_for_llm(
        self,
        calculators_with_results: list[dict[str, Any]],
        max_length: int = 2000,
    ) -> str:
        """Generate LLM context string from calculator results.

        Args:
            calculators_with_results: List of calculator results
            max_length: Maximum context length

        Returns:
            Formatted context string for LLM reasoning
        """
        if not calculators_with_results:
            return ""

        context_parts = ["Clinical Calculator Results:"]

        for i, calc_result in enumerate(calculators_with_results, 1):
            calc_name = calc_result.get("calculator_name", "Unknown")
            score = calc_result.get("score", "N/A")
            unit = calc_result.get("score_unit", "")
            risk = calc_result.get("risk_level", "")
            interpretation = calc_result.get("interpretation", "")

            context_parts.append(
                f"\n[Calculator {i}] {calc_name}: {score} {unit}"
            )
            if risk:
                context_parts.append(f"  Risk Level: {risk}")
            if interpretation:
                context_parts.append(f"  Interpretation: {interpretation}")

            # Add key recommendations if available
            recommendations = calc_result.get("recommendations", [])
            if recommendations:
                context_parts.append(f"  Key Recommendation: {recommendations[0]}")

        result = "\n".join(context_parts)

        # Truncate if too long
        if len(result) > max_length:
            result = result[:max_length - 3] + "..."

        return result

    def run_applicable_calculators(
        self,
        conditions: list[str],
        measurements: list[dict[str, Any]],
        demographics: dict[str, Any] | None = None,
        clinical_question: str | None = None,
        min_relevance: float = 2.0,
        min_data_completeness: float = 0.5,
        max_calculators: int = 5,
    ) -> list[dict[str, Any]]:
        """Identify and run applicable calculators for a patient.

        This is the main entry point for clinical agents to get calculator
        results for clinical reasoning.

        Args:
            conditions: Patient conditions
            measurements: Patient measurements
            demographics: Patient demographics
            clinical_question: Clinical question for context
            min_relevance: Minimum relevance score to run
            min_data_completeness: Minimum data completeness to run
            max_calculators: Maximum calculators to run

        Returns:
            List of calculator results
        """
        # Identify applicable calculators
        suggestions = self.identify_applicable_calculators(
            conditions=conditions,
            measurements=measurements,
            clinical_question=clinical_question,
            demographics=demographics,
            limit=max_calculators * 2,  # Get more than needed for filtering
        )

        results = []

        for suggestion in suggestions:
            # Filter by relevance and data completeness
            if suggestion["relevance_score"] < min_relevance:
                continue
            if suggestion["data_completeness"] < min_data_completeness:
                continue

            try:
                result = self.calculate_with_patient_data(
                    calculator_id=suggestion["calculator_id"],
                    measurements=measurements,
                    demographics=demographics,
                    conditions=conditions,
                )
                result["relevance_score"] = suggestion["relevance_score"]
                result["selection_reasons"] = suggestion["reasons"]
                results.append(result)

                if len(results) >= max_calculators:
                    break

            except Exception as e:
                logger.warning(
                    f"Failed to run calculator {suggestion['calculator_id']}: {e}"
                )
                continue

        return results


# Singleton instance
_calculator_reasoning_service: CalculatorReasoningService | None = None


def get_calculator_reasoning_service() -> CalculatorReasoningService:
    """Get singleton CalculatorReasoningService instance."""
    global _calculator_reasoning_service
    if _calculator_reasoning_service is None:
        _calculator_reasoning_service = CalculatorReasoningService()
    return _calculator_reasoning_service
