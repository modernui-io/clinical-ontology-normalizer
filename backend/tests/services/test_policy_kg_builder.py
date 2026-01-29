"""Tests for PolicyKGBuilder service."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.policy_kg_builder import (
    ExtractedAction,
    ExtractedCondition,
    ExtractedRule,
    PolicyKGBuilder,
    get_policy_kg_builder,
)


class TestExtractedRule:
    """Tests for ExtractedRule dataclass."""

    def test_extracted_rule_creation(self):
        """Test creating an ExtractedRule with all fields."""
        rule = ExtractedRule(
            rule_id="TEST_001",
            name="Hypertension Management",
            description="Rule for managing hypertension",
            source_text="If patient has hypertension, then prescribe ACE inhibitor",
            conditions=[
                ExtractedCondition(
                    text="patient has hypertension",
                    condition_type="patient_has",
                    value="hypertension",
                )
            ],
            actions=[
                ExtractedAction(
                    text="prescribe ACE inhibitor",
                    action_type="prescribe",
                    target="lisinopril",
                    dosage="10mg daily",
                )
            ],
            exceptions=[
                ExtractedCondition(
                    text="patient has angioedema history",
                    condition_type="patient_has",
                    value="angioedema",
                )
            ],
            evidence_grade="A",
            recommendation_strength="Strong",
            applies_to_conditions=["hypertension"],
            applies_to_medications=["lisinopril", "enalapril"],
            extraction_confidence=0.95,
        )

        assert rule.rule_id == "TEST_001"
        assert rule.name == "Hypertension Management"
        assert len(rule.conditions) == 1
        assert len(rule.actions) == 1
        assert len(rule.exceptions) == 1
        assert rule.evidence_grade == "A"
        assert rule.extraction_confidence == 0.95

    def test_extracted_condition_with_threshold(self):
        """Test ExtractedCondition with numeric threshold."""
        condition = ExtractedCondition(
            text="HbA1c greater than 7%",
            condition_type="lab_value",
            value="HbA1c",
            operator=">",
            threshold=7.0,
            threshold_unit="%",
        )

        assert condition.condition_type == "lab_value"
        assert condition.operator == ">"
        assert condition.threshold == 7.0
        assert condition.threshold_unit == "%"


class TestPolicyKGBuilder:
    """Tests for PolicyKGBuilder service."""

    def test_singleton(self):
        """Test that get_policy_kg_builder returns singleton."""
        builder1 = get_policy_kg_builder()
        builder2 = get_policy_kg_builder()
        assert builder1 is builder2

    def test_heuristic_extraction_if_then(self):
        """Test heuristic rule extraction with if-then pattern."""
        builder = PolicyKGBuilder()
        text = """
        If a patient has diabetes mellitus type 2, then initiate metformin therapy.
        If patient has chronic kidney disease, then reduce metformin dosage.
        """

        rules = builder._extract_rules_heuristic(text)

        assert len(rules) >= 2
        assert any("diabetes" in r.source_text.lower() for r in rules)
        assert any("metformin" in r.source_text.lower() for r in rules)

    def test_heuristic_extraction_should_pattern(self):
        """Test heuristic rule extraction with should pattern."""
        builder = PolicyKGBuilder()
        text = """
        Patients with hypertension should receive blood pressure monitoring every 3 months.
        Patients who have diabetes should have annual eye exams.
        """

        rules = builder._extract_rules_heuristic(text)

        assert len(rules) >= 1
        # Check that conditions and actions are extracted
        for rule in rules:
            assert len(rule.actions) > 0

    def test_heuristic_extraction_recommend_pattern(self):
        """Test heuristic rule extraction with recommend pattern."""
        builder = PolicyKGBuilder()
        text = """
        Recommend aspirin therapy for patients with cardiovascular disease.
        Consider statin therapy for patients with elevated LDL cholesterol.
        """

        rules = builder._extract_rules_heuristic(text)

        assert len(rules) >= 1

    def test_parse_extracted_rules(self):
        """Test parsing LLM-extracted rule data."""
        builder = PolicyKGBuilder()

        rules_data = [
            {
                "name": "Diabetes Screening",
                "description": "Screen for diabetes in high-risk patients",
                "conditions": [
                    {"text": "BMI > 25", "type": "lab_value", "operator": ">", "threshold": 25},
                    {"text": "age > 45", "type": "age", "operator": ">", "threshold": 45},
                ],
                "actions": [
                    {"text": "order HbA1c test", "type": "order_test", "target": "HbA1c"},
                ],
                "exceptions": [],
                "evidence_grade": "B",
                "recommendation_strength": "Moderate",
                "applies_to_conditions": ["obesity", "prediabetes"],
                "applies_to_medications": [],
                "applies_to_measurements": ["BMI", "HbA1c"],
                "confidence": 0.9,
            }
        ]

        rules = builder._parse_extracted_rules(rules_data, "source text")

        assert len(rules) == 1
        rule = rules[0]
        assert rule.name == "Diabetes Screening"
        assert len(rule.conditions) == 2
        assert len(rule.actions) == 1
        assert rule.conditions[0].threshold == 25
        assert rule.evidence_grade == "B"
        assert "obesity" in rule.applies_to_conditions

    def test_parse_extracted_rules_malformed(self):
        """Test parsing handles malformed data gracefully."""
        builder = PolicyKGBuilder()

        rules_data = [
            {
                "name": "Valid Rule",
                "description": "A valid rule",
                "conditions": [],
                "actions": [],
            },
            {
                # Missing required fields
                "invalid": True,
            },
        ]

        rules = builder._parse_extracted_rules(rules_data, "source text")

        # Should parse the valid rule, skip the invalid one
        assert len(rules) >= 1


class TestPolicyKGBuilderIntegration:
    """Integration tests for PolicyKGBuilder with database."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def sample_policy(self):
        """Create a sample policy for testing."""
        from app.models.policy import Policy, PolicySection, PolicyStatus

        policy = MagicMock(spec=Policy)
        policy.id = str(uuid4())
        policy.name = "Test Policy"
        policy.status = PolicyStatus.ACTIVE.value

        section = MagicMock(spec=PolicySection)
        section.id = str(uuid4())
        section.policy_id = policy.id
        section.content_text = """
        Section 3.1: Hypertension Management

        If a patient has hypertension and is over 60 years of age, then initiate
        treatment with an ACE inhibitor as first-line therapy. (Evidence Grade: A)

        Unless the patient has a history of angioedema or is pregnant,
        lisinopril 10mg daily is recommended as the starting dose.

        Recommendation strength: Strong
        """

        policy.sections = [section]
        return policy, section

    @pytest.mark.asyncio
    async def test_build_policy_kg_heuristic(self, mock_session, sample_policy):
        """Test building PolicyKG without LLM (heuristic only)."""
        policy, section = sample_policy

        # Mock the execute to return policy and sections
        mock_policy_result = MagicMock()
        mock_policy_result.scalar_one_or_none.return_value = policy

        mock_sections_result = MagicMock()
        mock_sections_result.scalars.return_value.all.return_value = [section]

        mock_session.execute.side_effect = [mock_policy_result, mock_sections_result]

        builder = PolicyKGBuilder()

        # Patch embedding service to avoid actual embeddings
        with patch("app.services.embedding_service.get_embedding_service") as mock_embed:
            mock_embed_svc = MagicMock()
            mock_embed_svc.encode.return_value = [0.1] * 384
            mock_embed_svc.encode_batch.return_value = [[0.1] * 384]
            mock_embed.return_value = mock_embed_svc

            result = await builder.build_policy_kg(
                mock_session,
                policy.id,
                use_llm=False,  # Use heuristic extraction
            )

        # Should create nodes, edges, and rules
        assert "nodes" in result
        assert "edges" in result
        assert "rules" in result
        # With heuristic extraction we should get at least some results
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_search_policy_rules(self, mock_session):
        """Test searching policy rules."""
        from app.models.policy_kg import PolicyRule

        # Create mock rules
        rule1 = MagicMock(spec=PolicyRule)
        rule1.rule_id = "RULE_001"
        rule1.name = "Hypertension Treatment"
        rule1.embedding = [0.1] * 384
        rule1.applies_to_conditions = ["hypertension"]

        rule2 = MagicMock(spec=PolicyRule)
        rule2.rule_id = "RULE_002"
        rule2.name = "Diabetes Management"
        rule2.embedding = [0.2] * 384
        rule2.applies_to_conditions = ["diabetes"]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule1, rule2]
        mock_session.execute.return_value = mock_result

        builder = PolicyKGBuilder()

        with patch("app.services.embedding_service.get_embedding_service") as mock_embed:
            mock_embed_svc = MagicMock()
            mock_embed_svc.encode.return_value = [0.1] * 384
            mock_embed_svc.cosine_similarity.side_effect = [0.9, 0.5]  # rule1 more similar
            mock_embed.return_value = mock_embed_svc

            results = await builder.search_policy_rules(
                mock_session,
                query="treatment for high blood pressure",
                patient_conditions=["hypertension"],
                top_k=2,
            )

        assert len(results) == 2
        # rule1 should be first due to higher similarity + condition boost
        assert results[0].rule_id == "RULE_001"


class TestHeuristicPatterns:
    """Test different heuristic patterns for rule extraction."""

    @pytest.fixture
    def builder(self):
        return PolicyKGBuilder()

    def test_pattern_if_then_basic(self, builder):
        """Test basic if-then pattern."""
        text = "If patient has fever, then administer antipyretics."
        rules = builder._extract_rules_heuristic(text)
        assert len(rules) >= 1

    def test_pattern_when_clause(self, builder):
        """Test when clause pattern."""
        text = "When blood glucose exceeds 180 mg/dL, administer insulin."
        rules = builder._extract_rules_heuristic(text)
        assert len(rules) >= 1

    def test_pattern_for_patients_with(self, builder):
        """Test 'for patients with' pattern."""
        text = "For patients with heart failure, limit sodium intake to 2g/day."
        rules = builder._extract_rules_heuristic(text)
        assert len(rules) >= 1

    def test_pattern_is_indicated(self, builder):
        """Test 'is indicated' pattern."""
        text = "Metformin is indicated for type 2 diabetes in adults."
        rules = builder._extract_rules_heuristic(text)
        assert len(rules) >= 1

    def test_complex_policy_text(self, builder):
        """Test extraction from complex policy text."""
        text = """
        4.2.1 Blood Pressure Management Guidelines

        Initial Assessment:
        If systolic blood pressure is greater than 140 mmHg, then classify as hypertensive.

        Treatment Initiation:
        For patients with confirmed hypertension who have no contraindications,
        initiate therapy with thiazide diuretic or ACE inhibitor.

        Special Populations:
        Patients with diabetes should receive ACE inhibitor as first-line therapy.
        Unless the patient has chronic kidney disease with eGFR < 30,
        continue ACE inhibitor therapy.

        Monitoring:
        Recommend blood pressure monitoring every 2 weeks until stable.
        Consider home blood pressure monitoring for improved compliance.

        Evidence Grade: A | Recommendation: Strong
        """

        rules = builder._extract_rules_heuristic(text)

        # Should extract multiple rules
        assert len(rules) >= 3

        # Check that various patterns were captured
        rule_texts = [r.source_text.lower() for r in rules]
        assert any("blood pressure" in t or "hypertensive" in t for t in rule_texts)
