"""Knowledge Graph Integration for Clinical Calculators.

This module provides services to:
1. Fetch patient clinical data from the Knowledge Graph
2. Map KG measurements to calculator input parameters
3. Execute calculators with auto-populated patient data
4. Support clinical agents in reasoning with calculators
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from app.services.calculator_definitions import (
    CALCULATOR_DEFINITIONS,
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


class CalculatorKGIntegration:
    """Service for integrating calculators with the Knowledge Graph."""

    def __init__(self, neo4j_driver=None):
        """Initialize with Neo4j driver.

        Args:
            neo4j_driver: Neo4j driver instance (optional, fetched from settings if None)
        """
        self._driver = neo4j_driver

    @property
    def driver(self):
        """Get Neo4j driver, initializing if needed."""
        if self._driver is None:
            try:
                from app.core.config import settings
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
            except Exception as e:
                logger.warning(f"Could not connect to Neo4j: {e}")
                return None
        return self._driver

    def get_patient_measurements(
        self,
        patient_id: str,
        measurement_labels: list[str] | None = None,
        since_days: int = 30,
    ) -> list[dict[str, Any]]:
        """Fetch patient measurements from the Knowledge Graph.

        Args:
            patient_id: Patient identifier
            measurement_labels: Optional list of specific measurements to fetch
            since_days: Only fetch measurements from the last N days

        Returns:
            List of measurement dicts with 'label', 'value', 'unit', 'date' keys
        """
        if self.driver is None:
            logger.warning("Neo4j not available, returning empty measurements")
            return []

        since_date = datetime.utcnow() - timedelta(days=since_days)

        # Build Cypher query
        label_filter = ""
        if measurement_labels:
            labels_lower = [l.lower() for l in measurement_labels]
            label_filter = "AND toLower(cf.label) IN $labels"

        query = f"""
        MATCH (p:Patient {{patient_id: $patient_id}})-[r]->(cf:ClinicalFact)
        WHERE cf.semantic_group IN ['Measurement', 'Lab', 'Vital', 'Observation']
          AND (cf.effective_date IS NULL OR cf.effective_date >= $since_date)
          {label_filter}
        RETURN cf.label AS label,
               cf.value AS value,
               cf.unit AS unit,
               cf.effective_date AS date,
               cf.semantic_group AS category
        ORDER BY cf.effective_date DESC
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    patient_id=patient_id,
                    since_date=since_date.isoformat(),
                    labels=measurement_labels if measurement_labels else [],
                )
                measurements = []
                for record in result:
                    measurements.append({
                        "label": record["label"],
                        "value": record["value"],
                        "unit": record["unit"],
                        "date": record["date"],
                        "category": record["category"],
                    })
                return measurements
        except Exception as e:
            logger.error(f"Error fetching patient measurements: {e}")
            return []

    def get_patient_demographics(self, patient_id: str) -> dict[str, Any]:
        """Fetch patient demographics from the Knowledge Graph.

        Args:
            patient_id: Patient identifier

        Returns:
            Dict with 'age', 'sex', 'race' and other demographic data
        """
        if self.driver is None:
            return {}

        query = """
        MATCH (p:Patient {patient_id: $patient_id})
        RETURN p.birth_date AS birth_date,
               p.sex AS sex,
               p.gender AS gender,
               p.race AS race,
               p.ethnicity AS ethnicity
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, patient_id=patient_id)
                record = result.single()
                if record:
                    demographics = dict(record)
                    # Calculate age if birth_date available
                    if demographics.get("birth_date"):
                        try:
                            birth_date = datetime.fromisoformat(
                                str(demographics["birth_date"]).replace("Z", "+00:00")
                            )
                            today = datetime.utcnow()
                            age = (today - birth_date).days // 365
                            demographics["age"] = age
                        except Exception:
                            pass
                    # Normalize sex
                    sex = demographics.get("sex") or demographics.get("gender")
                    if sex:
                        demographics["female"] = 1 if sex.lower() in ["f", "female"] else 0
                    return demographics
                return {}
        except Exception as e:
            logger.error(f"Error fetching patient demographics: {e}")
            return {}

    def get_patient_conditions(self, patient_id: str) -> list[dict[str, Any]]:
        """Fetch patient conditions/diagnoses from the Knowledge Graph.

        Args:
            patient_id: Patient identifier

        Returns:
            List of condition dicts with 'name', 'code', 'date' keys
        """
        if self.driver is None:
            return []

        query = """
        MATCH (p:Patient {patient_id: $patient_id})-[:HAS_CONDITION]->(c)
        RETURN c.label AS name,
               c.concept_code AS code,
               c.vocabulary_id AS vocabulary,
               c.effective_date AS date,
               c.status AS status
        ORDER BY c.effective_date DESC
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, patient_id=patient_id)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Error fetching patient conditions: {e}")
            return []

    def build_calculator_inputs(
        self,
        calculator_id: str,
        patient_id: str,
        additional_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build calculator inputs from patient KG data.

        Args:
            calculator_id: Calculator to build inputs for
            patient_id: Patient to fetch data for
            additional_inputs: Additional/override inputs to merge

        Returns:
            Dict of calculator input parameters
        """
        # Get measurements needed for this calculator
        needed_measurements = get_measurements_for_calculator(calculator_id)

        # Fetch patient measurements
        measurements = self.get_patient_measurements(
            patient_id,
            measurement_labels=needed_measurements if needed_measurements else None,
        )

        # Build inputs from measurements
        inputs, _ = build_calculator_inputs_from_measurements(
            calculator_id, measurements
        )

        # Fetch demographics and add relevant fields
        demographics = self.get_patient_demographics(patient_id)
        if demographics.get("age"):
            inputs["age"] = demographics["age"]
        if "female" in demographics:
            inputs["female"] = demographics["female"]

        # Fetch conditions for criteria-based calculators
        conditions = self.get_patient_conditions(patient_id)
        inputs = self._map_conditions_to_criteria(calculator_id, conditions, inputs)

        # Merge additional inputs (overrides)
        if additional_inputs:
            inputs.update(additional_inputs)

        return inputs

    def _map_conditions_to_criteria(
        self,
        calculator_id: str,
        conditions: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Map patient conditions to calculator criteria.

        This maps diagnoses to boolean criteria like 'diabetes', 'hypertension', etc.
        Now enhanced with OMOP hierarchy for semantic matching.
        """
        definition = get_calculator_definition(calculator_id)
        if definition is None or definition.calc_type != CalculatorType.CRITERIA:
            return inputs

        # Build a mapping of condition keywords to criteria names
        condition_keywords = {
            "diabetes": ["diabetes", "dm", "type 2 diabetes", "type 1 diabetes"],
            "hypertension": ["hypertension", "htn", "high blood pressure"],
            "congestive_heart_failure": ["heart failure", "chf", "hf", "cardiomyopathy"],
            "stroke_tia_thromboembolism": ["stroke", "tia", "transient ischemic", "cva", "thromboembolism"],
            "vascular_disease": ["coronary artery disease", "cad", "mi", "myocardial infarction", "pad", "peripheral arterial"],
            "renal_disease": ["chronic kidney disease", "ckd", "renal failure", "esrd"],
            "liver_disease": ["cirrhosis", "liver disease", "hepatic"],
            "confusion": ["delirium", "altered mental status", "confusion", "encephalopathy"],
            "malignancy": ["cancer", "malignancy", "carcinoma", "tumor", "neoplasm"],
            "copd": ["copd", "chronic obstructive", "emphysema"],
        }

        # Get condition names in lowercase
        condition_names = [c.get("name", "").lower() for c in conditions if c.get("name")]

        # Expand condition names using OMOP hierarchy
        expanded_condition_names = set(condition_names)
        try:
            from app.services.omop_hierarchy_service import get_omop_hierarchy_service

            hierarchy = get_omop_hierarchy_service()
            if hierarchy.is_available:
                for cond_name in condition_names:
                    ancestors = hierarchy.expand_condition_names(cond_name, max_distance=3)
                    expanded_condition_names.update(ancestors)
        except Exception as e:
            logger.warning(f"Hierarchy expansion failed in criteria mapping: {e}")

        # Check each criterion against conditions (including expanded ancestors)
        for criterion in definition.criteria:
            criterion_name = criterion.name.lower()
            keywords = condition_keywords.get(criterion_name, [criterion_name])

            for condition_name in expanded_condition_names:
                for keyword in keywords:
                    if keyword in condition_name:
                        inputs[criterion.name] = True
                        break

        return inputs

    def calculate_for_patient(
        self,
        calculator_id: str,
        patient_id: str,
        additional_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a calculator for a patient using KG data.

        Args:
            calculator_id: Calculator to execute
            patient_id: Patient to calculate for
            additional_inputs: Additional/override inputs

        Returns:
            Dict with calculation result and metadata
        """
        definition = get_calculator_definition(calculator_id)
        if definition is None:
            raise ValueError(f"Calculator not found: {calculator_id}")

        # Build inputs from KG
        inputs = self.build_calculator_inputs(
            calculator_id, patient_id, additional_inputs
        )

        # Track which inputs came from KG vs provided
        kg_inputs = {k: v for k, v in inputs.items() if k not in (additional_inputs or {})}
        provided_inputs = additional_inputs or {}

        # Execute calculation
        age = inputs.pop("age", None)

        if definition.calc_type == CalculatorType.CRITERIA:
            result = calculate_point_based_score(definition, inputs, age)
        elif definition.calc_type == CalculatorType.EQUATION:
            result = calculate_equation_score(definition, inputs)
        else:
            raise ValueError(f"Unsupported calculator type: {definition.calc_type}")

        return {
            "calculator_id": calculator_id,
            "calculator_name": result.calculator_name,
            "patient_id": patient_id,
            "score": result.score,
            "score_unit": result.score_unit,
            "risk_level": result.risk_level.value,
            "interpretation": result.interpretation,
            "recommendations": result.recommendations,
            "components": result.components,
            "references": result.references,
            "inputs_from_kg": kg_inputs,
            "inputs_provided": provided_inputs,
            "missing_inputs": self._get_missing_inputs(definition, inputs),
        }

    def _get_missing_inputs(
        self,
        definition,
        inputs: dict[str, Any],
    ) -> list[str]:
        """Identify missing required inputs."""
        missing = []

        if definition.calc_type == CalculatorType.EQUATION and definition.formula:
            for param in definition.formula.parameters:
                if param.required and param.name not in inputs:
                    missing.append(param.display_name)
        elif definition.calc_type == CalculatorType.CRITERIA:
            # For criteria calculators, all inputs are typically optional
            pass

        return missing

    def suggest_calculators_for_patient(
        self,
        patient_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Suggest relevant calculators based on patient's conditions and data.

        Args:
            patient_id: Patient identifier
            limit: Maximum number of suggestions

        Returns:
            List of calculator suggestions with relevance scores
        """
        conditions = self.get_patient_conditions(patient_id)
        measurements = self.get_patient_measurements(patient_id)
        demographics = self.get_patient_demographics(patient_id)

        suggestions = []

        for calc_id, definition in CALCULATOR_DEFINITIONS.items():
            relevance = 0
            reasons = []

            # Check if patient has relevant conditions for category
            category = definition.category.value.lower()
            for condition in conditions:
                name = (condition.get("name") or "").lower()
                if category in name or any(
                    cat_word in name
                    for cat_word in category.split("_")
                ):
                    relevance += 2
                    reasons.append(f"Has {condition.get('name')}")
                    break

            # Check if patient has measurements for this calculator
            needed = get_measurements_for_calculator(calc_id)
            available = [m["label"].lower() for m in measurements]
            matched = sum(1 for n in needed if any(n.lower() in a for a in available))
            if matched > 0:
                relevance += matched
                reasons.append(f"{matched}/{len(needed)} measurements available")

            # Age-appropriate calculators
            age = demographics.get("age", 0)
            if age >= 65 and "65" in definition.name:
                relevance += 1
                reasons.append("Age-appropriate")

            if relevance > 0:
                suggestions.append({
                    "calculator_id": calc_id,
                    "calculator_name": definition.name,
                    "category": definition.category.value,
                    "relevance_score": relevance,
                    "reasons": reasons,
                    "description": definition.description,
                })

        # Sort by relevance and return top N
        suggestions.sort(key=lambda x: x["relevance_score"], reverse=True)
        return suggestions[:limit]

    def get_calculator_context_for_agent(
        self,
        calculator_id: str,
        patient_id: str | None = None,
    ) -> dict[str, Any]:
        """Get calculator context for clinical reasoning agents.

        This provides all the information an agent needs to:
        1. Understand what the calculator does
        2. Know what inputs are needed
        3. See what patient data is available (if patient_id provided)
        4. Execute the calculation

        Args:
            calculator_id: Calculator identifier
            patient_id: Optional patient to get data for

        Returns:
            Dict with full calculator context
        """
        definition = get_calculator_definition(calculator_id)
        if definition is None:
            raise ValueError(f"Calculator not found: {calculator_id}")

        context = {
            "calculator": {
                "id": definition.id,
                "name": definition.name,
                "short_name": definition.short_name,
                "category": definition.category.value,
                "calc_type": definition.calc_type.value,
                "description": definition.description,
                "score_unit": definition.score_unit,
            },
            "required_inputs": [],
            "interpretations": [
                {
                    "score_range": f"{i.min_score} - {i.max_score or '∞'}",
                    "risk_level": i.risk_level.value,
                    "interpretation": i.interpretation,
                }
                for i in definition.interpretations
            ],
            "references": definition.references,
            "notes": definition.notes,
        }

        # Add input requirements
        if definition.calc_type == CalculatorType.EQUATION and definition.formula:
            context["required_inputs"] = [
                {
                    "name": p.name,
                    "display_name": p.display_name,
                    "unit": p.unit,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "required": p.required,
                }
                for p in definition.formula.parameters
            ]
            context["formula"] = definition.formula.formula_text
        elif definition.calc_type == CalculatorType.CRITERIA:
            context["criteria"] = [
                {
                    "name": c.name,
                    "display_name": c.display_name,
                    "points": c.points,
                    "description": c.description,
                }
                for c in definition.criteria
            ]

        # Add patient-specific data if patient_id provided
        if patient_id:
            inputs = self.build_calculator_inputs(calculator_id, patient_id)
            context["patient_data"] = {
                "patient_id": patient_id,
                "available_inputs": inputs,
                "missing_inputs": self._get_missing_inputs(definition, inputs),
            }

        return context


# Singleton instance
_calculator_kg_integration: CalculatorKGIntegration | None = None


def get_calculator_kg_integration() -> CalculatorKGIntegration:
    """Get singleton CalculatorKGIntegration instance."""
    global _calculator_kg_integration
    if _calculator_kg_integration is None:
        _calculator_kg_integration = CalculatorKGIntegration()
    return _calculator_kg_integration
