"""Criteria Parser Service for Trial Eligibility Criteria Fidelity (CSO-2.4).

Parses free-text eligibility criteria into structured, machine-executable
format and validates that criteria definitions are complete, unambiguous,
and ready for the automated screening pipeline.

Usage:
    from app.services.criteria_parser_service import get_criteria_parser_service

    service = get_criteria_parser_service()
    parsed = service.parse_criterion("HbA1c between 6.5% and 10%")
    result = service.validate_criterion(parsed)
    report = service.validate_trial_criteria("trial-123", [parsed])
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any

from app.schemas.criteria_fidelity import (
    CriterionIssue,
    CriterionType,
    IssueSeverity,
    IssueType,
    Operator,
    ParsedCriterion,
    TemporalConstraint,
    TrialValidationReport,
    ValidationResult,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Known clinical terms and patterns
# ==============================================================================

# Maps recognized condition terms to canonical forms
_CONDITION_TERMS: dict[str, list[str]] = {
    "type 2 diabetes": ["Type 2 Diabetes", "T2DM", "DM2"],
    "type 1 diabetes": ["Type 1 Diabetes", "T1DM", "DM1"],
    "atopic dermatitis": ["Atopic Dermatitis", "Eczema", "AD"],
    "hypertension": ["Hypertension", "HTN", "High Blood Pressure"],
    "heart failure": ["Heart Failure", "CHF", "Congestive Heart Failure"],
    "chronic kidney disease": ["Chronic Kidney Disease", "CKD"],
    "asthma": ["Asthma"],
    "copd": ["COPD", "Chronic Obstructive Pulmonary Disease"],
    "cancer": ["Cancer", "Malignant Neoplasm", "Malignancy"],
    "tuberculosis": ["Tuberculosis", "TB"],
    "hiv": ["HIV", "Human Immunodeficiency Virus"],
    "hepatitis": ["Hepatitis"],
    "hepatitis b": ["Hepatitis B", "HBV"],
    "hepatitis c": ["Hepatitis C", "HCV"],
    "rheumatoid arthritis": ["Rheumatoid Arthritis", "RA"],
    "lupus": ["Lupus", "SLE", "Systemic Lupus Erythematosus"],
    "depression": ["Depression", "Major Depressive Disorder", "MDD"],
    "anxiety": ["Anxiety", "Generalized Anxiety Disorder", "GAD"],
}

# Maps recognized measurement terms to canonical forms and expected units
_MEASUREMENT_TERMS: dict[str, dict[str, Any]] = {
    "hba1c": {"terms": ["HbA1c", "Hemoglobin A1c", "A1C", "Glycated Hemoglobin"], "unit": "%"},
    "hemoglobin a1c": {"terms": ["HbA1c", "Hemoglobin A1c"], "unit": "%"},
    "a1c": {"terms": ["HbA1c", "A1C"], "unit": "%"},
    "egfr": {"terms": ["eGFR", "Estimated GFR"], "unit": "mL/min/1.73m2"},
    "creatinine": {"terms": ["Creatinine", "Serum Creatinine"], "unit": "mg/dL"},
    "bmi": {"terms": ["BMI", "Body Mass Index"], "unit": "kg/m2"},
    "blood pressure": {"terms": ["Blood Pressure", "BP"], "unit": "mmHg"},
    "systolic blood pressure": {"terms": ["Systolic Blood Pressure", "SBP"], "unit": "mmHg"},
    "diastolic blood pressure": {"terms": ["Diastolic Blood Pressure", "DBP"], "unit": "mmHg"},
    "ldl": {"terms": ["LDL", "LDL Cholesterol"], "unit": "mg/dL"},
    "hdl": {"terms": ["HDL", "HDL Cholesterol"], "unit": "mg/dL"},
    "triglycerides": {"terms": ["Triglycerides", "TG"], "unit": "mg/dL"},
    "alt": {"terms": ["ALT", "Alanine Aminotransferase", "SGPT"], "unit": "U/L"},
    "ast": {"terms": ["AST", "Aspartate Aminotransferase", "SGOT"], "unit": "U/L"},
    "platelet": {"terms": ["Platelets", "Platelet Count", "PLT"], "unit": "x10^9/L"},
    "wbc": {"terms": ["WBC", "White Blood Cell Count"], "unit": "x10^9/L"},
    "hemoglobin": {"terms": ["Hemoglobin", "Hb", "Hgb"], "unit": "g/dL"},
    "inr": {"terms": ["INR", "International Normalized Ratio"], "unit": ""},
    "potassium": {"terms": ["Potassium", "K+"], "unit": "mEq/L"},
    "sodium": {"terms": ["Sodium", "Na+"], "unit": "mEq/L"},
    "glucose": {"terms": ["Glucose", "Blood Glucose", "FBG"], "unit": "mg/dL"},
    "fasting glucose": {"terms": ["Fasting Glucose", "FBG", "Fasting Blood Glucose"], "unit": "mg/dL"},
}

# Maps recognized medication terms to canonical forms
_MEDICATION_TERMS: dict[str, list[str]] = {
    "metformin": ["Metformin"],
    "insulin": ["Insulin"],
    "dupilumab": ["Dupilumab", "Dupixent"],
    "cemiplimab": ["Cemiplimab", "Libtayo"],
    "aflibercept": ["Aflibercept", "Eylea"],
    "aspirin": ["Aspirin", "ASA"],
    "warfarin": ["Warfarin", "Coumadin"],
    "statin": ["Statin", "HMG-CoA Reductase Inhibitor"],
    "ace inhibitor": ["ACE Inhibitor", "ACEI"],
    "corticosteroid": ["Corticosteroid", "Steroid"],
    "immunosuppressant": ["Immunosuppressant"],
    "biologic": ["Biologic", "Biologic Therapy"],
}

# Ambiguous terms that need clarification
_AMBIGUOUS_TERMS: set[str] = {
    "abnormal",
    "elevated",
    "high",
    "low",
    "normal",
    "significant",
    "severe",
    "moderate",
    "mild",
    "recent",
    "chronic",
    "acute",
    "stable",
    "unstable",
    "active",
    "controlled",
    "uncontrolled",
    "adequate",
    "inadequate",
    "positive",
    "negative",
}

# Domain label mapping (criterion_type -> OMOP domain)
_DOMAIN_MAP: dict[CriterionType, str] = {
    CriterionType.CONDITION: "Condition",
    CriterionType.MEASUREMENT: "Measurement",
    CriterionType.DEMOGRAPHIC: "Demographic",
    CriterionType.MEDICATION: "Drug",
    CriterionType.PROCEDURE: "Procedure",
}

# Regex patterns for parsing
_BETWEEN_PATTERN = re.compile(
    r"(?:between\s+)"
    r"([\d.]+)\s*(%|mg/dL|g/dL|mmHg|mL/min|U/L|kg/m2|years?|mmol/L|mEq/L|ng/mL|pg/mL|x10\^9/L)?"
    r"\s*(?:and|to|-)\s*"
    r"([\d.]+)\s*(%|mg/dL|g/dL|mmHg|mL/min|U/L|kg/m2|years?|mmol/L|mEq/L|ng/mL|pg/mL|x10\^9/L)?",
    re.IGNORECASE,
)

_COMPARISON_PATTERN = re.compile(
    r"(>=?|<=?|>|<|equal(?:s)?\s+(?:to)?|greater\s+than(?:\s+or\s+equal\s+to)?|less\s+than(?:\s+or\s+equal\s+to)?|at\s+least|at\s+most|above|below|over|under|more\s+than|no\s+more\s+than)"
    r"\s*([\d.]+)\s*(%|mg/dL|g/dL|mmHg|mL/min|U/L|kg/m2|years?|mmol/L|mEq/L|ng/mL|pg/mL|x10\^9/L)?",
    re.IGNORECASE,
)

_AGE_PATTERN = re.compile(
    r"(?:age|aged?)\s*(>=?|<=?|>|<|between|at\s+least|at\s+most|over|under|above|below|from)?\s*"
    r"(\d+)\s*(?:(?:and|to|-)\s*(\d+))?\s*(?:years?(?:\s+old)?)?",
    re.IGNORECASE,
)

_TEMPORAL_PATTERN = re.compile(
    r"(?:within\s+(?:the\s+)?(?:last|past|previous)\s+(\d+)\s*(days?|weeks?|months?|years?))"
    r"|(?:(?:in\s+the\s+)?(?:last|past|previous)\s+(\d+)\s*(days?|weeks?|months?|years?))"
    r"|(?:currently|current|ongoing|active(?:ly)?)",
    re.IGNORECASE,
)

_EXCLUSION_PREFIXES = [
    "no history of",
    "no ",
    "without ",
    "absence of ",
    "must not have",
    "exclude",
    "excluded",
    "not have",
    "not on ",
    "not currently",
    "not receiving",
    "not taking",
    "free of",
    "free from",
]


# ==============================================================================
# Criteria Parser Service
# ==============================================================================


class CriteriaParserService:
    """Service for parsing and validating clinical trial eligibility criteria.

    Converts free-text criteria into structured ParsedCriterion objects,
    validates their completeness and executability, and generates
    trial-level fidelity reports.
    """

    def __init__(self) -> None:
        self._version = "1.0.0"

    # ==========================================================================
    # Parsing
    # ==========================================================================

    def parse_criterion(self, text: str, *, is_exclusion: bool = False) -> ParsedCriterion:
        """Parse a free-text eligibility criterion into a structured format.

        Uses pattern matching and term lookups to extract criterion type,
        concept terms, operator, value, unit, and temporal constraints.

        Args:
            text: Free-text criterion string.
            is_exclusion: Whether this is an exclusion criterion.

        Returns:
            ParsedCriterion with structured interpretation.
        """
        original = text.strip()
        normalized = original.lower()
        warnings: list[str] = []
        confidence = 1.0

        # Check for exclusion prefixes
        detected_exclusion = is_exclusion
        for prefix in _EXCLUSION_PREFIXES:
            if normalized.startswith(prefix):
                detected_exclusion = True
                # Remove the prefix for further parsing
                normalized = normalized[len(prefix):].strip()
                break

        # Attempt to classify and parse
        criterion_type, domain, concept_terms, operator, value, value_high, unit = (
            self._classify_and_extract(normalized, original, warnings)
        )

        # Extract temporal constraint
        temporal = self._extract_temporal(original)

        # Adjust confidence based on warnings
        if warnings:
            confidence = max(0.3, 1.0 - 0.15 * len(warnings))

        return ParsedCriterion(
            original_text=original,
            criterion_type=criterion_type,
            domain=domain,
            concept_terms=concept_terms,
            operator=operator,
            value=value,
            value_high=value_high,
            unit=unit,
            temporal_constraint=temporal,
            is_exclusion=detected_exclusion,
            confidence=round(confidence, 2),
            parse_warnings=warnings,
        )

    def _classify_and_extract(
        self,
        normalized: str,
        original: str,
        warnings: list[str],
    ) -> tuple[CriterionType, str, list[str], Operator, Any, Any, str | None]:
        """Classify the criterion type and extract structured fields.

        Returns:
            (criterion_type, domain, concept_terms, operator, value, value_high, unit)
        """
        # 1. Check for demographic (age) criteria
        age_match = _AGE_PATTERN.search(original)
        if age_match:
            return self._parse_demographic(age_match, original, warnings)

        # 2. Check for measurement criteria (has numeric values)
        for key, info in _MEASUREMENT_TERMS.items():
            if key in normalized:
                return self._parse_measurement(key, info, normalized, original, warnings)

        # 3. Check for medication criteria
        for key, terms in _MEDICATION_TERMS.items():
            if key in normalized:
                return (
                    CriterionType.MEDICATION,
                    _DOMAIN_MAP[CriterionType.MEDICATION],
                    terms,
                    Operator.EXISTS,
                    None,
                    None,
                    None,
                )

        # 4. Check for condition criteria
        for key, terms in _CONDITION_TERMS.items():
            if key in normalized:
                return (
                    CriterionType.CONDITION,
                    _DOMAIN_MAP[CriterionType.CONDITION],
                    terms,
                    Operator.EXISTS,
                    None,
                    None,
                    None,
                )

        # 5. Check for procedure keywords
        procedure_keywords = [
            "surgery", "procedure", "transplant", "biopsy", "resection",
            "implant", "catheterization", "endoscopy", "dialysis",
        ]
        for kw in procedure_keywords:
            if kw in normalized:
                # Extract the surrounding phrase as concept terms
                concept = self._extract_phrase_around(original, kw)
                return (
                    CriterionType.PROCEDURE,
                    _DOMAIN_MAP[CriterionType.PROCEDURE],
                    [concept] if concept else [kw.title()],
                    Operator.EXISTS,
                    None,
                    None,
                    None,
                )

        # 6. Fallback: check if there are numeric comparisons (likely measurement)
        between_match = _BETWEEN_PATTERN.search(original)
        comp_match = _COMPARISON_PATTERN.search(original)
        if between_match or comp_match:
            warnings.append(
                "Could not identify specific measurement term; "
                "parsed as generic measurement criterion"
            )
            # Try to extract the concept name from the text before the operator
            concept = self._extract_concept_before_operator(original)
            if between_match:
                low = float(between_match.group(1))
                high = float(between_match.group(3))
                unit = between_match.group(2) or between_match.group(4)
                return (
                    CriterionType.MEASUREMENT,
                    _DOMAIN_MAP[CriterionType.MEASUREMENT],
                    [concept] if concept else ["Unknown Measurement"],
                    Operator.BETWEEN,
                    low,
                    high,
                    unit,
                )
            if comp_match:
                op = self._normalize_operator(comp_match.group(1))
                val = float(comp_match.group(2))
                unit = comp_match.group(3)
                return (
                    CriterionType.MEASUREMENT,
                    _DOMAIN_MAP[CriterionType.MEASUREMENT],
                    [concept] if concept else ["Unknown Measurement"],
                    op,
                    val,
                    None,
                    unit,
                )

        # 7. Ultimate fallback: condition with low confidence
        warnings.append(
            "Could not determine criterion type from text; defaulting to condition"
        )
        # Use the full text as the concept term
        concept_terms = [original.strip().rstrip(".")]
        return (
            CriterionType.CONDITION,
            _DOMAIN_MAP[CriterionType.CONDITION],
            concept_terms,
            Operator.EXISTS,
            None,
            None,
            None,
        )

    def _parse_demographic(
        self,
        match: re.Match,
        original: str,
        warnings: list[str],
    ) -> tuple[CriterionType, str, list[str], Operator, Any, Any, str | None]:
        """Parse a demographic (age) criterion."""
        op_text = (match.group(1) or "").strip().lower()
        val1 = int(match.group(2))
        val2 = match.group(3)

        if val2 is not None:
            # "age between X and Y" or "age X to Y"
            return (
                CriterionType.DEMOGRAPHIC,
                _DOMAIN_MAP[CriterionType.DEMOGRAPHIC],
                ["Age"],
                Operator.BETWEEN,
                val1,
                int(val2),
                "years",
            )

        op = self._normalize_operator(op_text) if op_text else Operator.GREATER_THAN
        if not op_text:
            # Bare "age 18" -> assume >= 18
            op = Operator.GREATER_THAN
            warnings.append("No operator specified for age; assuming >=")

        return (
            CriterionType.DEMOGRAPHIC,
            _DOMAIN_MAP[CriterionType.DEMOGRAPHIC],
            ["Age"],
            op,
            val1,
            None,
            "years",
        )

    def _parse_measurement(
        self,
        key: str,
        info: dict[str, Any],
        normalized: str,
        original: str,
        warnings: list[str],
    ) -> tuple[CriterionType, str, list[str], Operator, Any, Any, str | None]:
        """Parse a measurement criterion with value extraction."""
        terms = info["terms"]
        expected_unit = info.get("unit")

        # Check for between pattern
        between_match = _BETWEEN_PATTERN.search(original)
        if between_match:
            low = float(between_match.group(1))
            high = float(between_match.group(3))
            parsed_unit = between_match.group(2) or between_match.group(4)
            unit = parsed_unit or expected_unit
            if not parsed_unit and expected_unit:
                warnings.append(f"No unit specified; assuming '{expected_unit}'")
            return (
                CriterionType.MEASUREMENT,
                _DOMAIN_MAP[CriterionType.MEASUREMENT],
                terms,
                Operator.BETWEEN,
                low,
                high,
                unit,
            )

        # Check for comparison pattern
        comp_match = _COMPARISON_PATTERN.search(original)
        if comp_match:
            op = self._normalize_operator(comp_match.group(1))
            val = float(comp_match.group(2))
            parsed_unit = comp_match.group(3)
            unit = parsed_unit or expected_unit
            if not parsed_unit and expected_unit:
                warnings.append(f"No unit specified; assuming '{expected_unit}'")
            return (
                CriterionType.MEASUREMENT,
                _DOMAIN_MAP[CriterionType.MEASUREMENT],
                terms,
                op,
                val,
                None,
                unit,
            )

        # Measurement term found but no value -> EXISTS operator
        warnings.append(
            f"Measurement term '{key}' found but no numeric value or operator detected"
        )
        return (
            CriterionType.MEASUREMENT,
            _DOMAIN_MAP[CriterionType.MEASUREMENT],
            terms,
            Operator.EXISTS,
            None,
            None,
            expected_unit,
        )

    def _extract_temporal(self, text: str) -> TemporalConstraint | None:
        """Extract temporal constraint from criterion text."""
        match = _TEMPORAL_PATTERN.search(text)
        if not match:
            return None

        # "currently" / "active" pattern
        if not match.group(1) and not match.group(3):
            return TemporalConstraint(direction="active")

        # "within last N days/months/years"
        count_str = match.group(1) or match.group(3)
        unit_str = match.group(2) or match.group(4)

        count = int(count_str)
        unit_lower = unit_str.lower().rstrip("s")

        days_map = {"day": 1, "week": 7, "month": 30, "year": 365}
        window_days = count * days_map.get(unit_lower, 1)

        return TemporalConstraint(
            direction="within_last",
            window_days=window_days,
        )

    def _normalize_operator(self, op_text: str) -> Operator:
        """Convert operator text/symbol to Operator enum."""
        op_lower = op_text.lower().strip()

        if op_lower in (">=", "at least", "greater than or equal to", "at least", "from"):
            return Operator.GREATER_THAN
        if op_lower in (">", "greater than", "above", "over", "more than"):
            return Operator.GREATER_THAN
        if op_lower in ("<=", "at most", "less than or equal to", "no more than"):
            return Operator.LESS_THAN
        if op_lower in ("<", "less than", "below", "under"):
            return Operator.LESS_THAN
        if op_lower in ("=", "equals", "equal to", "equal"):
            return Operator.EQUALS
        if op_lower == "between":
            return Operator.BETWEEN

        return Operator.GREATER_THAN  # default

    def _extract_phrase_around(self, text: str, keyword: str) -> str:
        """Extract meaningful phrase around a keyword from the original text."""
        idx = text.lower().find(keyword)
        if idx == -1:
            return keyword.title()

        # Take up to 4 words before and including the keyword phrase
        before = text[:idx].strip().split()
        after_start = idx + len(keyword)
        after = text[after_start:].strip().split()

        phrase_parts = before[-3:] + [text[idx:idx + len(keyword)]]
        if after and after[0].lower() not in {"and", "or", "is", "was", ",", "."}:
            phrase_parts.append(after[0])

        return " ".join(phrase_parts).strip(" ,.")

    def _extract_concept_before_operator(self, text: str) -> str:
        """Extract concept name from text before a comparison operator."""
        # Find first operator symbol or word
        op_patterns = [
            r">=?", r"<=?", r"between", r"greater than", r"less than",
            r"at least", r"at most", r"above", r"below", r"over", r"under",
        ]
        earliest_pos = len(text)
        for pat in op_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m and m.start() < earliest_pos:
                earliest_pos = m.start()

        concept = text[:earliest_pos].strip().rstrip(" :")
        return concept if concept else "Unknown"

    # ==========================================================================
    # Validation
    # ==========================================================================

    def validate_criterion(self, criterion: ParsedCriterion) -> ValidationResult:
        """Validate a parsed criterion for completeness and executability.

        Checks for:
        - Missing units on measurement criteria
        - Ambiguous terms in concept_terms
        - Impossible ranges (min > max for BETWEEN)
        - Missing values for comparison operators
        - Incomplete criterion definitions

        Args:
            criterion: A ParsedCriterion to validate.

        Returns:
            ValidationResult with issues and suggested fix.
        """
        issues: list[CriterionIssue] = []

        # 1. Check for missing units on measurements
        if criterion.criterion_type == CriterionType.MEASUREMENT:
            if criterion.operator not in (Operator.EXISTS, Operator.NOT_EXISTS):
                if not criterion.unit:
                    issues.append(CriterionIssue(
                        issue_type=IssueType.MISSING_UNIT,
                        description=(
                            f"Measurement criterion has a numeric value ({criterion.value}) "
                            f"but no unit specified"
                        ),
                        severity=IssueSeverity.ERROR,
                        field="unit",
                    ))

        # 2. Check for missing values on comparison operators
        if criterion.operator not in (Operator.EXISTS, Operator.NOT_EXISTS):
            if criterion.value is None:
                issues.append(CriterionIssue(
                    issue_type=IssueType.MISSING_VALUE,
                    description=(
                        f"Operator '{criterion.operator.value}' requires a value, "
                        f"but none was provided"
                    ),
                    severity=IssueSeverity.ERROR,
                    field="value",
                ))

        # 3. Check for impossible ranges
        if criterion.operator == Operator.BETWEEN:
            if criterion.value is not None and criterion.value_high is not None:
                try:
                    if float(criterion.value) > float(criterion.value_high):
                        issues.append(CriterionIssue(
                            issue_type=IssueType.IMPOSSIBLE_RANGE,
                            description=(
                                f"Range minimum ({criterion.value}) is greater than "
                                f"maximum ({criterion.value_high})"
                            ),
                            severity=IssueSeverity.ERROR,
                            field="value",
                        ))
                except (ValueError, TypeError):
                    pass
            if criterion.value_high is None:
                issues.append(CriterionIssue(
                    issue_type=IssueType.INCOMPLETE,
                    description="BETWEEN operator requires both lower and upper bounds",
                    severity=IssueSeverity.ERROR,
                    field="value_high",
                ))

        # 4. Check for ambiguous terms in concept_terms
        for term in criterion.concept_terms:
            term_words = set(term.lower().split())
            ambiguous_found = term_words & _AMBIGUOUS_TERMS
            if ambiguous_found:
                issues.append(CriterionIssue(
                    issue_type=IssueType.AMBIGUOUS_TERM,
                    description=(
                        f"Concept term '{term}' contains ambiguous word(s): "
                        f"{', '.join(sorted(ambiguous_found))}. "
                        f"Consider specifying exact thresholds or codes."
                    ),
                    severity=IssueSeverity.WARNING,
                    field="concept_terms",
                ))

        # 5. Check for empty concept terms
        if not criterion.concept_terms:
            issues.append(CriterionIssue(
                issue_type=IssueType.INCOMPLETE,
                description="No clinical concept terms identified in criterion",
                severity=IssueSeverity.ERROR,
                field="concept_terms",
            ))

        # 6. Check demographic-specific: age without range
        if criterion.criterion_type == CriterionType.DEMOGRAPHIC:
            if criterion.operator == Operator.EXISTS and criterion.value is None:
                issues.append(CriterionIssue(
                    issue_type=IssueType.INCOMPLETE,
                    description=(
                        "Demographic criterion specified without a value or range. "
                        "Specify an age range or other demographic constraint."
                    ),
                    severity=IssueSeverity.WARNING,
                    field="value",
                ))

        # 7. Check for negative value on measurements (likely data quality)
        if criterion.criterion_type == CriterionType.MEASUREMENT and criterion.value is not None:
            try:
                if float(criterion.value) < 0:
                    issues.append(CriterionIssue(
                        issue_type=IssueType.IMPOSSIBLE_RANGE,
                        description=(
                            f"Measurement value ({criterion.value}) is negative, "
                            f"which is likely invalid for most clinical measurements"
                        ),
                        severity=IssueSeverity.WARNING,
                        field="value",
                    ))
            except (ValueError, TypeError):
                pass

        # Generate is_valid and suggested_fix
        has_errors = any(i.severity == IssueSeverity.ERROR for i in issues)
        is_valid = not has_errors

        suggested_fix = None
        if issues:
            suggested_fix = self.suggest_fix(criterion, issues)

        return ValidationResult(
            criterion=criterion,
            is_valid=is_valid,
            issues=issues,
            suggested_fix=suggested_fix,
        )

    # ==========================================================================
    # Trial-level validation
    # ==========================================================================

    def validate_trial_criteria(
        self,
        trial_id: str,
        criteria: list[ParsedCriterion],
    ) -> TrialValidationReport:
        """Validate all criteria for a trial and produce a fidelity report.

        Args:
            trial_id: Identifier for the trial.
            criteria: List of ParsedCriterion to validate.

        Returns:
            TrialValidationReport with per-criterion results and overall score.
        """
        results: list[ValidationResult] = []
        valid_count = 0
        warning_count = 0
        error_count = 0

        for criterion in criteria:
            result = self.validate_criterion(criterion)
            results.append(result)

            if result.is_valid and not result.issues:
                valid_count += 1
            elif result.is_valid:
                # Valid but has warnings
                warning_count += 1
            else:
                error_count += 1

        # Check for conflicting criteria
        conflict_issues = self._detect_conflicts(criteria)
        if conflict_issues:
            # Add conflict warnings to the last result or create synthetic ones
            for issue in conflict_issues:
                # Mark as warning on the first affected criterion
                if results:
                    results[0].issues.append(issue)
                    if results[0].is_valid and issue.severity == IssueSeverity.ERROR:
                        results[0].is_valid = False
                        valid_count = max(0, valid_count - 1)
                        error_count += 1

        # Calculate fidelity score
        total = len(criteria)
        if total == 0:
            fidelity_score = 0.0
        else:
            # Each valid criterion contributes 1/total
            # Warnings reduce by 0.1 per warning
            # Errors contribute 0
            score = 0.0
            for result in results:
                if result.is_valid and not result.issues:
                    score += 1.0
                elif result.is_valid:
                    # Has warnings: partial credit
                    warning_penalty = min(0.5, 0.1 * len(result.issues))
                    score += 1.0 - warning_penalty
                # Errors contribute 0
            fidelity_score = round(score / total, 3)

        return TrialValidationReport(
            trial_id=trial_id,
            total_criteria=total,
            valid_count=valid_count,
            warning_count=warning_count,
            error_count=error_count,
            results=results,
            overall_fidelity_score=fidelity_score,
            validated_at=datetime.now(timezone.utc),
        )

    def _detect_conflicts(
        self, criteria: list[ParsedCriterion]
    ) -> list[CriterionIssue]:
        """Detect conflicting criteria (e.g., age >= 65 AND age < 18)."""
        issues: list[CriterionIssue] = []

        # Group criteria by type and concept
        by_concept: dict[str, list[ParsedCriterion]] = {}
        for c in criteria:
            key = f"{c.criterion_type.value}:{','.join(sorted(t.lower() for t in c.concept_terms))}"
            by_concept.setdefault(key, []).append(c)

        for key, group in by_concept.items():
            if len(group) < 2:
                continue

            # Check for range conflicts
            for i, c1 in enumerate(group):
                for c2 in group[i + 1:]:
                    conflict = self._check_range_conflict(c1, c2)
                    if conflict:
                        issues.append(conflict)

        return issues

    def _check_range_conflict(
        self, c1: ParsedCriterion, c2: ParsedCriterion
    ) -> CriterionIssue | None:
        """Check if two criteria on the same concept have conflicting ranges."""
        if c1.value is None or c2.value is None:
            return None

        try:
            v1 = float(c1.value)
            v2 = float(c2.value)
        except (ValueError, TypeError):
            return None

        # e.g., one says > 100 and the other says < 50
        if (
            c1.operator == Operator.GREATER_THAN
            and c2.operator == Operator.LESS_THAN
            and v1 >= v2
        ):
            return CriterionIssue(
                issue_type=IssueType.CONFLICTING,
                description=(
                    f"Conflicting criteria: '{c1.original_text}' requires > {v1} "
                    f"but '{c2.original_text}' requires < {v2}"
                ),
                severity=IssueSeverity.ERROR,
            )

        if (
            c2.operator == Operator.GREATER_THAN
            and c1.operator == Operator.LESS_THAN
            and v2 >= v1
        ):
            return CriterionIssue(
                issue_type=IssueType.CONFLICTING,
                description=(
                    f"Conflicting criteria: '{c2.original_text}' requires > {v2} "
                    f"but '{c1.original_text}' requires < {v1}"
                ),
                severity=IssueSeverity.ERROR,
            )

        return None

    # ==========================================================================
    # Suggest fix
    # ==========================================================================

    def suggest_fix(
        self, criterion: ParsedCriterion, issues: list[CriterionIssue]
    ) -> str:
        """Generate a suggested correction for criterion issues.

        Args:
            criterion: The criterion with issues.
            issues: List of issues found during validation.

        Returns:
            Human-readable suggestion string.
        """
        if not issues:
            return "No issues to fix."

        # Find the most severe issue
        error_issues = [i for i in issues if i.severity == IssueSeverity.ERROR]
        target = error_issues[0] if error_issues else issues[0]

        suggestions: dict[IssueType, str] = {
            IssueType.MISSING_UNIT: (
                f"Add a unit of measurement to the criterion. "
                f"For example: '{criterion.original_text} [specify unit, "
                f"e.g., %, mg/dL, mmHg]'"
            ),
            IssueType.AMBIGUOUS_TERM: (
                f"Replace ambiguous terms with specific, quantifiable thresholds. "
                f"Instead of vague terms, use exact values or standard codes."
            ),
            IssueType.UNRESOLVABLE_CONCEPT: (
                f"The clinical concept could not be mapped to a standard terminology. "
                f"Use standard medical terms, ICD-10 codes, or SNOMED CT concepts."
            ),
            IssueType.IMPOSSIBLE_RANGE: (
                f"Check the numeric range. The minimum value should be less than "
                f"the maximum value. Current range: {criterion.value} to {criterion.value_high}"
            ),
            IssueType.CONFLICTING: (
                "Review criteria for logical consistency. Two criteria targeting "
                "the same concept have incompatible requirements."
            ),
            IssueType.INCOMPLETE: (
                f"Add missing required fields. The criterion needs: "
                f"{target.field or 'additional specification'}"
            ),
            IssueType.MISSING_OPERATOR: (
                "Specify a comparison operator (e.g., >=, <=, between, equals)."
            ),
            IssueType.MISSING_VALUE: (
                f"Specify a numeric value for the '{criterion.operator.value}' operator."
            ),
        }

        return suggestions.get(target.issue_type, f"Fix issue: {target.description}")


# ==============================================================================
# Singleton
# ==============================================================================

_service: CriteriaParserService | None = None
_lock = threading.Lock()


def get_criteria_parser_service() -> CriteriaParserService:
    """Get singleton criteria parser service instance."""
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                _service = CriteriaParserService()
                logger.info("Initialized CriteriaParserService")
    return _service
