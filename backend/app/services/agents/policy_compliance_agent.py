"""Policy Compliance Agent for Clinical Decision Support.

This agent is specialized in checking patient state against clinical
policies and guidelines, identifying compliance gaps, and recommending
policy-based actions.

Features:
- Queries PolicyKG for applicable rules
- Checks patient conditions against policy triggers
- Reports compliance status and gaps
- Recommends actions based on policy requirements
- Participates in TrustedMDT consensus with policy perspective

Based on research in Decision Knowledge Graphs for Clinical Practice Guidelines.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.multi_agent_orchestrator import (
    AgentContext,
    AgentRecommendation,
    AgentRole,
    AgentVote,
    BaseAgent,
    RecommendationType,
)

logger = logging.getLogger(__name__)


@dataclass
class PolicyMatch:
    """A policy that matches the patient's current state."""

    rule_id: str
    rule_name: str
    match_score: float
    matched_conditions: list[str] = field(default_factory=list)
    unmatched_conditions: list[str] = field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence_grade: str = ""
    source: str = ""


@dataclass
class ComplianceGap:
    """A compliance gap identified for the patient."""

    gap_id: str = field(default_factory=lambda: str(uuid4()))
    rule_id: str = ""
    rule_name: str = ""
    description: str = ""
    severity: str = "moderate"  # critical, high, moderate, low
    recommended_action: str = ""
    evidence_grade: str = ""
    due_date: datetime | None = None


class PolicyComplianceAgent(BaseAgent):
    """Agent specialized in clinical policy and guideline compliance.

    This agent:
    1. Matches patient state against applicable policies
    2. Identifies compliance gaps (missing screenings, treatments, etc.)
    3. Generates policy-based recommendations
    4. Votes on other recommendations from a policy compliance perspective
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.EVIDENCE,  # Uses EVIDENCE role for voting purposes
            name="Policy Compliance Specialist",
            description="Checks patient state against clinical policies and guidelines",
        )
        # In production, these would come from the PolicyKG
        self._sample_policies = self._load_sample_policies()

    def _load_sample_policies(self) -> list[dict[str, Any]]:
        """Load sample policies for demonstration.

        In production, this would query the PolicyKG database.
        """
        return [
            {
                "rule_id": "HYPERTENSION_001",
                "rule_name": "Hypertension Initial Treatment",
                "applies_to_conditions": ["hypertension", "high blood pressure"],
                "if_conditions": {
                    "has_condition": "hypertension",
                    "age": {"operator": ">=", "value": 18},
                },
                "then_actions": {
                    "recommend": "first-line antihypertensive therapy",
                    "options": ["ACE inhibitor", "ARB", "calcium channel blocker", "thiazide diuretic"],
                },
                "evidence_grade": "A",
                "recommendation_strength": "strong",
                "source": "JNC-8 Guidelines",
            },
            {
                "rule_id": "DIABETES_SCREENING_001",
                "rule_name": "Diabetes Screening for Hypertension",
                "applies_to_conditions": ["hypertension"],
                "if_conditions": {
                    "has_condition": "hypertension",
                },
                "then_actions": {
                    "recommend": "diabetes screening",
                    "tests": ["HbA1c", "fasting glucose"],
                    "frequency": "annually",
                },
                "evidence_grade": "B",
                "recommendation_strength": "strong",
                "source": "ADA Guidelines",
            },
            {
                "rule_id": "STATIN_THERAPY_001",
                "rule_name": "Statin Therapy for Diabetes",
                "applies_to_conditions": ["diabetes", "type 2 diabetes"],
                "if_conditions": {
                    "has_condition": "diabetes",
                    "age": {"operator": ">=", "value": 40},
                },
                "then_actions": {
                    "recommend": "moderate-intensity statin therapy",
                    "unless": ["statin allergy", "documented intolerance"],
                },
                "evidence_grade": "A",
                "recommendation_strength": "strong",
                "source": "ACC/AHA Guidelines",
            },
            {
                "rule_id": "RENAL_MONITORING_001",
                "rule_name": "Renal Function Monitoring",
                "applies_to_conditions": ["diabetes", "hypertension"],
                "applies_to_medications": ["ACE inhibitor", "ARB"],
                "if_conditions": {
                    "any_condition": ["diabetes", "hypertension"],
                    "any_medication": ["lisinopril", "losartan", "enalapril", "valsartan"],
                },
                "then_actions": {
                    "recommend": "annual renal function monitoring",
                    "tests": ["serum creatinine", "eGFR", "urine albumin-creatinine ratio"],
                },
                "evidence_grade": "B",
                "recommendation_strength": "moderate",
                "source": "KDIGO Guidelines",
            },
        ]

    async def analyze(self, context: AgentContext) -> list[AgentRecommendation]:
        """Analyze patient state against policies and generate compliance recommendations."""
        self.clear_reasoning()
        recommendations = []

        self.add_reasoning_step("Querying policy knowledge graph for applicable rules")

        # Get patient conditions and medications for matching
        patient_conditions = [
            c.get("name", "").lower() for c in context.conditions
        ]
        patient_medications = [
            m.get("name", "").lower() for m in context.medications
        ]
        patient_age = context.demographics.get("age", 0)

        self.add_reasoning_step(
            f"Patient has {len(patient_conditions)} conditions and {len(patient_medications)} medications"
        )

        # Match policies
        matched_policies = self._match_policies(
            patient_conditions, patient_medications, patient_age
        )

        self.add_reasoning_step(f"Found {len(matched_policies)} applicable policies")

        # Check compliance for each matched policy
        for policy_match in matched_policies:
            gaps = self._check_compliance(
                policy_match, context
            )

            if gaps:
                for gap in gaps:
                    self.add_reasoning_step(
                        f"Identified compliance gap: {gap.description}"
                    )

                    recommendations.append(
                        AgentRecommendation(
                            agent_role=self.role,
                            recommendation_type=RecommendationType.MONITORING,
                            content=f"Policy compliance gap: {gap.description}. "
                                    f"Recommended action: {gap.recommended_action}",
                            confidence=0.9,
                            evidence=[
                                f"Policy: {gap.rule_name}",
                                f"Evidence Grade: {gap.evidence_grade}",
                            ],
                            reasoning_chain=self.get_reasoning_chain(),
                            supporting_data={
                                "rule_id": gap.rule_id,
                                "severity": gap.severity,
                                "gap_type": "policy_compliance",
                            },
                        )
                    )

            # Also generate positive recommendations from fully matched policies
            if policy_match.match_score >= 0.8:
                for action in policy_match.recommended_actions:
                    action_desc = action.get("recommend", "")
                    if action_desc:
                        recommendations.append(
                            AgentRecommendation(
                                agent_role=self.role,
                                recommendation_type=RecommendationType.TREATMENT,
                                content=f"Guideline-based recommendation: {action_desc}",
                                confidence=0.85,
                                evidence=[
                                    f"Policy: {policy_match.rule_name}",
                                    f"Source: {policy_match.source}",
                                    f"Evidence Grade: {policy_match.evidence_grade}",
                                ],
                                reasoning_chain=self.get_reasoning_chain(),
                                supporting_data={
                                    "rule_id": policy_match.rule_id,
                                    "match_score": policy_match.match_score,
                                },
                            )
                        )

        # Add policy constraints to the context for other agents
        for policy_match in matched_policies:
            context.add_policy_constraint(
                rule_id=policy_match.rule_id,
                rule_name=policy_match.rule_name,
                applies_to=policy_match.matched_conditions,
                then_actions={"actions": policy_match.recommended_actions},
                evidence_grade=policy_match.evidence_grade,
                source=policy_match.source,
            )

        return recommendations

    def _match_policies(
        self,
        conditions: list[str],
        medications: list[str],
        age: int,
    ) -> list[PolicyMatch]:
        """Match policies against patient state."""
        matches = []

        for policy in self._sample_policies:
            applies_to_conditions = [
                c.lower() for c in policy.get("applies_to_conditions", [])
            ]
            applies_to_medications = [
                m.lower() for m in policy.get("applies_to_medications", [])
            ]

            # Check condition match
            matched_conditions = [
                c for c in conditions
                if any(pc in c or c in pc for pc in applies_to_conditions)
            ]

            # Check medication match if applicable
            matched_medications = []
            if applies_to_medications:
                matched_medications = [
                    m for m in medications
                    if any(pm in m or m in pm for pm in applies_to_medications)
                ]

            # Calculate match score
            if matched_conditions or matched_medications:
                total_required = len(applies_to_conditions) + (
                    len(applies_to_medications) if applies_to_medications else 0
                )
                total_matched = len(matched_conditions) + len(matched_medications)
                match_score = total_matched / total_required if total_required > 0 else 0

                # Check age constraints
                if_conditions = policy.get("if_conditions", {})
                age_constraint = if_conditions.get("age")
                if age_constraint:
                    operator = age_constraint.get("operator", ">=")
                    value = age_constraint.get("value", 0)
                    if operator == ">=" and age < value:
                        match_score *= 0.5  # Partial match if age doesn't meet

                if match_score > 0.3:  # Threshold for consideration
                    matches.append(
                        PolicyMatch(
                            rule_id=policy["rule_id"],
                            rule_name=policy["rule_name"],
                            match_score=match_score,
                            matched_conditions=matched_conditions,
                            unmatched_conditions=[
                                c for c in applies_to_conditions
                                if c not in matched_conditions
                            ],
                            recommended_actions=[policy.get("then_actions", {})],
                            evidence_grade=policy.get("evidence_grade", ""),
                            source=policy.get("source", ""),
                        )
                    )

        return sorted(matches, key=lambda m: m.match_score, reverse=True)

    def _check_compliance(
        self,
        policy_match: PolicyMatch,
        context: AgentContext,
    ) -> list[ComplianceGap]:
        """Check if patient is compliant with a matched policy."""
        gaps = []

        for action in policy_match.recommended_actions:
            recommended = action.get("recommend", "")
            tests = action.get("tests", [])
            options = action.get("options", [])

            # Check if recommended tests have been done
            if tests:
                patient_labs = [
                    lab.get("name", "").lower() for lab in context.lab_values
                ]
                missing_tests = [
                    test for test in tests
                    if not any(test.lower() in lab for lab in patient_labs)
                ]

                if missing_tests:
                    gaps.append(
                        ComplianceGap(
                            rule_id=policy_match.rule_id,
                            rule_name=policy_match.rule_name,
                            description=f"Missing recommended tests: {', '.join(missing_tests)}",
                            severity="moderate",
                            recommended_action=f"Order {', '.join(missing_tests)}",
                            evidence_grade=policy_match.evidence_grade,
                        )
                    )

            # Check if recommended medications are prescribed
            if options:
                patient_meds = [
                    med.get("name", "").lower() for med in context.medications
                ]
                has_recommended_med = any(
                    any(opt.lower() in med for med in patient_meds)
                    for opt in options
                )

                if not has_recommended_med:
                    gaps.append(
                        ComplianceGap(
                            rule_id=policy_match.rule_id,
                            rule_name=policy_match.rule_name,
                            description=f"Not on recommended therapy: {recommended}",
                            severity="high",
                            recommended_action=f"Consider starting one of: {', '.join(options)}",
                            evidence_grade=policy_match.evidence_grade,
                        )
                    )

        return gaps

    async def vote(
        self,
        recommendation: AgentRecommendation,
        context: AgentContext,
    ) -> AgentVote:
        """Vote on a recommendation from a policy compliance perspective."""
        concerns = []

        # Check if recommendation aligns with policies
        is_policy_supported = False
        supporting_policy = None

        for constraint in context.policy_constraints:
            # Check if recommendation content matches policy actions
            for action in constraint.then_actions.get("actions", []):
                recommend = action.get("recommend", "")
                if recommend.lower() in recommendation.content.lower():
                    is_policy_supported = True
                    supporting_policy = constraint.rule_name
                    break

        # Check for contraindications
        for constraint in context.policy_constraints:
            unless_conditions = constraint.then_actions.get("unless", [])
            for condition in unless_conditions:
                if condition.lower() in recommendation.content.lower():
                    concerns.append(
                        f"Policy {constraint.rule_id} notes this is contraindicated: {condition}"
                    )

        if is_policy_supported:
            return AgentVote(
                agent_role=self.role,
                agrees=True,
                confidence=0.9,
                concerns=[],
            )

        # If not explicitly supported but not contraindicated, moderate agreement
        if not concerns:
            return AgentVote(
                agent_role=self.role,
                agrees=True,
                confidence=0.6,
                concerns=["No explicit policy support found, but not contraindicated"],
            )

        # If contraindicated
        return AgentVote(
            agent_role=self.role,
            agrees=False,
            confidence=0.8,
            concerns=concerns,
        )

    def get_applicable_policies(self, context: AgentContext) -> list[dict[str, Any]]:
        """Get all policies that apply to the current patient context."""
        patient_conditions = [c.get("name", "").lower() for c in context.conditions]
        patient_medications = [m.get("name", "").lower() for m in context.medications]
        patient_age = context.demographics.get("age", 0)

        matches = self._match_policies(patient_conditions, patient_medications, patient_age)

        return [
            {
                "rule_id": m.rule_id,
                "rule_name": m.rule_name,
                "match_score": m.match_score,
                "matched_conditions": m.matched_conditions,
                "evidence_grade": m.evidence_grade,
                "source": m.source,
            }
            for m in matches
        ]
