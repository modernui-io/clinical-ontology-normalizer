"""Tests for Criteria Fidelity (CSO-2.4).

Covers:
- Parsing condition criteria from free text
- Parsing measurement criteria with ranges and operators
- Parsing demographic criteria (age)
- Parsing medication criteria
- Parsing procedure criteria
- Parsing exclusion criteria
- Temporal constraint extraction
- Validation: missing units detected
- Validation: ambiguous terms detected
- Validation: impossible ranges detected (min > max)
- Validation: missing value detected
- Validation: incomplete BETWEEN operator
- Validation: valid criterion passes
- Trial-level validation with mixed valid/invalid criteria
- Fidelity score calculation
- Conflict detection between criteria
- API endpoint: parse
- API endpoint: validate
- API endpoint: validate trial criteria
- Suggest fix generation
- Edge cases and fallback behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.criteria_fidelity import (
    CriterionIssue,
    CriterionType,
    IssueSeverity,
    IssueType,
    Operator,
    ParseCriterionRequest,
    ParsedCriterion,
    TemporalConstraint,
    TrialValidationReport,
    ValidateCriterionRequest,
    ValidationResult,
)
from app.services.criteria_parser_service import CriteriaParserService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def parser() -> CriteriaParserService:
    """Return a fresh CriteriaParserService instance."""
    return CriteriaParserService()


# =============================================================================
# Parsing: Condition criteria
# =============================================================================


class TestParseConditionCriteria:
    """Test parsing condition criteria from free text."""

    def test_parse_type2_diabetes(self, parser: CriteriaParserService) -> None:
        """Parse 'Patient must have Type 2 Diabetes'."""
        result = parser.parse_criterion("Patient must have Type 2 Diabetes")
        assert result.criterion_type == CriterionType.CONDITION
        assert result.operator == Operator.EXISTS
        assert any("Type 2 Diabetes" in t for t in result.concept_terms)
        assert result.is_exclusion is False
        assert result.confidence > 0.5

    def test_parse_atopic_dermatitis(self, parser: CriteriaParserService) -> None:
        """Parse 'Diagnosed with Atopic Dermatitis'."""
        result = parser.parse_criterion("Diagnosed with Atopic Dermatitis")
        assert result.criterion_type == CriterionType.CONDITION
        assert any("Atopic Dermatitis" in t for t in result.concept_terms)

    def test_parse_hypertension(self, parser: CriteriaParserService) -> None:
        """Parse 'History of hypertension'."""
        result = parser.parse_criterion("History of hypertension")
        assert result.criterion_type == CriterionType.CONDITION
        assert any("Hypertension" in t or "HTN" in t for t in result.concept_terms)

    def test_parse_unknown_condition_fallback(self, parser: CriteriaParserService) -> None:
        """Unknown text falls back to condition type with warning."""
        result = parser.parse_criterion("Some rare unknown condition XYZ-123")
        assert result.criterion_type == CriterionType.CONDITION
        assert len(result.parse_warnings) > 0
        assert result.confidence < 1.0


# =============================================================================
# Parsing: Measurement criteria
# =============================================================================


class TestParseMeasurementCriteria:
    """Test parsing measurement criteria with numeric values."""

    def test_parse_hba1c_between(self, parser: CriteriaParserService) -> None:
        """Parse 'HbA1c between 6.5% and 10%'."""
        result = parser.parse_criterion("HbA1c between 6.5% and 10%")
        assert result.criterion_type == CriterionType.MEASUREMENT
        assert result.operator == Operator.BETWEEN
        assert result.value == 6.5
        assert result.value_high == 10.0
        assert result.unit == "%"
        assert any("HbA1c" in t for t in result.concept_terms)

    def test_parse_egfr_greater_than(self, parser: CriteriaParserService) -> None:
        """Parse 'eGFR >= 30 mL/min'."""
        result = parser.parse_criterion("eGFR >= 30 mL/min")
        assert result.criterion_type == CriterionType.MEASUREMENT
        assert result.operator == Operator.GREATER_THAN
        assert result.value == 30.0
        assert any("eGFR" in t for t in result.concept_terms)

    def test_parse_bmi_less_than(self, parser: CriteriaParserService) -> None:
        """Parse 'BMI < 40 kg/m2'."""
        result = parser.parse_criterion("BMI < 40 kg/m2")
        assert result.criterion_type == CriterionType.MEASUREMENT
        assert result.operator == Operator.LESS_THAN
        assert result.value == 40.0

    def test_parse_measurement_no_value(self, parser: CriteriaParserService) -> None:
        """Parse measurement term without value -> EXISTS with warning."""
        result = parser.parse_criterion("HbA1c must be available")
        assert result.criterion_type == CriterionType.MEASUREMENT
        assert result.operator == Operator.EXISTS
        assert len(result.parse_warnings) > 0

    def test_parse_measurement_assumed_unit(self, parser: CriteriaParserService) -> None:
        """Parse HbA1c with numeric value but no explicit unit -> assumed %."""
        result = parser.parse_criterion("HbA1c >= 6.5")
        assert result.criterion_type == CriterionType.MEASUREMENT
        assert result.value == 6.5
        # Should assume % unit with a warning
        assert result.unit == "%"
        assert any("unit" in w.lower() or "assuming" in w.lower() for w in result.parse_warnings)


# =============================================================================
# Parsing: Demographic criteria
# =============================================================================


class TestParseDemographicCriteria:
    """Test parsing demographic (age) criteria."""

    def test_parse_age_greater_than(self, parser: CriteriaParserService) -> None:
        """Parse 'Age >= 18 years'."""
        result = parser.parse_criterion("Age >= 18 years")
        assert result.criterion_type == CriterionType.DEMOGRAPHIC
        assert result.operator == Operator.GREATER_THAN
        assert result.value == 18
        assert result.unit == "years"

    def test_parse_age_between(self, parser: CriteriaParserService) -> None:
        """Parse 'Age between 18 and 75 years'."""
        result = parser.parse_criterion("Age between 18 and 75 years")
        assert result.criterion_type == CriterionType.DEMOGRAPHIC
        assert result.operator == Operator.BETWEEN
        assert result.value == 18
        assert result.value_high == 75

    def test_parse_age_bare_number(self, parser: CriteriaParserService) -> None:
        """Parse 'Age 18' -> assume >= with warning."""
        result = parser.parse_criterion("Age 18")
        assert result.criterion_type == CriterionType.DEMOGRAPHIC
        assert result.value == 18
        assert len(result.parse_warnings) > 0


# =============================================================================
# Parsing: Medication criteria
# =============================================================================


class TestParseMedicationCriteria:
    """Test parsing medication criteria."""

    def test_parse_currently_on_metformin(self, parser: CriteriaParserService) -> None:
        """Parse 'Currently on metformin'."""
        result = parser.parse_criterion("Currently on metformin")
        assert result.criterion_type == CriterionType.MEDICATION
        assert result.operator == Operator.EXISTS
        assert any("Metformin" in t for t in result.concept_terms)

    def test_parse_taking_insulin(self, parser: CriteriaParserService) -> None:
        """Parse 'Patient is taking insulin'."""
        result = parser.parse_criterion("Patient is taking insulin")
        assert result.criterion_type == CriterionType.MEDICATION
        assert any("Insulin" in t for t in result.concept_terms)


# =============================================================================
# Parsing: Procedure criteria
# =============================================================================


class TestParseProcedureCriteria:
    """Test parsing procedure criteria."""

    def test_parse_prior_surgery(self, parser: CriteriaParserService) -> None:
        """Parse 'Prior cardiac surgery'."""
        result = parser.parse_criterion("Prior cardiac surgery")
        assert result.criterion_type == CriterionType.PROCEDURE
        assert result.operator == Operator.EXISTS

    def test_parse_biopsy(self, parser: CriteriaParserService) -> None:
        """Parse 'Must have had a biopsy'."""
        result = parser.parse_criterion("Must have had a biopsy")
        assert result.criterion_type == CriterionType.PROCEDURE


# =============================================================================
# Parsing: Exclusion detection
# =============================================================================


class TestParseExclusionCriteria:
    """Test detection of exclusion prefixes."""

    def test_no_history_of(self, parser: CriteriaParserService) -> None:
        """Parse 'No history of cancer'."""
        result = parser.parse_criterion("No history of cancer")
        assert result.is_exclusion is True
        assert result.criterion_type == CriterionType.CONDITION

    def test_must_not_have(self, parser: CriteriaParserService) -> None:
        """Parse 'Must not have tuberculosis'."""
        result = parser.parse_criterion("Must not have tuberculosis")
        assert result.is_exclusion is True

    def test_explicit_exclusion_flag(self, parser: CriteriaParserService) -> None:
        """Parse with is_exclusion=True override."""
        result = parser.parse_criterion("Type 2 Diabetes", is_exclusion=True)
        assert result.is_exclusion is True


# =============================================================================
# Parsing: Temporal constraints
# =============================================================================


class TestParseTemporalConstraints:
    """Test extraction of temporal constraints."""

    def test_within_last_6_months(self, parser: CriteriaParserService) -> None:
        """Parse 'HbA1c >= 6.5% within the last 6 months'."""
        result = parser.parse_criterion("HbA1c >= 6.5% within the last 6 months")
        assert result.temporal_constraint is not None
        assert result.temporal_constraint.direction == "within_last"
        assert result.temporal_constraint.window_days == 180  # 6 * 30

    def test_currently_active(self, parser: CriteriaParserService) -> None:
        """Parse 'Currently on metformin'."""
        result = parser.parse_criterion("Currently on metformin")
        assert result.temporal_constraint is not None
        assert result.temporal_constraint.direction == "active"

    def test_no_temporal(self, parser: CriteriaParserService) -> None:
        """Parse criterion with no temporal constraint."""
        result = parser.parse_criterion("Type 2 Diabetes")
        assert result.temporal_constraint is None


# =============================================================================
# Validation: Missing units
# =============================================================================


class TestValidationMissingUnit:
    """Test detection of missing units on measurement criteria."""

    def test_missing_unit_detected(self, parser: CriteriaParserService) -> None:
        """Measurement with value but no unit -> ERROR."""
        criterion = ParsedCriterion(
            original_text="HbA1c >= 6.5",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.GREATER_THAN,
            value=6.5,
            unit=None,
        )
        result = parser.validate_criterion(criterion)
        assert not result.is_valid
        assert any(i.issue_type == IssueType.MISSING_UNIT for i in result.issues)

    def test_unit_present_passes(self, parser: CriteriaParserService) -> None:
        """Measurement with unit present -> no MISSING_UNIT issue."""
        criterion = ParsedCriterion(
            original_text="HbA1c >= 6.5%",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.GREATER_THAN,
            value=6.5,
            unit="%",
        )
        result = parser.validate_criterion(criterion)
        assert not any(i.issue_type == IssueType.MISSING_UNIT for i in result.issues)


# =============================================================================
# Validation: Ambiguous terms
# =============================================================================


class TestValidationAmbiguousTerms:
    """Test detection of ambiguous terms."""

    def test_ambiguous_term_detected(self, parser: CriteriaParserService) -> None:
        """Concept with 'elevated' -> WARNING."""
        criterion = ParsedCriterion(
            original_text="Elevated blood pressure",
            criterion_type=CriterionType.CONDITION,
            domain="Condition",
            concept_terms=["Elevated Blood Pressure"],
            operator=Operator.EXISTS,
        )
        result = parser.validate_criterion(criterion)
        assert any(i.issue_type == IssueType.AMBIGUOUS_TERM for i in result.issues)
        # Ambiguous is only a warning, criterion is still valid
        assert result.is_valid


# =============================================================================
# Validation: Impossible ranges
# =============================================================================


class TestValidationImpossibleRanges:
    """Test detection of impossible ranges (min > max)."""

    def test_min_greater_than_max(self, parser: CriteriaParserService) -> None:
        """BETWEEN with min > max -> ERROR."""
        criterion = ParsedCriterion(
            original_text="HbA1c between 10% and 6.5%",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.BETWEEN,
            value=10.0,
            value_high=6.5,
            unit="%",
        )
        result = parser.validate_criterion(criterion)
        assert not result.is_valid
        assert any(i.issue_type == IssueType.IMPOSSIBLE_RANGE for i in result.issues)

    def test_valid_range_passes(self, parser: CriteriaParserService) -> None:
        """BETWEEN with valid range -> passes."""
        criterion = ParsedCriterion(
            original_text="HbA1c between 6.5% and 10%",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.BETWEEN,
            value=6.5,
            value_high=10.0,
            unit="%",
        )
        result = parser.validate_criterion(criterion)
        assert result.is_valid
        assert not any(i.issue_type == IssueType.IMPOSSIBLE_RANGE for i in result.issues)


# =============================================================================
# Validation: Missing value
# =============================================================================


class TestValidationMissingValue:
    """Test detection of missing values for comparison operators."""

    def test_missing_value_on_greater_than(self, parser: CriteriaParserService) -> None:
        """GREATER_THAN with no value -> ERROR."""
        criterion = ParsedCriterion(
            original_text="HbA1c >=",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.GREATER_THAN,
            value=None,
            unit="%",
        )
        result = parser.validate_criterion(criterion)
        assert not result.is_valid
        assert any(i.issue_type == IssueType.MISSING_VALUE for i in result.issues)


# =============================================================================
# Validation: Incomplete BETWEEN
# =============================================================================


class TestValidationIncompleteBetween:
    """Test detection of incomplete BETWEEN operator."""

    def test_between_missing_upper_bound(self, parser: CriteriaParserService) -> None:
        """BETWEEN with only lower bound -> ERROR."""
        criterion = ParsedCriterion(
            original_text="HbA1c between 6.5% and ?",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.BETWEEN,
            value=6.5,
            value_high=None,
            unit="%",
        )
        result = parser.validate_criterion(criterion)
        assert not result.is_valid
        assert any(i.issue_type == IssueType.INCOMPLETE for i in result.issues)


# =============================================================================
# Validation: Valid criterion passes
# =============================================================================


class TestValidationValidCriterion:
    """Test that fully specified criteria pass validation."""

    def test_valid_condition_passes(self, parser: CriteriaParserService) -> None:
        """Well-formed condition criterion passes validation."""
        criterion = ParsedCriterion(
            original_text="Patient must have Type 2 Diabetes",
            criterion_type=CriterionType.CONDITION,
            domain="Condition",
            concept_terms=["Type 2 Diabetes"],
            operator=Operator.EXISTS,
        )
        result = parser.validate_criterion(criterion)
        assert result.is_valid
        assert len(result.issues) == 0

    def test_valid_measurement_passes(self, parser: CriteriaParserService) -> None:
        """Well-formed measurement criterion passes validation."""
        criterion = ParsedCriterion(
            original_text="HbA1c between 6.5% and 10%",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.BETWEEN,
            value=6.5,
            value_high=10.0,
            unit="%",
        )
        result = parser.validate_criterion(criterion)
        assert result.is_valid
        assert len(result.issues) == 0

    def test_valid_demographic_passes(self, parser: CriteriaParserService) -> None:
        """Well-formed demographic criterion passes validation."""
        criterion = ParsedCriterion(
            original_text="Age >= 18 years",
            criterion_type=CriterionType.DEMOGRAPHIC,
            domain="Demographic",
            concept_terms=["Age"],
            operator=Operator.GREATER_THAN,
            value=18,
            unit="years",
        )
        result = parser.validate_criterion(criterion)
        assert result.is_valid


# =============================================================================
# Trial-level validation
# =============================================================================


class TestTrialValidation:
    """Test trial-level validation with mixed criteria."""

    def test_mixed_valid_and_invalid(self, parser: CriteriaParserService) -> None:
        """Trial with mix of valid and invalid criteria."""
        criteria = [
            # Valid condition
            ParsedCriterion(
                original_text="Type 2 Diabetes",
                criterion_type=CriterionType.CONDITION,
                domain="Condition",
                concept_terms=["Type 2 Diabetes"],
                operator=Operator.EXISTS,
            ),
            # Valid measurement
            ParsedCriterion(
                original_text="HbA1c between 6.5% and 10%",
                criterion_type=CriterionType.MEASUREMENT,
                domain="Measurement",
                concept_terms=["HbA1c"],
                operator=Operator.BETWEEN,
                value=6.5,
                value_high=10.0,
                unit="%",
            ),
            # Invalid: missing unit
            ParsedCriterion(
                original_text="BMI > 18",
                criterion_type=CriterionType.MEASUREMENT,
                domain="Measurement",
                concept_terms=["BMI"],
                operator=Operator.GREATER_THAN,
                value=18.0,
                unit=None,
            ),
        ]

        report = parser.validate_trial_criteria("trial-123", criteria)
        assert report.trial_id == "trial-123"
        assert report.total_criteria == 3
        assert report.valid_count == 2
        assert report.error_count == 1
        assert 0.0 < report.overall_fidelity_score < 1.0
        assert len(report.results) == 3

    def test_all_valid_fidelity_score(self, parser: CriteriaParserService) -> None:
        """All valid criteria -> fidelity score = 1.0."""
        criteria = [
            ParsedCriterion(
                original_text="Type 2 Diabetes",
                criterion_type=CriterionType.CONDITION,
                domain="Condition",
                concept_terms=["Type 2 Diabetes"],
                operator=Operator.EXISTS,
            ),
            ParsedCriterion(
                original_text="Age >= 18 years",
                criterion_type=CriterionType.DEMOGRAPHIC,
                domain="Demographic",
                concept_terms=["Age"],
                operator=Operator.GREATER_THAN,
                value=18,
                unit="years",
            ),
        ]

        report = parser.validate_trial_criteria("trial-456", criteria)
        assert report.overall_fidelity_score == 1.0
        assert report.error_count == 0
        assert report.valid_count == 2

    def test_all_invalid_fidelity_score(self, parser: CriteriaParserService) -> None:
        """All invalid criteria -> fidelity score = 0.0."""
        criteria = [
            ParsedCriterion(
                original_text="HbA1c between 10% and 5%",
                criterion_type=CriterionType.MEASUREMENT,
                domain="Measurement",
                concept_terms=["HbA1c"],
                operator=Operator.BETWEEN,
                value=10.0,
                value_high=5.0,
                unit="%",
            ),
            ParsedCriterion(
                original_text="BMI >=",
                criterion_type=CriterionType.MEASUREMENT,
                domain="Measurement",
                concept_terms=["BMI"],
                operator=Operator.GREATER_THAN,
                value=None,
                unit=None,
            ),
        ]

        report = parser.validate_trial_criteria("trial-789", criteria)
        assert report.overall_fidelity_score == 0.0
        assert report.error_count == 2
        assert report.valid_count == 0

    def test_empty_criteria_list(self, parser: CriteriaParserService) -> None:
        """Empty criteria list -> fidelity score 0.0."""
        report = parser.validate_trial_criteria("trial-empty", [])
        assert report.total_criteria == 0
        assert report.overall_fidelity_score == 0.0


# =============================================================================
# Conflict detection
# =============================================================================


class TestConflictDetection:
    """Test detection of conflicting criteria."""

    def test_conflicting_age_ranges(self, parser: CriteriaParserService) -> None:
        """Age >= 65 AND Age < 18 -> CONFLICTING error."""
        criteria = [
            ParsedCriterion(
                original_text="Age >= 65",
                criterion_type=CriterionType.DEMOGRAPHIC,
                domain="Demographic",
                concept_terms=["Age"],
                operator=Operator.GREATER_THAN,
                value=65,
                unit="years",
            ),
            ParsedCriterion(
                original_text="Age < 18",
                criterion_type=CriterionType.DEMOGRAPHIC,
                domain="Demographic",
                concept_terms=["Age"],
                operator=Operator.LESS_THAN,
                value=18,
                unit="years",
            ),
        ]

        report = parser.validate_trial_criteria("trial-conflict", criteria)
        all_issues = []
        for r in report.results:
            all_issues.extend(r.issues)
        assert any(i.issue_type == IssueType.CONFLICTING for i in all_issues)


# =============================================================================
# Suggest fix
# =============================================================================


class TestSuggestFix:
    """Test suggestion generation for criterion issues."""

    def test_suggest_fix_missing_unit(self, parser: CriteriaParserService) -> None:
        """Missing unit -> fix suggestion mentions adding a unit."""
        criterion = ParsedCriterion(
            original_text="HbA1c >= 6.5",
            criterion_type=CriterionType.MEASUREMENT,
            domain="Measurement",
            concept_terms=["HbA1c"],
            operator=Operator.GREATER_THAN,
            value=6.5,
            unit=None,
        )
        issues = [
            CriterionIssue(
                issue_type=IssueType.MISSING_UNIT,
                description="No unit",
                severity=IssueSeverity.ERROR,
                field="unit",
            )
        ]
        fix = parser.suggest_fix(criterion, issues)
        assert "unit" in fix.lower()

    def test_suggest_fix_no_issues(self, parser: CriteriaParserService) -> None:
        """No issues -> 'No issues to fix'."""
        criterion = ParsedCriterion(
            original_text="Type 2 Diabetes",
            criterion_type=CriterionType.CONDITION,
            domain="Condition",
            concept_terms=["Type 2 Diabetes"],
            operator=Operator.EXISTS,
        )
        fix = parser.suggest_fix(criterion, [])
        assert "no issues" in fix.lower()


# =============================================================================
# API endpoint tests
# =============================================================================


@pytest.fixture
def app():
    """Create a minimal FastAPI app with criteria fidelity routes for testing."""
    from fastapi import FastAPI
    from app.api.criteria_fidelity import router

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    return test_app


@pytest.fixture
async def client(app):
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestAPIEndpoints:
    """Test API endpoints for criteria fidelity."""

    @pytest.mark.anyio
    async def test_parse_endpoint(self, client: AsyncClient) -> None:
        """POST /api/v1/criteria/parse returns parsed criterion."""
        response = await client.post(
            "/api/v1/criteria/parse",
            json={"text": "HbA1c between 6.5% and 10%", "is_exclusion": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["criterion_type"] == "measurement"
        assert data["operator"] == "between"
        assert data["value"] == 6.5
        assert data["value_high"] == 10.0

    @pytest.mark.anyio
    async def test_parse_endpoint_condition(self, client: AsyncClient) -> None:
        """POST /api/v1/criteria/parse parses condition text."""
        response = await client.post(
            "/api/v1/criteria/parse",
            json={"text": "Patient must have Type 2 Diabetes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["criterion_type"] == "condition"
        assert data["operator"] == "exists"

    @pytest.mark.anyio
    async def test_validate_endpoint(self, client: AsyncClient) -> None:
        """POST /api/v1/criteria/validate returns validation result."""
        criterion = {
            "original_text": "HbA1c >= 6.5",
            "criterion_type": "measurement",
            "domain": "Measurement",
            "concept_terms": ["HbA1c"],
            "operator": "greater_than",
            "value": 6.5,
            "unit": None,
        }
        response = await client.post(
            "/api/v1/criteria/validate",
            json={"criterion": criterion},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert any(i["issue_type"] == "MISSING_UNIT" for i in data["issues"])

    @pytest.mark.anyio
    async def test_validate_endpoint_valid(self, client: AsyncClient) -> None:
        """POST /api/v1/criteria/validate with valid criterion."""
        criterion = {
            "original_text": "HbA1c >= 6.5%",
            "criterion_type": "measurement",
            "domain": "Measurement",
            "concept_terms": ["HbA1c"],
            "operator": "greater_than",
            "value": 6.5,
            "unit": "%",
        }
        response = await client.post(
            "/api/v1/criteria/validate",
            json={"criterion": criterion},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True

    @pytest.mark.anyio
    async def test_validate_trial_criteria_with_texts(self, client: AsyncClient) -> None:
        """POST /api/v1/criteria/trials/{trial_id}/validate-criteria with texts."""
        response = await client.post(
            "/api/v1/criteria/trials/trial-test-123/validate-criteria",
            json={
                "criteria_texts": [
                    "Age >= 18 years",
                    "HbA1c between 6.5% and 10%",
                    "Patient must have Type 2 Diabetes",
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trial_id"] == "trial-test-123"
        assert data["total_criteria"] == 3
        assert data["overall_fidelity_score"] > 0.0
        assert len(data["results"]) == 3
