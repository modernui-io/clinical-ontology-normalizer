"""Criteria Fidelity API endpoints (CSO-2.4).

Endpoints for parsing, validating, and reporting on clinical trial
eligibility criteria definitions to ensure they are complete,
unambiguous, and machine-executable.

Endpoints:
    POST /api/v1/criteria/parse                       - Parse a single criterion text
    POST /api/v1/criteria/validate                    - Validate a criterion definition
    POST /api/v1/trials/{trial_id}/validate-criteria  - Validate all criteria for a trial
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.criteria_fidelity import (
    ParseCriterionRequest,
    ParsedCriterion,
    TrialValidationReport,
    ValidateCriterionRequest,
    ValidateTrialCriteriaRequest,
    ValidationResult,
)
from app.services.criteria_parser_service import get_criteria_parser_service
from app.services.trial_eligibility_service import get_trial_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/criteria", tags=["Criteria Fidelity"])


# ==============================================================================
# Parse endpoint
# ==============================================================================


@router.post(
    "/parse",
    response_model=ParsedCriterion,
    summary="Parse a free-text eligibility criterion",
    description=(
        "Parse a natural-language eligibility criterion into a structured, "
        "machine-executable format. Returns the parsed criterion with "
        "concept terms, operator, value, unit, and confidence."
    ),
)
async def parse_criterion(request: ParseCriterionRequest) -> ParsedCriterion:
    """Parse a free-text criterion into structured format."""
    service = get_criteria_parser_service()
    parsed = service.parse_criterion(request.text, is_exclusion=request.is_exclusion)
    logger.info(
        "Parsed criterion: type=%s, operator=%s, confidence=%.2f",
        parsed.criterion_type.value,
        parsed.operator.value,
        parsed.confidence,
    )
    return parsed


# ==============================================================================
# Validate endpoint
# ==============================================================================


@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="Validate a parsed criterion definition",
    description=(
        "Validate a structured criterion definition for completeness and "
        "executability. Checks for missing units, ambiguous terms, "
        "impossible ranges, and other quality issues."
    ),
)
async def validate_criterion(request: ValidateCriterionRequest) -> ValidationResult:
    """Validate a criterion for completeness and executability."""
    service = get_criteria_parser_service()
    result = service.validate_criterion(request.criterion)
    logger.info(
        "Validated criterion: valid=%s, issues=%d",
        result.is_valid,
        len(result.issues),
    )
    return result


# ==============================================================================
# Trial-level validation endpoint
# ==============================================================================


@router.post(
    "/trials/{trial_id}/validate-criteria",
    response_model=TrialValidationReport,
    summary="Validate all eligibility criteria for a trial",
    description=(
        "Validate all inclusion and exclusion criteria defined for a trial. "
        "If criteria_texts is provided, those texts are parsed first. "
        "Otherwise, the trial's existing criteria definitions are validated. "
        "Returns a fidelity report with per-criterion results and an "
        "overall fidelity score."
    ),
)
async def validate_trial_criteria(
    trial_id: str,
    request: ValidateTrialCriteriaRequest | None = None,
) -> TrialValidationReport:
    """Validate all criteria for a trial."""
    parser = get_criteria_parser_service()

    if request and request.criteria_texts:
        # Parse provided texts into criteria
        criteria = [parser.parse_criterion(text) for text in request.criteria_texts]
    else:
        # Load criteria from the trial definition
        trial_service = get_trial_service()
        trial = await trial_service.get_trial(trial_id)
        if not trial:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trial '{trial_id}' not found",
            )

        # Extract criteria texts from the trial's inclusion/exclusion criteria
        criteria = _extract_criteria_from_trial(trial, parser)

    report = parser.validate_trial_criteria(trial_id, criteria)
    logger.info(
        "Trial %s criteria validation: %d total, %d valid, %d warnings, %d errors, "
        "fidelity=%.3f",
        trial_id,
        report.total_criteria,
        report.valid_count,
        report.warning_count,
        report.error_count,
        report.overall_fidelity_score,
    )
    return report


def _extract_criteria_from_trial(trial, parser) -> list[ParsedCriterion]:
    """Extract and parse criteria from a trial's inclusion/exclusion dicts.

    Reads the existing criterion JSON format used by TrialEligibilityService
    and converts each criterion entry into a ParsedCriterion for validation.
    """
    from app.schemas.criteria_fidelity import CriterionType, Operator

    criteria: list[ParsedCriterion] = []

    inclusion = trial.inclusion_criteria or {}
    exclusion = trial.exclusion_criteria or {}

    for criterion_dict in inclusion.get("criteria", []):
        parsed = _dict_to_parsed_criterion(criterion_dict, is_exclusion=False)
        criteria.append(parsed)

    for criterion_dict in exclusion.get("criteria", []):
        parsed = _dict_to_parsed_criterion(criterion_dict, is_exclusion=True)
        criteria.append(parsed)

    return criteria


def _dict_to_parsed_criterion(d: dict, *, is_exclusion: bool = False) -> ParsedCriterion:
    """Convert a trial criterion dict to a ParsedCriterion."""
    from app.schemas.criteria_fidelity import CriterionType, Operator

    ctype_map = {
        "condition": CriterionType.CONDITION,
        "measurement": CriterionType.MEASUREMENT,
        "demographic": CriterionType.DEMOGRAPHIC,
        "medication": CriterionType.MEDICATION,
        "drug": CriterionType.MEDICATION,
        "procedure": CriterionType.PROCEDURE,
    }

    domain_map = {
        CriterionType.CONDITION: "Condition",
        CriterionType.MEASUREMENT: "Measurement",
        CriterionType.DEMOGRAPHIC: "Demographic",
        CriterionType.MEDICATION: "Drug",
        CriterionType.PROCEDURE: "Procedure",
    }

    ctype = ctype_map.get(d.get("criterion_type", ""), CriterionType.CONDITION)
    domain = domain_map.get(ctype, "Condition")
    name = d.get("name", "Unknown")
    codes = d.get("codes", [])
    concept_terms = [c["display"] for c in codes if c.get("display")]
    if not concept_terms:
        concept_terms = [name]

    # Determine operator and values
    operator = Operator.EXISTS
    value = None
    value_high = None
    unit = None
    warnings: list[str] = []

    if ctype == CriterionType.DEMOGRAPHIC:
        age_range = d.get("age_range", {})
        min_age = age_range.get("min_age")
        max_age = age_range.get("max_age")
        concept_terms = ["Age"]
        unit = "years"
        if min_age is not None and max_age is not None:
            operator = Operator.BETWEEN
            value = min_age
            value_high = max_age
        elif min_age is not None:
            operator = Operator.GREATER_THAN
            value = min_age
        elif max_age is not None:
            operator = Operator.LESS_THAN
            value = max_age

    elif ctype == CriterionType.MEASUREMENT:
        vr = d.get("value_range", {})
        min_val = vr.get("min_value")
        max_val = vr.get("max_value")
        if min_val is not None and max_val is not None:
            operator = Operator.BETWEEN
            value = min_val
            value_high = max_val
        elif min_val is not None:
            operator = Operator.GREATER_THAN
            value = min_val
        elif max_val is not None:
            operator = Operator.LESS_THAN
            value = max_val

    return ParsedCriterion(
        original_text=name,
        criterion_type=ctype,
        domain=domain,
        concept_terms=concept_terms,
        operator=operator,
        value=value,
        value_high=value_high,
        unit=unit,
        is_exclusion=is_exclusion,
        confidence=1.0,
        parse_warnings=warnings,
    )
