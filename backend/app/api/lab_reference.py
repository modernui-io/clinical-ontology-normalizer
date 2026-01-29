"""Lab Reference Range API endpoints.

Provides endpoints for looking up lab reference ranges and interpreting
laboratory values for clinical decision support.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.lab_reference import (
    get_lab_reference_service,
    LabCategory,
    InterpretationLevel,
    ReferenceRange,
    LabInterpretation,
)

router = APIRouter(prefix="/lab-reference", tags=["Lab Reference"])


# ============================================================================
# Response Models
# ============================================================================


class ReferenceRangeResponse(BaseModel):
    """Response model for a lab reference range."""

    test_name: str = Field(..., description="Full test name")
    test_code: str = Field(..., description="Test code (LOINC or abbreviation)")
    category: str = Field(..., description="Lab category")
    unit: str = Field(..., description="Unit of measurement")
    low_normal: float = Field(..., description="Lower bound of normal range")
    high_normal: float = Field(..., description="Upper bound of normal range")
    low_critical: float | None = Field(None, description="Critical low threshold")
    high_critical: float | None = Field(None, description="Critical high threshold")
    gender_specific: bool = Field(default=False, description="Whether ranges differ by gender")
    male_low: float | None = Field(None, description="Male-specific lower bound")
    male_high: float | None = Field(None, description="Male-specific upper bound")
    female_low: float | None = Field(None, description="Female-specific lower bound")
    female_high: float | None = Field(None, description="Female-specific upper bound")
    notes: str = Field(default="", description="Clinical notes")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")

    model_config = {
        "json_schema_extra": {
            "example": {
                "test_name": "Sodium",
                "test_code": "Na",
                "category": "electrolyte",
                "unit": "mEq/L",
                "low_normal": 136,
                "high_normal": 145,
                "low_critical": 120,
                "high_critical": 160,
                "gender_specific": False,
                "notes": "Serum sodium; reflects fluid balance",
                "aliases": ["na", "sodium", "serum sodium", "na+"],
            }
        }
    }


class InterpretationResponse(BaseModel):
    """Response model for lab value interpretation."""

    test_name: str = Field(..., description="Test name")
    value: float = Field(..., description="Input value")
    unit: str = Field(..., description="Unit of measurement")
    level: str = Field(..., description="Interpretation level")
    reference_range: str = Field(..., description="Normal range (e.g., '136-145')")
    is_critical: bool = Field(..., description="Whether value is critical")
    clinical_significance: str = Field(..., description="Clinical significance")
    possible_causes: list[str] = Field(default_factory=list, description="Possible causes")
    recommended_actions: list[str] = Field(default_factory=list, description="Recommended actions")

    model_config = {
        "json_schema_extra": {
            "example": {
                "test_name": "Sodium",
                "value": 128,
                "unit": "mEq/L",
                "level": "low",
                "reference_range": "136-145",
                "is_critical": False,
                "clinical_significance": "Low Sodium - may indicate underlying condition",
                "possible_causes": ["SIADH", "Diuretics", "Heart failure"],
                "recommended_actions": ["Correlate with clinical presentation", "Consider repeat testing"],
            }
        }
    }


class InterpretRequest(BaseModel):
    """Request model for interpreting a lab value."""

    test: str = Field(..., min_length=1, description="Test name, code, or alias")
    value: float = Field(..., description="Numeric lab value")
    gender: str | None = Field(None, description="Patient gender (male/female)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "test": "sodium",
                "value": 128,
                "gender": "female",
            }
        }
    }


class PanelInterpretRequest(BaseModel):
    """Request model for interpreting multiple lab values."""

    values: dict[str, float] = Field(..., description="Dict of test name/code to value")
    gender: str | None = Field(None, description="Patient gender (male/female)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "values": {
                    "Na": 128,
                    "K": 5.2,
                    "Glucose": 95,
                    "Hgb": 10.5,
                },
                "gender": "female",
            }
        }
    }


class CategoryResponse(BaseModel):
    """Response model for a lab category."""

    value: str = Field(..., description="Category value/code")
    name: str = Field(..., description="Display name")
    test_count: int = Field(..., description="Number of tests in category")


class TestListResponse(BaseModel):
    """Response model for list of lab tests."""

    total: int = Field(..., description="Total number of tests")
    tests: list[ReferenceRangeResponse] = Field(..., description="List of tests")


class StatsResponse(BaseModel):
    """Response model for lab reference statistics."""

    total_tests: int = Field(..., description="Total number of lab tests")
    by_category: dict[str, int] = Field(..., description="Test count by category")
    gender_specific_count: int = Field(..., description="Tests with gender-specific ranges")
    with_critical_ranges: int = Field(..., description="Tests with critical thresholds")
    total_aliases: int = Field(..., description="Total number of aliases")


# ============================================================================
# Helper Functions
# ============================================================================


def _reference_to_response(ref: ReferenceRange) -> ReferenceRangeResponse:
    """Convert ReferenceRange to response model."""
    return ReferenceRangeResponse(
        test_name=ref.test_name,
        test_code=ref.test_code,
        category=ref.category.value,
        unit=ref.unit,
        low_normal=ref.low_normal,
        high_normal=ref.high_normal,
        low_critical=ref.low_critical,
        high_critical=ref.high_critical,
        gender_specific=ref.gender_specific,
        male_low=ref.male_low,
        male_high=ref.male_high,
        female_low=ref.female_low,
        female_high=ref.female_high,
        notes=ref.notes,
        aliases=ref.aliases,
    )


def _interpretation_to_response(interp: LabInterpretation) -> InterpretationResponse:
    """Convert LabInterpretation to response model."""
    return InterpretationResponse(
        test_name=interp.test_name,
        value=interp.value,
        unit=interp.unit,
        level=interp.level.value,
        reference_range=interp.reference_range,
        is_critical=interp.is_critical,
        clinical_significance=interp.clinical_significance,
        possible_causes=interp.possible_causes,
        recommended_actions=interp.recommended_actions,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/tests",
    response_model=TestListResponse,
    summary="List all lab tests",
    description="Get a list of all available lab tests with their reference ranges.",
)
async def list_tests(
    category: str | None = Query(
        None,
        description="Filter by category (chemistry, hematology, cardiac, etc.)",
    ),
) -> TestListResponse:
    """List all lab tests, optionally filtered by category."""
    service = get_lab_reference_service()

    # Convert category string to enum if provided
    cat_enum = None
    if category:
        try:
            cat_enum = LabCategory(category.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category}. Valid categories: {[c.value for c in LabCategory]}",
            )

    references = service.get_all_references(cat_enum)
    tests = [_reference_to_response(ref) for ref in references]

    return TestListResponse(
        total=len(tests),
        tests=tests,
    )


@router.get(
    "/tests/{code}",
    response_model=ReferenceRangeResponse,
    summary="Get test by code",
    description="Get reference range for a specific lab test by code or alias.",
)
async def get_test(code: str) -> ReferenceRangeResponse:
    """Get reference range for a specific lab test."""
    service = get_lab_reference_service()
    ref = service.get_reference(code)

    if not ref:
        raise HTTPException(
            status_code=404,
            detail=f"Lab test not found: {code}",
        )

    return _reference_to_response(ref)


@router.get(
    "/search",
    response_model=TestListResponse,
    summary="Search lab tests",
    description="Search for lab tests by name or alias.",
)
async def search_tests(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
) -> TestListResponse:
    """Search for lab tests by name or alias."""
    service = get_lab_reference_service()
    results = service.search(q, limit=limit)
    tests = [_reference_to_response(ref) for ref in results]

    return TestListResponse(
        total=len(tests),
        tests=tests,
    )


@router.post(
    "/interpret",
    response_model=InterpretationResponse,
    summary="Interpret a lab value",
    description="Interpret a single lab value and get clinical guidance.",
)
async def interpret_value(request: InterpretRequest) -> InterpretationResponse:
    """Interpret a single lab value."""
    service = get_lab_reference_service()
    interpretation = service.interpret(
        test=request.test,
        value=request.value,
        gender=request.gender,
    )

    if not interpretation:
        raise HTTPException(
            status_code=404,
            detail=f"Lab test not found: {request.test}",
        )

    return _interpretation_to_response(interpretation)


@router.post(
    "/interpret-panel",
    response_model=list[InterpretationResponse],
    summary="Interpret multiple lab values",
    description="Interpret a panel of lab values and get clinical guidance for each.",
)
async def interpret_panel(request: PanelInterpretRequest) -> list[InterpretationResponse]:
    """Interpret multiple lab values as a panel."""
    service = get_lab_reference_service()
    interpretations = service.interpret_panel(
        values=request.values,
        gender=request.gender,
    )

    return [_interpretation_to_response(interp) for interp in interpretations]


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List lab categories",
    description="Get a list of all lab test categories with test counts.",
)
async def list_categories() -> list[CategoryResponse]:
    """List all lab test categories."""
    service = get_lab_reference_service()
    stats = service.get_stats()
    by_category = stats.get("by_category", {})

    categories = []
    for cat in LabCategory:
        count = by_category.get(cat.value, 0)
        categories.append(
            CategoryResponse(
                value=cat.value,
                name=cat.value.replace("_", " ").title(),
                test_count=count,
            )
        )

    return categories


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get lab reference statistics",
    description="Get statistics about the lab reference database.",
)
async def get_stats() -> StatsResponse:
    """Get lab reference database statistics."""
    service = get_lab_reference_service()
    stats = service.get_stats()

    return StatsResponse(
        total_tests=stats.get("total_tests", 0),
        by_category=stats.get("by_category", {}),
        gender_specific_count=stats.get("gender_specific_count", 0),
        with_critical_ranges=stats.get("with_critical_ranges", 0),
        total_aliases=stats.get("total_aliases", 0),
    )
