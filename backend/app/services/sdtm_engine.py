"""SDTM Mapping Engine.

Transforms source data to SDTM format using mapping specifications.
Handles variable transformations, codelist lookups, and data type conversions.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

from app.models.sdtm_mapping import (
    SDTMDomainSpec,
    SDTMMappingSpec,
    TransformationType,
    VariableMapping,
)

logger = logging.getLogger(__name__)


@dataclass
class TransformationResult:
    """Result of a single transformation."""

    variable: str
    value: Any
    success: bool = True
    error: str | None = None


@dataclass
class RecordTransformResult:
    """Result of transforming a single source record."""

    source_row: int
    sdtm_record: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


@dataclass
class DomainTransformResult:
    """Result of transforming all records for a domain."""

    domain: str
    records: list[dict[str, Any]]
    record_count: int
    success_count: int
    error_count: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.error_count == 0


class CodelistManager:
    """Manages codelist lookups for SDTM transformations."""

    def __init__(self) -> None:
        # Default codelists - in production, load from CDISC CT
        self._codelists: dict[str, dict[str, str]] = {
            "SEX": {
                "male": "M",
                "female": "F",
                "m": "M",
                "f": "F",
                "unknown": "U",
                "undifferentiated": "U",
            },
            "NY": {
                "yes": "Y",
                "no": "N",
                "y": "Y",
                "n": "N",
                "true": "Y",
                "false": "N",
                "1": "Y",
                "0": "N",
            },
            "ETHNIC": {
                "hispanic or latino": "HISPANIC OR LATINO",
                "not hispanic or latino": "NOT HISPANIC OR LATINO",
                "unknown": "UNKNOWN",
                "not reported": "NOT REPORTED",
            },
            "AGEU": {
                "years": "YEARS",
                "year": "YEARS",
                "months": "MONTHS",
                "month": "MONTHS",
                "weeks": "WEEKS",
                "week": "WEEKS",
                "days": "DAYS",
                "day": "DAYS",
            },
            "AESEV": {
                "mild": "MILD",
                "moderate": "MODERATE",
                "severe": "SEVERE",
                "1": "MILD",
                "2": "MODERATE",
                "3": "SEVERE",
            },
            "ROUTE": {
                "oral": "ORAL",
                "intravenous": "INTRAVENOUS",
                "iv": "INTRAVENOUS",
                "subcutaneous": "SUBCUTANEOUS",
                "sc": "SUBCUTANEOUS",
                "intramuscular": "INTRAMUSCULAR",
                "im": "INTRAMUSCULAR",
                "topical": "TOPICAL",
                "inhaled": "INHALED",
                "inhalation": "INHALED",
            },
            "POSITION": {
                "sitting": "SITTING",
                "standing": "STANDING",
                "supine": "SUPINE",
                "prone": "PRONE",
            },
        }

    def lookup(self, codelist_id: str, value: Any) -> str | None:
        """Look up a value in a codelist.

        Args:
            codelist_id: Codelist identifier
            value: Value to look up

        Returns:
            Mapped value or None if not found
        """
        if value is None:
            return None

        codelist = self._codelists.get(codelist_id.upper())
        if not codelist:
            return str(value).upper()  # Return uppercased original if no codelist

        key = str(value).lower().strip()
        return codelist.get(key)

    def add_codelist(self, codelist_id: str, mappings: dict[str, str]) -> None:
        """Add or update a codelist.

        Args:
            codelist_id: Codelist identifier
            mappings: Dictionary of source to target mappings
        """
        self._codelists[codelist_id.upper()] = {
            k.lower(): v for k, v in mappings.items()
        }


class SDTMEngine:
    """Engine for transforming source data to SDTM format."""

    def __init__(self, mapping_spec: SDTMMappingSpec | None = None) -> None:
        self._mapping_spec = mapping_spec
        self._codelist_manager = CodelistManager()
        self._sequence_counters: dict[str, int] = {}

    @property
    def mapping_spec(self) -> SDTMMappingSpec | None:
        return self._mapping_spec

    @mapping_spec.setter
    def mapping_spec(self, spec: SDTMMappingSpec) -> None:
        self._mapping_spec = spec
        self._sequence_counters = {}

    @property
    def codelist_manager(self) -> CodelistManager:
        return self._codelist_manager

    def transform_record(
        self,
        source_record: dict[str, Any],
        domain_spec: SDTMDomainSpec,
        row_number: int = 0,
    ) -> RecordTransformResult:
        """Transform a single source record to SDTM format.

        Args:
            source_record: Source data record
            domain_spec: Domain specification with mappings
            row_number: Row number in source data

        Returns:
            Transformation result with SDTM record
        """
        sdtm_record: dict[str, Any] = {}
        warnings: list[str] = []
        errors: list[str] = []

        # Sort mappings by order
        sorted_mappings = sorted(
            domain_spec.variable_mappings, key=lambda m: m.order
        )

        for mapping in sorted_mappings:
            try:
                # Check condition
                if mapping.condition and not self._evaluate_condition(
                    mapping.condition, source_record, sdtm_record
                ):
                    continue

                result = self._apply_transformation(
                    mapping, source_record, sdtm_record, domain_spec
                )

                if result.success:
                    if result.value is not None:
                        sdtm_record[result.variable] = result.value
                else:
                    if result.error:
                        errors.append(result.error)

            except Exception as e:
                errors.append(
                    f"Error transforming {mapping.target_variable}: {str(e)}"
                )

        # Add domain constant if not mapped
        if "DOMAIN" not in sdtm_record:
            sdtm_record["DOMAIN"] = domain_spec.domain

        return RecordTransformResult(
            source_row=row_number,
            sdtm_record=sdtm_record,
            warnings=warnings,
            errors=errors,
        )

    def transform_domain(
        self,
        source_data: list[dict[str, Any]],
        domain_spec: SDTMDomainSpec,
    ) -> DomainTransformResult:
        """Transform all source records for a domain.

        Args:
            source_data: List of source records
            domain_spec: Domain specification

        Returns:
            Domain transformation result
        """
        records: list[dict[str, Any]] = []
        all_warnings: list[str] = []
        all_errors: list[str] = []
        success_count = 0

        # Reset sequence counter for this domain
        seq_var = f"{domain_spec.domain}SEQ"
        self._sequence_counters[seq_var] = 0

        for i, source_record in enumerate(source_data):
            result = self.transform_record(source_record, domain_spec, i)

            if result.success:
                records.append(result.sdtm_record)
                success_count += 1
            else:
                all_errors.extend(
                    [f"Row {i}: {e}" for e in result.errors]
                )

            all_warnings.extend(result.warnings)

        return DomainTransformResult(
            domain=domain_spec.domain,
            records=records,
            record_count=len(source_data),
            success_count=success_count,
            error_count=len(source_data) - success_count,
            warnings=all_warnings,
            errors=all_errors,
        )

    def _apply_transformation(
        self,
        mapping: VariableMapping,
        source_record: dict[str, Any],
        sdtm_record: dict[str, Any],
        domain_spec: SDTMDomainSpec,
    ) -> TransformationResult:
        """Apply a transformation to produce an SDTM variable value."""
        trans = mapping.transformation
        trans_type = trans.transformation_type

        try:
            if trans_type == TransformationType.DIRECT:
                value = self._transform_direct(trans.source_columns, source_record)

            elif trans_type == TransformationType.CONSTANT:
                value = trans.constant_value

            elif trans_type == TransformationType.CONCATENATE:
                value = self._transform_concatenate(
                    trans.source_columns, source_record, trans.format_pattern
                )

            elif trans_type == TransformationType.CODELIST:
                value = self._transform_codelist(
                    trans.source_columns, source_record, trans.codelist_id
                )

            elif trans_type == TransformationType.DATE_CONVERT:
                value = self._transform_date(
                    trans.source_columns, source_record, trans.format_pattern
                )

            elif trans_type == TransformationType.SUBSTRING:
                value = self._transform_substring(
                    trans.source_columns, source_record, trans.parameters
                )

            elif trans_type == TransformationType.EXPRESSION:
                value = self._transform_expression(
                    trans.format_pattern, source_record, sdtm_record
                )

            elif trans_type == TransformationType.LOOKUP:
                value = self._transform_lookup(
                    trans.source_columns, source_record, trans.lookup_table
                )

            elif trans_type == TransformationType.SEQUENCE:
                value = self._transform_sequence(
                    mapping.target_variable, trans.parameters
                )

            else:
                return TransformationResult(
                    variable=mapping.target_variable,
                    value=None,
                    success=False,
                    error=f"Unknown transformation type: {trans_type}",
                )

            return TransformationResult(
                variable=mapping.target_variable,
                value=value,
                success=True,
            )

        except Exception as e:
            return TransformationResult(
                variable=mapping.target_variable,
                value=None,
                success=False,
                error=str(e),
            )

    def _transform_direct(
        self, source_columns: list[str], source_record: dict[str, Any]
    ) -> Any:
        """Direct copy from first source column."""
        if not source_columns:
            return None
        return source_record.get(source_columns[0])

    def _transform_concatenate(
        self,
        source_columns: list[str],
        source_record: dict[str, Any],
        format_pattern: str | None,
    ) -> str | None:
        """Concatenate multiple source columns."""
        values = [source_record.get(col, "") for col in source_columns]
        if not any(values):
            return None

        if format_pattern:
            try:
                return format_pattern.format(*values)
            except (IndexError, KeyError):
                return "-".join(str(v) for v in values if v)
        else:
            return "-".join(str(v) for v in values if v)

    def _transform_codelist(
        self,
        source_columns: list[str],
        source_record: dict[str, Any],
        codelist_id: str | None,
    ) -> str | None:
        """Look up value in codelist."""
        if not source_columns or not codelist_id:
            return None

        source_value = source_record.get(source_columns[0])
        if source_value is None:
            return None

        mapped = self._codelist_manager.lookup(codelist_id, source_value)
        if mapped is None:
            logger.warning(
                f"No mapping found for '{source_value}' in codelist '{codelist_id}'"
            )
            return str(source_value).upper()

        return mapped

    def _transform_date(
        self,
        source_columns: list[str],
        source_record: dict[str, Any],
        format_pattern: str | None,
    ) -> str | None:
        """Convert date to ISO 8601 format."""
        if not source_columns:
            return None

        source_value = source_record.get(source_columns[0])
        if source_value is None:
            return None

        # If already ISO format, return as-is
        if isinstance(source_value, str) and re.match(
            r"^\d{4}-\d{2}-\d{2}", source_value
        ):
            return source_value

        # If datetime object
        if isinstance(source_value, datetime):
            return source_value.strftime("%Y-%m-%dT%H:%M:%S")

        # Try to parse with format pattern
        if format_pattern:
            try:
                dt = datetime.strptime(str(source_value), format_pattern)
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

        # Try common formats
        common_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"]
        for fmt in common_formats:
            try:
                dt = datetime.strptime(str(source_value), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return str(source_value)

    def _transform_substring(
        self,
        source_columns: list[str],
        source_record: dict[str, Any],
        parameters: dict[str, Any],
    ) -> str | None:
        """Extract substring from source value."""
        if not source_columns:
            return None

        source_value = source_record.get(source_columns[0])
        if source_value is None:
            return None

        start = parameters.get("start", 0)
        length = parameters.get("length")

        value_str = str(source_value)
        if length:
            return value_str[start : start + length]
        else:
            return value_str[start:]

    def _transform_expression(
        self,
        expression: str | None,
        source_record: dict[str, Any],
        sdtm_record: dict[str, Any],
    ) -> Any:
        """Evaluate a simple expression."""
        if not expression:
            return None

        # Create safe evaluation context
        context = {**source_record, **sdtm_record}

        # Simple arithmetic and string operations only
        # For security, we limit to basic operations
        try:
            # Handle simple conditional: value if condition else other
            if " if " in expression and " else " in expression:
                match = re.match(
                    r"(.+)\s+if\s+(.+)\s+else\s+(.+)", expression.strip()
                )
                if match:
                    true_val, condition, false_val = match.groups()
                    # Very basic condition evaluation
                    cond_result = self._evaluate_simple_condition(
                        condition.strip(), context
                    )
                    expr_to_eval = true_val if cond_result else false_val
                    return self._evaluate_simple_expr(expr_to_eval.strip(), context)

            return self._evaluate_simple_expr(expression, context)

        except Exception as e:
            logger.warning(f"Expression evaluation failed: {expression} - {e}")
            return None

    def _evaluate_simple_expr(self, expr: str, context: dict) -> Any:
        """Evaluate a simple expression (variable lookup or arithmetic)."""
        expr = expr.strip()

        # Direct variable lookup
        if expr in context:
            return context[expr]

        # Quoted string
        if (expr.startswith("'") and expr.endswith("'")) or (
            expr.startswith('"') and expr.endswith('"')
        ):
            return expr[1:-1]

        # Number
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        return None

    def _evaluate_simple_condition(self, condition: str, context: dict) -> bool:
        """Evaluate a simple condition."""
        # Handle == comparison
        if "==" in condition:
            parts = condition.split("==")
            if len(parts) == 2:
                left = self._evaluate_simple_expr(parts[0].strip(), context)
                right = self._evaluate_simple_expr(parts[1].strip(), context)
                return left == right

        # Handle != comparison
        if "!=" in condition:
            parts = condition.split("!=")
            if len(parts) == 2:
                left = self._evaluate_simple_expr(parts[0].strip(), context)
                right = self._evaluate_simple_expr(parts[1].strip(), context)
                return left != right

        # Handle 'in' operator
        if " in " in condition:
            parts = condition.split(" in ")
            if len(parts) == 2:
                left = self._evaluate_simple_expr(parts[0].strip(), context)
                # Handle tuple/list literal
                right = parts[1].strip()
                if right.startswith("(") and right.endswith(")"):
                    items = [
                        s.strip().strip("'\"")
                        for s in right[1:-1].split(",")
                    ]
                    return left in items

        return False

    def _transform_lookup(
        self,
        source_columns: list[str],
        source_record: dict[str, Any],
        lookup_table: str | None,
    ) -> Any:
        """Look up value in external table (placeholder)."""
        # In production, this would query an external lookup table
        if not source_columns:
            return None
        return source_record.get(source_columns[0])

    def _transform_sequence(
        self, variable: str, parameters: dict[str, Any]
    ) -> int:
        """Generate sequence number."""
        key = parameters.get("key", variable)
        start = parameters.get("start", 1)

        if key not in self._sequence_counters:
            self._sequence_counters[key] = start - 1

        self._sequence_counters[key] += 1
        return self._sequence_counters[key]

    def _evaluate_condition(
        self,
        condition: str,
        source_record: dict[str, Any],
        sdtm_record: dict[str, Any],
    ) -> bool:
        """Evaluate a mapping condition."""
        context = {**source_record, **sdtm_record}
        return self._evaluate_simple_condition(condition, context)


# Singleton instance
_engine_instance: SDTMEngine | None = None
_engine_lock = threading.Lock()


def get_sdtm_engine() -> SDTMEngine:
    """Get the SDTM engine singleton."""
    global _engine_instance
    # VP-ThreadSafety-6: Double-checked locking for thread safety
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = SDTMEngine()
    return _engine_instance
