"""SDTM Validation Service.

Implements validation rules compatible with Pinnacle 21 for SDTM datasets.
Checks variable names, lengths, types, controlled terminology, and consistency.
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.models.sdtm_mapping import (
    SDTMDataType,
    SDTMDomainSpec,
    SDTMMappingSpec,
    SDTMVariable,
)

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""

    ERROR = "ERROR"  # Must fix before submission
    WARNING = "WARNING"  # Should fix but not blocking
    NOTE = "NOTE"  # Informational


class ValidationCategory(str, Enum):
    """Categories of validation rules."""

    STRUCTURE = "STRUCTURE"  # Dataset/variable structure
    CONTROLLED_TERM = "CONTROLLED_TERM"  # Controlled terminology
    DATA_TYPE = "DATA_TYPE"  # Data type conformance
    BUSINESS_RULE = "BUSINESS_RULE"  # Business logic rules
    CONSISTENCY = "CONSISTENCY"  # Cross-record consistency
    COMPLETENESS = "COMPLETENESS"  # Required data presence


@dataclass
class ValidationIssue:
    """A validation issue found in the data."""

    rule_id: str
    severity: ValidationSeverity
    category: ValidationCategory
    domain: str
    variable: str | None
    row: int | None
    message: str
    value: Any = None
    expected: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "domain": self.domain,
            "variable": self.variable,
            "row": self.row,
            "message": self.message,
            "value": str(self.value) if self.value is not None else None,
            "expected": str(self.expected) if self.expected is not None else None,
        }


@dataclass
class ValidationResult:
    """Result of validation for a domain or dataset."""

    domain: str | None
    record_count: int
    issues: list[ValidationIssue] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    @property
    def note_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.NOTE)

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "record_count": self.record_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "note_count": self.note_count,
            "is_valid": self.is_valid,
            "validated_at": self.validated_at.isoformat(),
            "issues": [i.to_dict() for i in self.issues],
        }


class SDTMValidator:
    """Validates SDTM datasets against rules and specifications."""

    # Valid variable name pattern (alphanumeric, underscore, 1-8 chars, start with letter)
    VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,7}$", re.IGNORECASE)

    # ISO 8601 date patterns
    ISO_DATE_PATTERN = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?(T\d{2}(:\d{2})?(:\d{2})?)?$")
    ISO_PARTIAL_DATE_PATTERN = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")

    # Known controlled terminologies (subset)
    CONTROLLED_TERMS: dict[str, set[str]] = {
        "NY": {"Y", "N"},
        "SEX": {"M", "F", "U", "UNDIFFERENTIATED"},
        "ETHNIC": {"HISPANIC OR LATINO", "NOT HISPANIC OR LATINO", "NOT REPORTED", "UNKNOWN"},
        "AESEV": {"MILD", "MODERATE", "SEVERE"},
        "OUT": {"RECOVERED/RESOLVED", "RECOVERING/RESOLVING", "NOT RECOVERED/NOT RESOLVED", "RECOVERED/RESOLVED WITH SEQUELAE", "FATAL", "UNKNOWN"},
        "ACN": {"DRUG WITHDRAWN", "DOSE REDUCED", "DOSE NOT CHANGED", "DOSE INCREASED", "NOT APPLICABLE", "UNKNOWN"},
        "STENRF": {"BEFORE", "DURING", "AFTER", "CONTINUING", "U"},
        "POSITION": {"SITTING", "STANDING", "SUPINE", "PRONE", "SEMI-RECUMBENT"},
    }

    def __init__(self) -> None:
        self._custom_terminologies: dict[str, set[str]] = {}

    def add_terminology(self, codelist_id: str, values: set[str]) -> None:
        """Add custom controlled terminology for validation.

        Args:
            codelist_id: Codelist identifier
            values: Set of valid values
        """
        self._custom_terminologies[codelist_id.upper()] = {v.upper() for v in values}

    def validate_domain(
        self,
        domain_spec: SDTMDomainSpec,
        records: list[dict[str, Any]],
    ) -> ValidationResult:
        """Validate all records for a domain.

        Args:
            domain_spec: Domain specification
            records: Records to validate

        Returns:
            Validation result with issues
        """
        issues: list[ValidationIssue] = []

        # Validate domain-level structure
        issues.extend(self._validate_domain_structure(domain_spec))

        # Validate each record
        for i, record in enumerate(records):
            issues.extend(self._validate_record(domain_spec, record, i))

        # Cross-record validations
        issues.extend(self._validate_cross_record(domain_spec, records))

        return ValidationResult(
            domain=domain_spec.domain,
            record_count=len(records),
            issues=issues,
        )

    def validate_mapping_spec(
        self, mapping_spec: SDTMMappingSpec
    ) -> ValidationResult:
        """Validate a mapping specification.

        Args:
            mapping_spec: Mapping specification to validate

        Returns:
            Validation result with issues
        """
        issues: list[ValidationIssue] = []

        # Check study-level requirements
        if not mapping_spec.study_id:
            issues.append(
                ValidationIssue(
                    rule_id="SD0001",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.COMPLETENESS,
                    domain="STUDY",
                    variable=None,
                    row=None,
                    message="Study ID is required",
                )
            )

        # Validate each domain spec
        for domain_spec in mapping_spec.domains:
            issues.extend(self._validate_domain_structure(domain_spec))

        return ValidationResult(
            domain=None,
            record_count=0,
            issues=issues,
        )

    def _validate_domain_structure(
        self, domain_spec: SDTMDomainSpec
    ) -> list[ValidationIssue]:
        """Validate domain specification structure."""
        issues: list[ValidationIssue] = []

        # Rule SD0101: Domain code must be 2 characters
        if len(domain_spec.domain) != 2:
            issues.append(
                ValidationIssue(
                    rule_id="SD0101",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.STRUCTURE,
                    domain=domain_spec.domain,
                    variable=None,
                    row=None,
                    message=f"Domain code must be 2 characters, got {len(domain_spec.domain)}",
                    value=domain_spec.domain,
                    expected="2 characters",
                )
            )

        # Validate each variable
        for var in domain_spec.variables:
            issues.extend(self._validate_variable_spec(domain_spec.domain, var))

        # Rule SD0102: Required identifier variables
        var_names = {v.name for v in domain_spec.variables}
        required_ids = {"STUDYID", "DOMAIN", "USUBJID"}
        missing_ids = required_ids - var_names
        for missing in missing_ids:
            issues.append(
                ValidationIssue(
                    rule_id="SD0102",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.COMPLETENESS,
                    domain=domain_spec.domain,
                    variable=missing,
                    row=None,
                    message=f"Required identifier variable {missing} is missing",
                )
            )

        # Rule SD0103: Sequence variable for non-DM domains
        if domain_spec.domain != "DM":
            seq_var = f"{domain_spec.domain}SEQ"
            if seq_var not in var_names:
                issues.append(
                    ValidationIssue(
                        rule_id="SD0103",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.COMPLETENESS,
                        domain=domain_spec.domain,
                        variable=seq_var,
                        row=None,
                        message=f"Sequence variable {seq_var} is required for domain {domain_spec.domain}",
                    )
                )

        return issues

    def _validate_variable_spec(
        self, domain: str, var: SDTMVariable
    ) -> list[ValidationIssue]:
        """Validate a variable specification."""
        issues: list[ValidationIssue] = []

        # Rule SD0201: Variable name format
        if not self.VAR_NAME_PATTERN.match(var.name):
            issues.append(
                ValidationIssue(
                    rule_id="SD0201",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.STRUCTURE,
                    domain=domain,
                    variable=var.name,
                    row=None,
                    message="Variable name must be 1-8 uppercase alphanumeric characters starting with a letter",
                    value=var.name,
                )
            )

        # Rule SD0202: Character variable length
        if var.data_type == SDTMDataType.CHAR and var.length:
            if var.length > 200:
                issues.append(
                    ValidationIssue(
                        rule_id="SD0202",
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.STRUCTURE,
                        domain=domain,
                        variable=var.name,
                        row=None,
                        message=f"Character variable length {var.length} exceeds recommended maximum of 200",
                        value=var.length,
                        expected="<= 200",
                    )
                )

        # Rule SD0203: Label length
        if len(var.label) > 40:
            issues.append(
                ValidationIssue(
                    rule_id="SD0203",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.STRUCTURE,
                    domain=domain,
                    variable=var.name,
                    row=None,
                    message=f"Variable label exceeds 40 characters",
                    value=len(var.label),
                    expected="<= 40",
                )
            )

        return issues

    def _validate_record(
        self,
        domain_spec: SDTMDomainSpec,
        record: dict[str, Any],
        row_num: int,
    ) -> list[ValidationIssue]:
        """Validate a single data record."""
        issues: list[ValidationIssue] = []
        var_map = {v.name: v for v in domain_spec.variables}

        for var_name, var_spec in var_map.items():
            value = record.get(var_name)

            # Rule SD0301: Required variable presence
            if var_spec.core == "Req" and (value is None or value == ""):
                issues.append(
                    ValidationIssue(
                        rule_id="SD0301",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.COMPLETENESS,
                        domain=domain_spec.domain,
                        variable=var_name,
                        row=row_num,
                        message=f"Required variable {var_name} is missing or empty",
                    )
                )
                continue

            if value is None or value == "":
                continue

            # Rule SD0302: Data type conformance
            type_issue = self._validate_data_type(
                domain_spec.domain, var_name, var_spec, value, row_num
            )
            if type_issue:
                issues.append(type_issue)

            # Rule SD0303: Character length
            if var_spec.data_type == SDTMDataType.CHAR and var_spec.length:
                if len(str(value)) > var_spec.length:
                    issues.append(
                        ValidationIssue(
                            rule_id="SD0303",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.DATA_TYPE,
                            domain=domain_spec.domain,
                            variable=var_name,
                            row=row_num,
                            message=f"Value length {len(str(value))} exceeds defined length {var_spec.length}",
                            value=value,
                            expected=f"<= {var_spec.length} characters",
                        )
                    )

            # Rule SD0304: Controlled terminology
            if var_spec.controlled_term:
                ct_issue = self._validate_controlled_term(
                    domain_spec.domain, var_name, var_spec.controlled_term, value, row_num
                )
                if ct_issue:
                    issues.append(ct_issue)

        return issues

    def _validate_data_type(
        self,
        domain: str,
        var_name: str,
        var_spec: SDTMVariable,
        value: Any,
        row_num: int,
    ) -> ValidationIssue | None:
        """Validate value conforms to expected data type."""

        if var_spec.data_type == SDTMDataType.NUM:
            try:
                float(value)
            except (ValueError, TypeError):
                return ValidationIssue(
                    rule_id="SD0302",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.DATA_TYPE,
                    domain=domain,
                    variable=var_name,
                    row=row_num,
                    message=f"Value is not numeric",
                    value=value,
                    expected="numeric",
                )

        elif var_spec.data_type == SDTMDataType.INTEGER:
            try:
                int(value)
            except (ValueError, TypeError):
                return ValidationIssue(
                    rule_id="SD0302",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.DATA_TYPE,
                    domain=domain,
                    variable=var_name,
                    row=row_num,
                    message=f"Value is not an integer",
                    value=value,
                    expected="integer",
                )

        elif var_spec.data_type in (SDTMDataType.DATE, SDTMDataType.DATETIME):
            if isinstance(value, str):
                if not self.ISO_DATE_PATTERN.match(value):
                    return ValidationIssue(
                        rule_id="SD0302",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.DATA_TYPE,
                        domain=domain,
                        variable=var_name,
                        row=row_num,
                        message=f"Date/time value is not in ISO 8601 format",
                        value=value,
                        expected="ISO 8601 (YYYY-MM-DDTHH:MM:SS)",
                    )

        return None

    def _validate_controlled_term(
        self,
        domain: str,
        var_name: str,
        codelist_id: str,
        value: Any,
        row_num: int,
    ) -> ValidationIssue | None:
        """Validate value against controlled terminology."""

        # Check custom terminologies first
        valid_values = self._custom_terminologies.get(codelist_id.upper())
        if valid_values is None:
            valid_values = self.CONTROLLED_TERMS.get(codelist_id.upper())

        if valid_values is None:
            # Unknown codelist - just note it
            return ValidationIssue(
                rule_id="SD0304",
                severity=ValidationSeverity.NOTE,
                category=ValidationCategory.CONTROLLED_TERM,
                domain=domain,
                variable=var_name,
                row=row_num,
                message=f"Unknown codelist '{codelist_id}' - cannot validate controlled terminology",
                value=value,
            )

        value_upper = str(value).upper()
        if value_upper not in valid_values:
            return ValidationIssue(
                rule_id="SD0304",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.CONTROLLED_TERM,
                domain=domain,
                variable=var_name,
                row=row_num,
                message=f"Value not in controlled terminology '{codelist_id}'",
                value=value,
                expected=f"One of: {', '.join(sorted(valid_values))}",
            )

        return None

    def _validate_cross_record(
        self,
        domain_spec: SDTMDomainSpec,
        records: list[dict[str, Any]],
    ) -> list[ValidationIssue]:
        """Validate cross-record consistency."""
        issues: list[ValidationIssue] = []

        if not records:
            return issues

        # Rule SD0401: Unique key
        if domain_spec.key_variables:
            seen_keys: set[tuple] = set()
            for i, record in enumerate(records):
                key = tuple(record.get(k) for k in domain_spec.key_variables)
                if key in seen_keys:
                    issues.append(
                        ValidationIssue(
                            rule_id="SD0401",
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.CONSISTENCY,
                            domain=domain_spec.domain,
                            variable=None,
                            row=i,
                            message=f"Duplicate key values: {domain_spec.key_variables}",
                            value=str(key),
                        )
                    )
                seen_keys.add(key)

        # Rule SD0402: STUDYID consistency
        study_ids = {record.get("STUDYID") for record in records}
        if len(study_ids) > 1:
            issues.append(
                ValidationIssue(
                    rule_id="SD0402",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONSISTENCY,
                    domain=domain_spec.domain,
                    variable="STUDYID",
                    row=None,
                    message=f"Multiple STUDYID values found in dataset",
                    value=str(study_ids),
                )
            )

        # Rule SD0403: Sequence numbering
        if domain_spec.domain != "DM":
            seq_var = f"{domain_spec.domain}SEQ"
            for usubjid in {r.get("USUBJID") for r in records}:
                subject_records = [r for r in records if r.get("USUBJID") == usubjid]
                seqs = sorted([r.get(seq_var, 0) for r in subject_records])
                expected_seqs = list(range(1, len(seqs) + 1))
                if seqs != expected_seqs:
                    issues.append(
                        ValidationIssue(
                            rule_id="SD0403",
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.CONSISTENCY,
                            domain=domain_spec.domain,
                            variable=seq_var,
                            row=None,
                            message=f"Sequence numbers for subject {usubjid} are not consecutive starting from 1",
                            value=str(seqs),
                            expected=str(expected_seqs),
                        )
                    )

        return issues


# Singleton instance
_validator_instance: SDTMValidator | None = None
_validator_lock = threading.Lock()


def get_sdtm_validator() -> SDTMValidator:
    """Get the SDTM validator singleton."""
    global _validator_instance
    # VP-ThreadSafety-8: Double-checked locking for thread safety
    if _validator_instance is None:
        with _validator_lock:
            if _validator_instance is None:
                _validator_instance = SDTMValidator()
    return _validator_instance
