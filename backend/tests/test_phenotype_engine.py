"""Tests for the Computable Phenotype Engine.

Tests cover:
- Criterion evaluation logic
- Value-based filtering
- Temporal filtering
- Phenotype status determination
- Care gap identification
- Built-in phenotype definitions
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.phenotype_engine import (
    CareGap,
    CriterionLogic,
    CriterionResult,
    PhenotypeCriterion,
    PhenotypeDefinition,
    PhenotypeEngine,
    PhenotypeResult,
    PhenotypeStatus,
    ValueOperator,
    HFREF_PHENOTYPE,
    T2DM_PHENOTYPE,
    CKD_3PLUS_PHENOTYPE,
)
from app.schemas.knowledge_graph import NodeType


class TestValueOperators:
    """Tests for value-based criterion evaluation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.engine = PhenotypeEngine(self.mock_session)

    def test_value_eq(self) -> None:
        """Test equal operator."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.EQ,
            value_threshold=50.0,
        )
        assert self.engine._check_value(50.0, criterion) is True
        assert self.engine._check_value(49.0, criterion) is False

    def test_value_lt(self) -> None:
        """Test less than operator."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.LT,
            value_threshold=60.0,
        )
        assert self.engine._check_value(59.0, criterion) is True
        assert self.engine._check_value(60.0, criterion) is False
        assert self.engine._check_value(61.0, criterion) is False

    def test_value_le(self) -> None:
        """Test less than or equal operator."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.LE,
            value_threshold=40.0,
        )
        assert self.engine._check_value(40.0, criterion) is True
        assert self.engine._check_value(39.0, criterion) is True
        assert self.engine._check_value(41.0, criterion) is False

    def test_value_gt(self) -> None:
        """Test greater than operator."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.GT,
            value_threshold=7.0,
        )
        assert self.engine._check_value(8.0, criterion) is True
        assert self.engine._check_value(7.0, criterion) is False
        assert self.engine._check_value(6.0, criterion) is False

    def test_value_ge(self) -> None:
        """Test greater than or equal operator."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.GE,
            value_threshold=50.0,
        )
        assert self.engine._check_value(50.0, criterion) is True
        assert self.engine._check_value(51.0, criterion) is True
        assert self.engine._check_value(49.0, criterion) is False

    def test_value_between(self) -> None:
        """Test between operator."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.BETWEEN,
            value_threshold=[30.0, 60.0],
        )
        assert self.engine._check_value(45.0, criterion) is True
        assert self.engine._check_value(30.0, criterion) is True
        assert self.engine._check_value(60.0, criterion) is True
        assert self.engine._check_value(29.0, criterion) is False
        assert self.engine._check_value(61.0, criterion) is False

    def test_value_in(self) -> None:
        """Test in operator."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.IN,
            value_threshold=[1.0, 2.0, 3.0],
        )
        assert self.engine._check_value(2.0, criterion) is True
        assert self.engine._check_value(4.0, criterion) is False

    def test_value_none(self) -> None:
        """Test handling of None values."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.LT,
            value_threshold=60.0,
        )
        assert self.engine._check_value(None, criterion) is False

    def test_value_string_conversion(self) -> None:
        """Test handling of string values that can be converted."""
        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            value_field="value",
            value_operator=ValueOperator.LT,
            value_threshold=60.0,
        )
        assert self.engine._check_value("55.5", criterion) is True
        assert self.engine._check_value("invalid", criterion) is False


class TestStatusDetermination:
    """Tests for phenotype status determination logic."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.engine = PhenotypeEngine(self.mock_session)

    def _make_criterion_result(self, met: bool, name: str = "Test") -> CriterionResult:
        """Helper to create criterion results."""
        criterion = PhenotypeCriterion(name=name, concept_codes=[123])
        return CriterionResult(criterion=criterion, met=met)

    def test_all_inclusion_met_and_logic(self) -> None:
        """Test PRESENT status when all inclusion criteria met (AND logic)."""
        inclusion_results = [
            self._make_criterion_result(True, "Criterion 1"),
            self._make_criterion_result(True, "Criterion 2"),
        ]
        exclusion_results: list[CriterionResult] = []

        status, confidence = self.engine._determine_status(
            inclusion_results, exclusion_results, CriterionLogic.AND
        )

        assert status == PhenotypeStatus.PRESENT
        assert confidence >= 0.90

    def test_some_inclusion_met_and_logic(self) -> None:
        """Test POSSIBLE status when some inclusion criteria met (AND logic)."""
        inclusion_results = [
            self._make_criterion_result(True, "Criterion 1"),
            self._make_criterion_result(False, "Criterion 2"),
        ]
        exclusion_results: list[CriterionResult] = []

        status, confidence = self.engine._determine_status(
            inclusion_results, exclusion_results, CriterionLogic.AND
        )

        assert status == PhenotypeStatus.POSSIBLE

    def test_no_inclusion_met_and_logic(self) -> None:
        """Test ABSENT status when no inclusion criteria met (AND logic)."""
        inclusion_results = [
            self._make_criterion_result(False, "Criterion 1"),
            self._make_criterion_result(False, "Criterion 2"),
        ]
        exclusion_results: list[CriterionResult] = []

        status, confidence = self.engine._determine_status(
            inclusion_results, exclusion_results, CriterionLogic.AND
        )

        assert status == PhenotypeStatus.ABSENT

    def test_any_inclusion_met_or_logic(self) -> None:
        """Test PRESENT status when any inclusion criterion met (OR logic)."""
        inclusion_results = [
            self._make_criterion_result(True, "Criterion 1"),
            self._make_criterion_result(False, "Criterion 2"),
        ]
        exclusion_results: list[CriterionResult] = []

        status, confidence = self.engine._determine_status(
            inclusion_results, exclusion_results, CriterionLogic.OR
        )

        assert status == PhenotypeStatus.PRESENT
        assert confidence >= 0.85

    def test_exclusion_criteria_met(self) -> None:
        """Test ABSENT status when exclusion criteria met."""
        inclusion_results = [
            self._make_criterion_result(True, "Criterion 1"),
        ]
        exclusion_results = [
            self._make_criterion_result(True, "Exclusion 1"),
        ]

        status, confidence = self.engine._determine_status(
            inclusion_results, exclusion_results, CriterionLogic.AND
        )

        assert status == PhenotypeStatus.ABSENT
        assert confidence >= 0.90

    def test_no_inclusion_criteria(self) -> None:
        """Test INSUFFICIENT_DATA status when no inclusion criteria."""
        status, confidence = self.engine._determine_status([], [], CriterionLogic.AND)

        assert status == PhenotypeStatus.INSUFFICIENT_DATA
        assert confidence == 0.0


class TestBuiltInPhenotypes:
    """Tests for built-in phenotype definitions."""

    def test_hfref_phenotype_definition(self) -> None:
        """Test HFrEF phenotype definition structure."""
        assert HFREF_PHENOTYPE.id == "hfref"
        assert len(HFREF_PHENOTYPE.inclusion_criteria) >= 2
        assert len(HFREF_PHENOTYPE.exclusion_criteria) >= 1
        assert len(HFREF_PHENOTYPE.care_gap_criteria) >= 2

        # Check HF diagnosis criterion
        hf_criterion = HFREF_PHENOTYPE.inclusion_criteria[0]
        assert "heart failure" in hf_criterion.name.lower()
        assert 316139 in hf_criterion.concept_codes  # Heart failure OMOP ID

        # Check LVEF criterion
        lvef_criterion = HFREF_PHENOTYPE.inclusion_criteria[1]
        assert lvef_criterion.value_operator == ValueOperator.LE
        assert lvef_criterion.value_threshold == 40.0

    def test_t2dm_phenotype_definition(self) -> None:
        """Test T2DM phenotype definition structure."""
        assert T2DM_PHENOTYPE.id == "t2dm"
        assert T2DM_PHENOTYPE.inclusion_logic == CriterionLogic.OR
        assert len(T2DM_PHENOTYPE.exclusion_criteria) >= 1

        # Check T1DM exclusion
        t1dm_exclusion = T2DM_PHENOTYPE.exclusion_criteria[0]
        assert "type 1" in t1dm_exclusion.name.lower()

    def test_ckd_phenotype_definition(self) -> None:
        """Test CKD Stage 3+ phenotype definition structure."""
        assert CKD_3PLUS_PHENOTYPE.id == "ckd_3plus"
        assert CKD_3PLUS_PHENOTYPE.inclusion_logic == CriterionLogic.OR

        # Check eGFR criterion
        egfr_criterion = next(
            (c for c in CKD_3PLUS_PHENOTYPE.inclusion_criteria if "egfr" in c.name.lower()),
            None,
        )
        assert egfr_criterion is not None
        assert egfr_criterion.value_operator == ValueOperator.LT
        assert egfr_criterion.value_threshold == 60.0
        assert egfr_criterion.min_occurrences == 2  # Two readings required


class TestPhenotypeEngine:
    """Tests for PhenotypeEngine class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.engine = PhenotypeEngine(self.mock_session)

    def test_register_phenotype(self) -> None:
        """Test registering a custom phenotype."""
        custom_phenotype = PhenotypeDefinition(
            id="custom_test",
            name="Custom Test Phenotype",
            description="A test phenotype",
            inclusion_criteria=[
                PhenotypeCriterion(
                    name="Test Criterion",
                    concept_codes=[999999],
                    description="Test",
                ),
            ],
        )

        self.engine.register_phenotype(custom_phenotype)

        assert "custom_test" in [p["id"] for p in self.engine.list_phenotypes()]
        assert self.engine.get_phenotype("custom_test") is not None

    def test_list_phenotypes(self) -> None:
        """Test listing phenotypes includes built-ins."""
        phenotypes = self.engine.list_phenotypes()

        assert len(phenotypes) >= 3  # At least the 3 built-in phenotypes
        phenotype_ids = [p["id"] for p in phenotypes]
        assert "hfref" in phenotype_ids
        assert "t2dm" in phenotype_ids
        assert "ckd_3plus" in phenotype_ids

    def test_get_phenotype_not_found(self) -> None:
        """Test getting non-existent phenotype returns None."""
        result = self.engine.get_phenotype("nonexistent_phenotype")
        assert result is None

    def test_evaluate_unknown_phenotype(self) -> None:
        """Test evaluating unknown phenotype raises error."""
        with pytest.raises(ValueError, match="Unknown phenotype"):
            self.engine.evaluate("nonexistent_phenotype", "patient123")


class TestCriterionEvaluation:
    """Tests for criterion evaluation with mock database."""

    def setup_method(self) -> None:
        """Set up test fixtures with mock session."""
        self.mock_session = MagicMock()
        self.engine = PhenotypeEngine(self.mock_session)

    def _setup_mock_query(self, matches: list[tuple]) -> None:
        """Set up mock query to return specified matches."""
        mock_result = MagicMock()
        mock_result.all.return_value = matches
        self.mock_session.execute.return_value = mock_result

    def test_criterion_with_no_matches(self) -> None:
        """Test criterion evaluation with no matching nodes."""
        self._setup_mock_query([])

        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            min_occurrences=1,
        )

        result = self.engine._evaluate_criterion(criterion, "patient123")

        assert result.met is False
        assert result.occurrence_count == 0

    def test_criterion_with_matches(self) -> None:
        """Test criterion evaluation with matching nodes."""
        # Create mock nodes and edges
        mock_node = MagicMock()
        mock_node.omop_concept_id = 123
        mock_node.label = "Test Condition"
        mock_node.node_type = NodeType.CONDITION
        mock_node.properties = {"assertion": "present"}

        mock_edge = MagicMock()
        mock_edge.event_date = datetime.now(timezone.utc)
        mock_edge.valid_from = None

        self._setup_mock_query([(mock_node, mock_edge)])

        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            min_occurrences=1,
            assertion_filter=["present"],
        )

        result = self.engine._evaluate_criterion(criterion, "patient123")

        assert result.met is True
        assert result.occurrence_count == 1
        assert len(result.matched_concepts) == 1

    def test_criterion_min_occurrences_not_met(self) -> None:
        """Test criterion with insufficient occurrences."""
        mock_node = MagicMock()
        mock_node.omop_concept_id = 123
        mock_node.label = "Test"
        mock_node.node_type = NodeType.MEASUREMENT
        mock_node.properties = {}

        mock_edge = MagicMock()
        mock_edge.event_date = datetime.now(timezone.utc)
        mock_edge.valid_from = None

        self._setup_mock_query([(mock_node, mock_edge)])

        criterion = PhenotypeCriterion(
            name="Test",
            concept_codes=[123],
            min_occurrences=2,  # Requires 2, only have 1
        )

        result = self.engine._evaluate_criterion(criterion, "patient123")

        assert result.met is False
        assert result.occurrence_count == 1


class TestCareGapIdentification:
    """Tests for care gap identification."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.engine = PhenotypeEngine(self.mock_session)

    def _setup_mock_query(self, matches: list[tuple]) -> None:
        """Set up mock query to return specified matches."""
        mock_result = MagicMock()
        mock_result.all.return_value = matches
        self.mock_session.execute.return_value = mock_result

    def test_care_gap_identified_when_criterion_not_met(self) -> None:
        """Test care gaps are identified when criteria not met."""
        # Setup: No matching medications
        self._setup_mock_query([])

        phenotype = PhenotypeDefinition(
            id="test",
            name="Test",
            description="Test",
            inclusion_criteria=[],
            care_gap_criteria=[
                PhenotypeCriterion(
                    name="Required Medication",
                    concept_codes=[123],
                    node_types=[NodeType.DRUG],
                    description="Required treatment",
                ),
            ],
        )

        self.engine.register_phenotype(phenotype)
        gaps = self.engine._identify_care_gaps(phenotype, "patient123")

        assert len(gaps) == 1
        assert gaps[0].severity == "high"  # Drug gaps are high severity
        assert "medication" in gaps[0].description.lower()

    def test_no_care_gap_when_criterion_met(self) -> None:
        """Test no care gaps when criteria are met."""
        mock_node = MagicMock()
        mock_node.omop_concept_id = 123
        mock_node.label = "Test Med"
        mock_node.node_type = NodeType.DRUG
        mock_node.properties = {}

        mock_edge = MagicMock()
        mock_edge.event_date = datetime.now(timezone.utc)
        mock_edge.valid_from = None

        self._setup_mock_query([(mock_node, mock_edge)])

        phenotype = PhenotypeDefinition(
            id="test",
            name="Test",
            description="Test",
            inclusion_criteria=[],
            care_gap_criteria=[
                PhenotypeCriterion(
                    name="Required Medication",
                    concept_codes=[123],
                    node_types=[NodeType.DRUG],
                    description="Required treatment",
                ),
            ],
        )

        self.engine.register_phenotype(phenotype)
        gaps = self.engine._identify_care_gaps(phenotype, "patient123")

        assert len(gaps) == 0


class TestPhenotypeResult:
    """Tests for PhenotypeResult dataclass."""

    def test_result_properties(self) -> None:
        """Test result property calculations."""
        criterion1 = PhenotypeCriterion(name="C1", concept_codes=[1])
        criterion2 = PhenotypeCriterion(name="C2", concept_codes=[2])

        result = PhenotypeResult(
            phenotype_id="test",
            patient_id="patient123",
            status=PhenotypeStatus.PRESENT,
            confidence=0.95,
            inclusion_results=[
                CriterionResult(criterion=criterion1, met=True),
                CriterionResult(criterion=criterion2, met=False),
            ],
            care_gaps=[
                CareGap(criterion=criterion2, description="Missing C2"),
            ],
        )

        assert result.is_present is True
        assert result.has_care_gaps is True
        assert result.inclusion_criteria_met == 1
        assert result.total_inclusion_criteria == 2

    def test_result_absent_status(self) -> None:
        """Test result with ABSENT status."""
        result = PhenotypeResult(
            phenotype_id="test",
            patient_id="patient123",
            status=PhenotypeStatus.ABSENT,
            confidence=0.80,
        )

        assert result.is_present is False
        assert result.has_care_gaps is False


class TestEvidenceSummary:
    """Tests for evidence summary generation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.engine = PhenotypeEngine(self.mock_session)

    def test_evidence_summary_content(self) -> None:
        """Test evidence summary includes key information."""
        phenotype = PhenotypeDefinition(
            id="test",
            name="Test Phenotype",
            description="Test",
            inclusion_criteria=[
                PhenotypeCriterion(name="Criterion 1", concept_codes=[1]),
            ],
        )

        criterion = PhenotypeCriterion(name="Criterion 1", concept_codes=[1])
        inclusion_results = [
            CriterionResult(criterion=criterion, met=True, occurrence_count=2),
        ]

        summary = self.engine._build_evidence_summary(
            phenotype,
            inclusion_results,
            [],
            PhenotypeStatus.PRESENT,
        )

        assert "Test Phenotype" in summary
        assert "present" in summary.lower()
        assert "Criterion 1" in summary
        assert "2 occurrence" in summary
