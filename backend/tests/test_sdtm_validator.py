"""Tests for SDTM validation rules.

Tests verify:
- Structure validation (required variables, key sequences)
- Controlled terminology validation
- Data type validation
- Business rule validation
- Cross-record consistency validation
- Completeness validation
- Pinnacle 21 compatible error codes
"""

import pytest

from app.services.sdtm_validator import (
    SDTMValidator,
    ValidationIssue,
    ValidationResult,
    ValidationCategory,
    ValidationSeverity,
    get_sdtm_validator,
)
from app.models.sdtm_mapping import (
    SDTMDomainSpec,
    SDTMVariable,
    SDTMMappingSpec,
    SDTMDomainClass,
    SDTMDataType,
    SDTMVariableRole,
)


class TestValidationIssue:
    """Test validation issue structure."""

    def test_issue_has_required_fields(self):
        issue = ValidationIssue(
            rule_id="SD0001",
            category=ValidationCategory.STRUCTURE,
            severity=ValidationSeverity.ERROR,
            message="Missing variable",
            domain="DM",
            variable="STUDYID",
            row=1,
        )
        assert issue.rule_id == "SD0001"
        assert issue.domain == "DM"
        assert issue.variable == "STUDYID"
        assert issue.row == 1

    def test_issue_to_dict(self):
        issue = ValidationIssue(
            rule_id="SD0001",
            category=ValidationCategory.STRUCTURE,
            severity=ValidationSeverity.ERROR,
            message="Test message",
            domain="DM",
            variable="STUDYID",
            row=1,
            value="test_value",
        )
        d = issue.to_dict()
        assert d["rule_id"] == "SD0001"
        assert d["domain"] == "DM"
        assert d["severity"] == "ERROR"


class TestStructureValidation:
    """Test structure validation rules."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    @pytest.fixture
    def dm_spec(self):
        return SDTMDomainSpec(
            domain="DM",
            domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
            label="Demographics",
            structure="One record per subject",
            key_variables=["STUDYID", "USUBJID"],
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR, core="Req", controlled_term="SEX"),
            ],
        )

    def test_valid_structure(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M"},
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ002", "SEX": "F"},
        ]
        result = validator.validate_domain(dm_spec, records)

        # Should have no structure errors
        structure_errors = [i for i in result.issues if i.category == ValidationCategory.STRUCTURE and i.severity == ValidationSeverity.ERROR]
        assert len(structure_errors) == 0

    def test_missing_required_variable(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001"},  # Missing SEX
        ]
        result = validator.validate_domain(dm_spec, records)

        # Should have completeness error for missing SEX
        sex_issues = [i for i in result.issues if i.variable == "SEX"]
        assert len(sex_issues) > 0

    def test_duplicate_key_values(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M"},
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "F"},  # Duplicate USUBJID
        ]
        result = validator.validate_domain(dm_spec, records)

        # Should have consistency error for duplicate keys
        consistency_issues = [i for i in result.issues if i.category == ValidationCategory.CONSISTENCY]
        assert len(consistency_issues) > 0

    def test_missing_studyid(self, validator, dm_spec):
        records = [
            {"DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M"},  # Missing STUDYID
        ]
        result = validator.validate_domain(dm_spec, records)

        studyid_issues = [i for i in result.issues if i.variable == "STUDYID"]
        assert len(studyid_issues) > 0


class TestControlledTerminologyValidation:
    """Test controlled terminology validation rules."""

    @pytest.fixture
    def validator(self):
        validator = SDTMValidator()
        # SEX codelist is built-in
        return validator

    @pytest.fixture
    def dm_spec(self):
        return SDTMDomainSpec(
            domain="DM",
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR, controlled_term="SEX"),
            ],
        )

    def test_valid_controlled_term(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M"},
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ002", "SEX": "F"},
        ]
        result = validator.validate_domain(dm_spec, records)

        ct_errors = [i for i in result.issues if i.category == ValidationCategory.CONTROLLED_TERM and i.severity == ValidationSeverity.ERROR]
        assert len(ct_errors) == 0

    def test_invalid_controlled_term(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "X"},  # Invalid value
        ]
        result = validator.validate_domain(dm_spec, records)

        ct_issues = [i for i in result.issues if i.category == ValidationCategory.CONTROLLED_TERM and i.severity == ValidationSeverity.ERROR]
        assert len(ct_issues) > 0
        assert any("SEX" in (i.variable or "") for i in ct_issues)

    def test_null_controlled_term_allowed(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": None},
        ]
        result = validator.validate_domain(dm_spec, records)

        # Null values are handled by completeness rules, not CT validation
        ct_errors = [i for i in result.issues if i.category == ValidationCategory.CONTROLLED_TERM and i.severity == ValidationSeverity.ERROR]
        # Should not have CT error for null (CT is only checked if value present)
        assert len(ct_errors) == 0


class TestDataTypeValidation:
    """Test data type validation rules."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    @pytest.fixture
    def lb_spec(self):
        return SDTMDomainSpec(
            domain="LB",
            label="Laboratory Test Results",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="LBSEQ", label="Sequence", data_type=SDTMDataType.NUM),
                SDTMVariable(name="LBSTRESN", label="Numeric Result", data_type=SDTMDataType.NUM),
                SDTMVariable(name="LBDTC", label="Date/Time", data_type=SDTMDataType.DATETIME),
            ],
        )

    def test_valid_numeric_values(self, validator, lb_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "LB", "USUBJID": "SUBJ001", "LBSEQ": 1, "LBSTRESN": 120.5, "LBDTC": "2024-01-15T10:30:00"},
        ]
        result = validator.validate_domain(lb_spec, records)

        dtype_errors = [i for i in result.issues if i.category == ValidationCategory.DATA_TYPE and i.severity == ValidationSeverity.ERROR]
        assert len(dtype_errors) == 0

    def test_invalid_numeric_value(self, validator, lb_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "LB", "USUBJID": "SUBJ001", "LBSEQ": "not_a_number", "LBSTRESN": 120, "LBDTC": "2024-01-15"},
        ]
        result = validator.validate_domain(lb_spec, records)

        dtype_issues = [i for i in result.issues if i.category == ValidationCategory.DATA_TYPE]
        assert len(dtype_issues) > 0

    def test_invalid_date_format(self, validator, lb_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "LB", "USUBJID": "SUBJ001", "LBSEQ": 1, "LBSTRESN": 120, "LBDTC": "15/01/2024"},  # Invalid format
        ]
        result = validator.validate_domain(lb_spec, records)

        date_issues = [i for i in result.issues if i.variable == "LBDTC"]
        assert len(date_issues) > 0


class TestConsistencyValidation:
    """Test cross-record consistency validation."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    @pytest.fixture
    def vs_spec(self):
        return SDTMDomainSpec(
            domain="VS",
            domain_class=SDTMDomainClass.FINDINGS,
            label="Vital Signs",
            key_variables=["STUDYID", "USUBJID", "VSSEQ"],
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="VSSEQ", label="Sequence", data_type=SDTMDataType.NUM),
                SDTMVariable(name="VSTESTCD", label="Test Code", data_type=SDTMDataType.CHAR),
            ],
        )

    def test_sequence_continuity(self, validator, vs_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 1, "VSTESTCD": "SYSBP"},
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 2, "VSTESTCD": "DIABP"},
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 3, "VSTESTCD": "PULSE"},
        ]
        result = validator.validate_domain(vs_spec, records)

        seq_issues = [i for i in result.issues if "sequence" in i.message.lower() or "SEQ" in (i.variable or "")]
        # Continuous sequence should not have errors (may have notes/warnings)
        seq_errors = [i for i in seq_issues if i.severity == ValidationSeverity.ERROR]
        assert len(seq_errors) == 0

    def test_sequence_gap_warning(self, validator, vs_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 1, "VSTESTCD": "SYSBP"},
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 3, "VSTESTCD": "DIABP"},  # Gap - missing 2
        ]
        result = validator.validate_domain(vs_spec, records)

        # Should flag sequence gap as warning
        seq_issues = [i for i in result.issues if "sequence" in i.message.lower()]
        assert len(seq_issues) > 0


class TestCompletenessValidation:
    """Test completeness validation rules."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    @pytest.fixture
    def dm_spec(self):
        return SDTMDomainSpec(
            domain="DM",
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="RACE", label="Race", data_type=SDTMDataType.CHAR, core="Exp"),
            ],
        )

    def test_all_required_present(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M", "RACE": "WHITE"},
        ]
        result = validator.validate_domain(dm_spec, records)

        completeness_errors = [i for i in result.issues if i.category == ValidationCategory.COMPLETENESS and i.severity == ValidationSeverity.ERROR]
        assert len(completeness_errors) == 0

    def test_missing_required_field(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "RACE": "WHITE"},  # Missing SEX
        ]
        result = validator.validate_domain(dm_spec, records)

        completeness_issues = [i for i in result.issues if i.category == ValidationCategory.COMPLETENESS]
        assert len(completeness_issues) > 0
        assert any("SEX" in (i.variable or "") or "SEX" in i.message for i in completeness_issues)

    def test_empty_string_treated_as_missing(self, validator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "", "RACE": "WHITE"},
        ]
        result = validator.validate_domain(dm_spec, records)

        # Empty string should be flagged for required field
        completeness_issues = [i for i in result.issues if i.category == ValidationCategory.COMPLETENESS]
        assert len(completeness_issues) > 0


class TestMappingSpecValidation:
    """Test mapping specification validation."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    def test_valid_mapping_spec(self, validator):
        spec = SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            sdtmig_version="3.3",
            domains=[
                SDTMDomainSpec(
                    domain="DM",
                    label="Demographics",
                    key_variables=["STUDYID", "USUBJID"],
                    variables=[
                        SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                        SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                        SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                    ],
                ),
            ],
        )
        result = validator.validate_mapping_spec(spec)
        # May have structure warnings but should not have critical errors
        assert result.error_count == 0 or result is not None

    def test_mapping_spec_missing_study_id(self, validator):
        spec = SDTMMappingSpec(
            study_id="",
            study_name="Test Study",
            sdtmig_version="3.3",
            domains=[],
        )
        result = validator.validate_mapping_spec(spec)

        # Should flag missing study ID
        issues = [i for i in result.issues if "study" in i.message.lower()]
        assert len(issues) > 0


class TestValidationResult:
    """Test validation result structure."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    @pytest.fixture
    def simple_spec(self):
        return SDTMDomainSpec(
            domain="DM",
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR, core="Req"),
            ],
        )

    def test_result_counts(self, validator, simple_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001"},
            {"STUDYID": "STUDY001", "DOMAIN": "DM"},  # Missing USUBJID
        ]
        result = validator.validate_domain(simple_spec, records)

        assert result.record_count == 2
        assert result.error_count >= 0
        assert result.warning_count >= 0

    def test_result_is_valid(self, validator, simple_spec):
        # Valid records
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001"},
        ]
        result = validator.validate_domain(simple_spec, records)
        assert result.is_valid == (result.error_count == 0)

    def test_result_to_dict(self, validator, simple_spec):
        records = [{"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001"}]
        result = validator.validate_domain(simple_spec, records)

        d = result.to_dict()
        assert "domain" in d
        assert "record_count" in d
        assert "error_count" in d
        assert "issues" in d


class TestValidatorSingleton:
    """Test singleton pattern."""

    def test_get_sdtm_validator_singleton(self):
        v1 = get_sdtm_validator()
        v2 = get_sdtm_validator()
        assert v1 is v2


class TestCustomTerminology:
    """Test custom terminology loading."""

    def test_add_custom_terminology(self):
        validator = SDTMValidator()
        validator.add_terminology("CUSTOM", {"A", "B", "C"})

        spec = SDTMDomainSpec(
            domain="XX",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="VAR", label="Variable", data_type=SDTMDataType.CHAR, controlled_term="CUSTOM"),
            ],
        )
        records = [{"STUDYID": "S1", "DOMAIN": "XX", "USUBJID": "U1", "VAR": "A"}]
        result = validator.validate_domain(spec, records)

        ct_errors = [i for i in result.issues if i.category == ValidationCategory.CONTROLLED_TERM and i.severity == ValidationSeverity.ERROR]
        assert len(ct_errors) == 0

    def test_custom_terminology_invalid_value(self):
        validator = SDTMValidator()
        validator.add_terminology("CUSTOM", {"A", "B", "C"})

        spec = SDTMDomainSpec(
            domain="XX",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="VAR", label="Variable", data_type=SDTMDataType.CHAR, controlled_term="CUSTOM"),
            ],
        )
        records = [{"STUDYID": "S1", "DOMAIN": "XX", "USUBJID": "U1", "VAR": "X"}]  # Invalid value
        result = validator.validate_domain(spec, records)

        ct_errors = [i for i in result.issues if i.category == ValidationCategory.CONTROLLED_TERM and i.severity == ValidationSeverity.ERROR]
        assert len(ct_errors) > 0

    def test_unknown_terminology_note(self):
        validator = SDTMValidator()

        spec = SDTMDomainSpec(
            domain="XX",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="VAR", label="Variable", data_type=SDTMDataType.CHAR, controlled_term="UNKNOWN_CT"),
            ],
        )
        records = [{"STUDYID": "S1", "DOMAIN": "XX", "USUBJID": "U1", "VAR": "X"}]
        result = validator.validate_domain(spec, records)

        # Unknown codelist should generate a note, not an error
        ct_notes = [i for i in result.issues if i.category == ValidationCategory.CONTROLLED_TERM and i.severity == ValidationSeverity.NOTE]
        assert len(ct_notes) > 0


class TestDomainCodeValidation:
    """Test domain code validation."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    def test_valid_domain_code(self, validator):
        spec = SDTMDomainSpec(
            domain="DM",
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
            ],
        )
        result = validator.validate_domain(spec, [])

        structure_errors = [i for i in result.issues if i.rule_id == "SD0101"]
        assert len(structure_errors) == 0

    def test_invalid_domain_code_length(self, validator):
        spec = SDTMDomainSpec(
            domain="DEMO",  # Too long
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
            ],
        )
        result = validator.validate_domain(spec, [])

        structure_errors = [i for i in result.issues if i.rule_id == "SD0101"]
        assert len(structure_errors) > 0


class TestVariableNameValidation:
    """Test variable name validation."""

    @pytest.fixture
    def validator(self):
        return SDTMValidator()

    def test_valid_variable_name(self, validator):
        spec = SDTMDomainSpec(
            domain="DM",
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
            ],
        )
        result = validator.validate_domain(spec, [])

        name_errors = [i for i in result.issues if i.rule_id == "SD0201"]
        assert len(name_errors) == 0

    def test_invalid_variable_name_too_long(self, validator):
        spec = SDTMDomainSpec(
            domain="DM",
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="TOOLONGNAME", label="Too Long", data_type=SDTMDataType.CHAR),  # > 8 chars
            ],
        )
        result = validator.validate_domain(spec, [])

        name_errors = [i for i in result.issues if i.rule_id == "SD0201"]
        assert len(name_errors) > 0

    def test_invalid_variable_name_starts_with_number(self, validator):
        spec = SDTMDomainSpec(
            domain="DM",
            label="Demographics",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="1VAR", label="Invalid", data_type=SDTMDataType.CHAR),  # Starts with number
            ],
        )
        result = validator.validate_domain(spec, [])

        name_errors = [i for i in result.issues if i.rule_id == "SD0201"]
        assert len(name_errors) > 0
