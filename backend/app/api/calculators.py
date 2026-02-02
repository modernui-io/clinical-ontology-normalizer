"""Clinical Calculator API Endpoints.

Provides API for clinical calculators:
- List all calculators with categories
- Get calculator details and input schema
- Execute calculators with validation
- User favorites management
- Custom calculator creation (via calculator builder)

Categories:
- Cardiovascular: ASCVD, Framingham, HEART, CHA2DS2-VASc, HAS-BLED
- Renal: CKD-EPI eGFR, Cockcroft-Gault, UACR
- Hepatic: MELD, Child-Pugh, FIB-4
- Critical Care: SOFA, qSOFA, Wells PE/DVT
- General: BMI, BSA, Corrected Calcium, Anion Gap
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status, Header, Path
from pydantic import BaseModel, Field
from app.schemas.calculators import (
    DataDrivenCalculationResponse,
    DataDrivenCalculatorDetail,
    DataDrivenCalculatorListResponse,
)

router = APIRouter(prefix="/calculators", tags=["Clinical Calculators"])

# Create a separate router for clinical calculators to avoid route conflicts
clinical_router = APIRouter(prefix="/calculators/clinical", tags=["Clinical Calculators"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CalculatorInputDefinition(BaseModel):
    """Definition of a calculator input parameter."""

    name: str = Field(..., min_length=1, max_length=50, description="Variable name (used in formula as $name)")
    type: str = Field(
        default="number",
        description="Input type: number, integer, boolean, select, radio",
    )
    label: str = Field(..., min_length=1, max_length=100, description="Display label")
    unit: str | None = Field(None, max_length=50, description="Unit of measurement (e.g., kg, mL/min)")
    min_value: float | None = Field(None, description="Minimum allowed value")
    max_value: float | None = Field(None, description="Maximum allowed value")
    default_value: float | None = Field(None, description="Default value if not provided")
    required: bool = Field(default=True, description="Whether input is required")
    options: list[dict[str, Any]] | None = Field(
        None, description="Options for select/radio type (e.g., [{'value': 1, 'label': 'Yes'}])"
    )
    description: str | None = Field(None, max_length=500, description="Help text for the input")


class InterpretationRule(BaseModel):
    """Rule for interpreting calculator results."""

    min_value: float | None = Field(None, alias="min", description="Minimum value (inclusive)")
    max_value: float | None = Field(None, alias="max", description="Maximum value (exclusive)")
    label: str = Field(..., description="Interpretation label (e.g., 'Normal', 'High')")
    risk_level: str = Field(
        default="low",
        description="Risk level: low, low_moderate, moderate, moderate_high, high, very_high",
    )

    class Config:
        populate_by_name = True


class CreateCalculatorRequest(BaseModel):
    """Request to create a new custom calculator."""

    name: str = Field(..., min_length=1, max_length=255, description="Calculator name")
    description: str | None = Field(None, max_length=2000, description="Calculator description")
    formula: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Formula using safe DSL. Variables as $name, supports: +,-,*,/,^,if(),min(),max(),etc.",
    )
    inputs: list[CalculatorInputDefinition] = Field(
        ..., min_length=1, max_length=20, description="Input parameter definitions"
    )
    output_type: str = Field(
        default="number",
        description="Output type: number, integer, percentage, category, score",
    )
    output_unit: str | None = Field(None, max_length=50, description="Unit for output value")
    interpretation_rules: list[InterpretationRule] | None = Field(
        None, description="Rules for interpreting results by value ranges"
    )
    recommendations: dict[str, list[str]] | None = Field(
        None, description="Recommendations keyed by risk_level"
    )
    references: list[str] | None = Field(None, max_length=20, description="Citation references")
    category: str | None = Field(None, max_length=100, description="Category for organization")


class UpdateCalculatorRequest(BaseModel):
    """Request to update an existing calculator."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    formula: str | None = Field(None, min_length=1, max_length=5000)
    inputs: list[CalculatorInputDefinition] | None = Field(None, min_length=1, max_length=20)
    output_type: str | None = None
    output_unit: str | None = None
    interpretation_rules: list[InterpretationRule] | None = None
    recommendations: dict[str, list[str]] | None = None
    references: list[str] | None = None
    category: str | None = None


class ExecuteCalculatorRequest(BaseModel):
    """Request to execute a calculator."""

    inputs: dict[str, Any] = Field(..., description="Input values keyed by input name")
    patient_id: str | None = Field(None, description="Optional patient ID for audit trail")


class ValidateFormulaRequest(BaseModel):
    """Request to validate a formula."""

    formula: str = Field(..., min_length=1, max_length=5000, description="Formula to validate")
    variables: list[str] | None = Field(None, description="Expected variable names")


class CalculatorSummary(BaseModel):
    """Summary of a calculator for list responses."""

    id: str
    name: str
    description: str | None
    category: str | None
    is_builtin: bool
    output_type: str
    output_unit: str | None
    input_count: int


class CalculatorDetails(BaseModel):
    """Full details of a calculator."""

    id: str
    name: str
    description: str | None
    formula: str
    inputs: list[dict[str, Any]]
    output_type: str
    output_unit: str | None
    interpretation_rules: list[dict[str, Any]] | None
    recommendations: dict[str, list[str]] | None
    references: list[str] | None
    category: str | None
    is_builtin: bool
    created_by: str | None
    created_at: str | None
    updated_at: str | None
    version: int


class ExecutionResult(BaseModel):
    """Result from executing a calculator."""

    calculator_id: str
    calculator_name: str
    score: float
    score_unit: str | None
    risk_level: str | None
    interpretation: str | None
    recommendations: list[str]
    components: dict[str, Any]
    references: list[str]
    execution_time_ms: float
    inputs_used: dict[str, Any]


class FormulaValidationResponse(BaseModel):
    """Response from formula validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    variables_used: list[str]
    functions_used: list[str]


class ListCalculatorsResponse(BaseModel):
    """Response for list calculators endpoint."""

    calculators: list[CalculatorSummary]
    total_count: int
    builtin_count: int
    custom_count: int


class CreateCalculatorResponse(BaseModel):
    """Response from creating a calculator."""

    id: str
    message: str
    calculator: CalculatorSummary


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=ListCalculatorsResponse,
    summary="List all calculators",
    description="Get a list of all available calculators (built-in and custom).",
)
async def list_calculators(
    category: str | None = Query(None, description="Filter by category"),
    include_builtin: bool = Query(True, description="Include built-in calculators"),
    include_custom: bool = Query(True, description="Include custom calculators"),
) -> ListCalculatorsResponse:
    """List all available calculators.

    Returns both built-in and custom calculators with basic information.
    Use GET /calculators/{id} for full details including formula.
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()
    calculators = service.list_calculators(
        category=category,
        include_builtin=include_builtin,
        include_custom=include_custom,
    )

    builtin_count = sum(1 for c in calculators if c["is_builtin"])
    custom_count = len(calculators) - builtin_count

    return ListCalculatorsResponse(
        calculators=[CalculatorSummary(**c) for c in calculators],
        total_count=len(calculators),
        builtin_count=builtin_count,
        custom_count=custom_count,
    )


@router.post(
    "",
    response_model=CreateCalculatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom calculator",
    description="Create a new custom calculator with a formula using the safe DSL.",
)
async def create_calculator(request: CreateCalculatorRequest) -> CreateCalculatorResponse:
    """Create a new custom calculator.

    The formula uses a safe DSL that supports:
    - **Variables**: $weight, $height, etc. (reference input values)
    - **Operators**: +, -, *, /, ^ (power)
    - **Comparisons**: <, >, <=, >=, ==, !=
    - **Logical**: and, or, not
    - **Functions**: min(), max(), abs(), round(), sqrt(), log(), pow(), exp(), if()

    Example formulas:
    - BMI: `$weight / ($height / 100) ^ 2`
    - Renal dosing: `if($egfr < 30, $dose * 0.5, if($egfr < 60, $dose * 0.75, $dose))`
    - Anion gap: `$sodium - ($chloride + $bicarbonate)`
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()

    # Convert interpretation rules
    interp_rules = None
    if request.interpretation_rules:
        interp_rules = [
            {
                "min": r.min_value,
                "max": r.max_value,
                "label": r.label,
                "risk_level": r.risk_level,
            }
            for r in request.interpretation_rules
        ]

    try:
        calc_id = service.create_calculator(
            name=request.name,
            formula=request.formula,
            inputs=[inp.model_dump() for inp in request.inputs],
            description=request.description,
            output_type=request.output_type,
            output_unit=request.output_unit,
            interpretation_rules=interp_rules,
            recommendations=request.recommendations,
            references=request.references,
            category=request.category,
        )

        calc = service.get_calculator(calc_id)
        if not calc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Calculator created but could not be loaded",
            )

        return CreateCalculatorResponse(
            id=calc_id,
            message="Calculator created successfully",
            calculator=CalculatorSummary(
                id=calc_id,
                name=calc["name"],
                description=calc.get("description"),
                category=calc.get("category"),
                is_builtin=False,
                output_type=calc.get("output_type", "number"),
                output_unit=calc.get("output_unit"),
                input_count=len(calc.get("inputs", [])),
            ),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{calculator_id}",
    response_model=CalculatorDetails,
    summary="Get calculator details",
    description="Get full details of a calculator including formula and input definitions.",
)
async def get_calculator(calculator_id: str) -> CalculatorDetails:
    """Get full details of a specific calculator.

    Returns the complete calculator definition including:
    - Formula
    - Input definitions with validation rules
    - Interpretation rules
    - Recommendations
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()
    calc = service.get_calculator(calculator_id)

    if not calc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculator not found: {calculator_id}",
        )

    return CalculatorDetails(
        id=calc["id"],
        name=calc["name"],
        description=calc.get("description"),
        formula=calc["formula"],
        inputs=calc.get("inputs", []),
        output_type=calc.get("output_type", "number"),
        output_unit=calc.get("output_unit"),
        interpretation_rules=calc.get("interpretation_rules"),
        recommendations=calc.get("recommendations"),
        references=calc.get("references"),
        category=calc.get("category"),
        is_builtin=calc.get("is_builtin", False),
        created_by=calc.get("created_by"),
        created_at=calc.get("created_at"),
        updated_at=calc.get("updated_at"),
        version=calc.get("version", 1),
    )


@router.put(
    "/{calculator_id}",
    response_model=CalculatorDetails,
    summary="Update calculator",
    description="Update an existing custom calculator. Built-in calculators cannot be modified.",
)
async def update_calculator(calculator_id: str, request: UpdateCalculatorRequest) -> CalculatorDetails:
    """Update an existing custom calculator.

    Only custom calculators can be updated. Built-in calculators are read-only.

    Partial updates are supported - only fields included in the request
    will be modified.
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()

    # Build updates dict
    updates: dict[str, Any] = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.formula is not None:
        updates["formula"] = request.formula
    if request.inputs is not None:
        updates["inputs"] = [inp.model_dump() for inp in request.inputs]
    if request.output_type is not None:
        updates["output_type"] = request.output_type
    if request.output_unit is not None:
        updates["output_unit"] = request.output_unit
    if request.interpretation_rules is not None:
        updates["interpretation_rules"] = [
            {
                "min": r.min_value,
                "max": r.max_value,
                "label": r.label,
                "risk_level": r.risk_level,
            }
            for r in request.interpretation_rules
        ]
    if request.recommendations is not None:
        updates["recommendations"] = request.recommendations
    if request.references is not None:
        updates["references"] = request.references
    if request.category is not None:
        updates["category"] = request.category

    try:
        service.update_calculator(calculator_id, updates)
        return cast(CalculatorDetails, await get_calculator(calculator_id))

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        elif "built-in" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )


@router.delete(
    "/{calculator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete calculator",
    description="Delete a custom calculator. Built-in calculators cannot be deleted.",
)
async def delete_calculator(calculator_id: str) -> None:
    """Delete a custom calculator.

    Only custom calculators can be deleted. Built-in calculators are permanent.
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()

    try:
        service.delete_calculator(calculator_id)

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        elif "built-in" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )


@router.post(
    "/{calculator_id}/execute",
    response_model=ExecutionResult,
    summary="Execute calculator",
    description="Run a calculator with provided input values.",
)
async def execute_calculator(
    calculator_id: str,
    request: ExecuteCalculatorRequest,
) -> ExecutionResult:
    """Execute a calculator with input values.

    Validates inputs against the calculator's input definitions
    and returns the computed result with interpretation.

    Example:
    ```json
    {
        "inputs": {
            "weight": 70,
            "height": 175
        },
        "patient_id": "optional-patient-id"
    }
    ```
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()

    try:
        result = service.execute_calculator(
            calculator_id=calculator_id,
            input_values=request.inputs,
            patient_id=request.patient_id,
        )

        return ExecutionResult(
            calculator_id=result.calculator_id,
            calculator_name=result.calculator_name,
            score=result.score,
            score_unit=result.score_unit,
            risk_level=result.risk_level,
            interpretation=result.interpretation,
            recommendations=result.recommendations,
            components=result.components,
            references=result.references,
            execution_time_ms=result.execution_time_ms,
            inputs_used=result.inputs_used,
        )

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )


@router.post(
    "/validate",
    response_model=FormulaValidationResponse,
    summary="Validate formula",
    description="Validate a formula without creating a calculator.",
)
async def validate_formula(request: ValidateFormulaRequest) -> FormulaValidationResponse:
    """Validate a formula string.

    Checks for:
    - Syntax errors
    - Unknown functions
    - Variable usage
    - Mathematical validity

    Use this to test formulas before creating a calculator.
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()
    result = service.validate_formula(request.formula, request.variables)

    return FormulaValidationResponse(
        is_valid=result.is_valid,
        errors=result.errors,
        warnings=result.warnings,
        variables_used=result.variables_used,
        functions_used=result.functions_used,
    )


@router.get(
    "/categories/list",
    response_model=list[str],
    summary="List categories",
    description="Get list of all calculator categories.",
)
async def list_categories() -> list[str]:
    """Get all calculator categories.

    Returns a list of unique categories used by calculators.
    """
    from app.services.calculator_builder import get_calculator_builder_service

    service = get_calculator_builder_service()
    stats = service.get_stats()
    return cast(list[str], stats.get("categories", []))


@router.get(
    "/examples/formulas",
    summary="Get formula examples",
    description="Get example formulas to help with calculator creation.",
)
async def get_formula_examples() -> dict[str, Any]:
    """Get example formulas and syntax help.

    Returns examples of valid formulas and documentation
    for the formula DSL.
    """
    return {
        "syntax": {
            "variables": "$variable_name (e.g., $weight, $age, $egfr)",
            "operators": {
                "arithmetic": "+ - * / ^ (power)",
                "comparison": "< > <= >= == !=",
                "logical": "and, or, not",
            },
            "functions": {
                "math": "min(), max(), abs(), round(), sqrt(), log(), log10(), pow(), exp()",
                "trig": "sin(), cos(), tan()",
                "rounding": "floor(), ceil(), round()",
                "conditional": "if(condition, true_value, false_value)",
            },
        },
        "examples": [
            {
                "name": "BMI",
                "formula": "$weight / ($height / 100) ^ 2",
                "description": "Body Mass Index",
            },
            {
                "name": "Renal Dose Adjustment",
                "formula": "if($egfr < 30, $dose * 0.5, if($egfr < 60, $dose * 0.75, $dose))",
                "description": "Adjust medication dose based on kidney function",
            },
            {
                "name": "Anion Gap",
                "formula": "$sodium - ($chloride + $bicarbonate)",
                "description": "Serum anion gap calculation",
            },
            {
                "name": "Corrected Calcium",
                "formula": "$calcium + 0.8 * (4 - $albumin)",
                "description": "Albumin-corrected calcium",
            },
            {
                "name": "Mean Arterial Pressure",
                "formula": "($sbp + 2 * $dbp) / 3",
                "description": "MAP from systolic and diastolic pressures",
            },
            {
                "name": "Creatinine Clearance (Cockcroft-Gault)",
                "formula": "((140 - $age) * $weight * if($female, 0.85, 1)) / (72 * $creatinine)",
                "description": "Estimated creatinine clearance",
            },
            {
                "name": "Ideal Body Weight (Male)",
                "formula": "50 + 2.3 * ($height_inches - 60)",
                "description": "IBW in kg for males",
            },
            {
                "name": "Complex Conditional",
                "formula": "if($score > 5 and $age > 65, 'high', if($score > 3, 'moderate', 'low'))",
                "description": "Multi-level risk stratification",
            },
        ],
        "tips": [
            "Use parentheses to ensure correct order of operations",
            "Variable names are case-sensitive",
            "Division by zero will return an error",
            "Boolean inputs are treated as 1 (true) or 0 (false)",
            "Use nested if() statements for multiple conditions",
        ],
    }


# =============================================================================
# Clinical Calculator Endpoints (using clinical_calculator_service)
# =============================================================================


class ClinicalCalculatorSummary(BaseModel):
    """Summary of a clinical calculator."""
    id: str
    name: str
    short_name: str
    category: str
    description: str


class ClinicalCalculatorDetail(BaseModel):
    """Detailed clinical calculator with input schema."""
    id: str
    name: str
    short_name: str
    category: str
    description: str
    inputs: dict[str, Any]
    required: list[str]


class ClinicalCalculationRequest(BaseModel):
    """Request to execute a clinical calculator."""
    inputs: dict[str, Any] = Field(..., description="Input values keyed by parameter name")


class ClinicalCalculationResult(BaseModel):
    """Result from a clinical calculation."""
    calculator_id: str
    calculator_name: str
    score: float
    score_unit: str
    risk_level: str
    interpretation: str
    recommendations: list[str]
    components: dict[str, Any]
    references: list[str]
    formula_used: str = ""
    warnings: list[str] = []


class CategoryInfo(BaseModel):
    """Category information with calculator count."""
    id: str
    name: str
    count: int


class ListClinicalCalculatorsResponse(BaseModel):
    """Response for listing clinical calculators."""
    calculators: list[ClinicalCalculatorSummary]
    total_count: int
    categories: list[CategoryInfo]


class FavoriteToggleResponse(BaseModel):
    """Response from toggling favorite status."""
    calculator_id: str
    is_favorite: bool
    message: str


@clinical_router.get(
    "",
    response_model=ListClinicalCalculatorsResponse,
    summary="List clinical calculators",
    description="Get all validated clinical calculators grouped by category.",
)
async def list_clinical_calculators(
    category: str | None = Query(None, description="Filter by category"),
) -> ListClinicalCalculatorsResponse:
    """List all available clinical calculators.

    Returns validated clinical calculators including:
    - Cardiovascular risk scores (ASCVD, HEART, CHA2DS2-VASc, etc.)
    - Renal function calculators (eGFR, CrCl, UACR)
    - Hepatic scores (MELD, Child-Pugh, FIB-4)
    - Critical care scores (SOFA, qSOFA, Wells)
    - General calculators (BMI, BSA, Anion Gap)
    """
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()
    calculators = service.list_calculators(category=category)
    categories = service.get_categories()

    return ListClinicalCalculatorsResponse(
        calculators=[ClinicalCalculatorSummary(**c) for c in calculators],
        total_count=len(calculators),
        categories=[CategoryInfo(**cat) for cat in categories],
    )


@clinical_router.get(
    "/{calculator_id}",
    response_model=ClinicalCalculatorDetail,
    summary="Get clinical calculator details",
    description="Get detailed information about a clinical calculator including input schema.",
)
async def get_clinical_calculator(calculator_id: str) -> ClinicalCalculatorDetail:
    """Get details of a specific clinical calculator.

    Returns the calculator definition including:
    - Input parameter schema with types and validation rules
    - Description and references
    - Category information
    """
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()
    calc = service.get_calculator(calculator_id)

    if not calc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculator not found: {calculator_id}",
        )

    return ClinicalCalculatorDetail(**calc)


@clinical_router.post(
    "/{calculator_id}/calculate",
    response_model=ClinicalCalculationResult,
    summary="Execute clinical calculator",
    description="Run a clinical calculator with provided input values.",
)
async def execute_clinical_calculator(
    calculator_id: str,
    request: ClinicalCalculationRequest,
) -> ClinicalCalculationResult:
    """Execute a clinical calculator.

    Validates inputs and computes the clinical score with:
    - Risk interpretation
    - Clinical recommendations
    - Component breakdown
    - References

    Example for BMI:
    ```json
    {
        "inputs": {
            "weight_kg": 70,
            "height_cm": 175
        }
    }
    ```

    Example for CHA2DS2-VASc:
    ```json
    {
        "inputs": {
            "age": 72,
            "sex": "female",
            "chf": false,
            "hypertension": true,
            "diabetes": true,
            "stroke_tia": false,
            "vascular_disease": true
        }
    }
    ```
    """
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()

    try:
        result = service.calculate(calculator_id, request.inputs)
        return ClinicalCalculationResult(
            calculator_id=result.calculator_id,
            calculator_name=result.calculator_name,
            score=result.score,
            score_unit=result.score_unit,
            risk_level=result.risk_level.value,
            interpretation=result.interpretation,
            recommendations=result.recommendations,
            components=result.components,
            references=result.references,
            formula_used=result.formula_used,
            warnings=result.warnings,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@clinical_router.get(
    "/favorites/list",
    response_model=list[ClinicalCalculatorSummary],
    summary="Get favorite calculators",
    description="Get user's favorite clinical calculators.",
)
async def get_favorite_calculators(
    x_user_id: str = Header(default="anonymous", alias="X-User-ID"),
) -> list[ClinicalCalculatorSummary]:
    """Get user's favorite calculators.

    Returns the list of calculators marked as favorites by the user.
    User is identified by the X-User-ID header.
    """
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()
    favorites = service.get_favorites(x_user_id)

    return [ClinicalCalculatorSummary(**c) for c in favorites]


@clinical_router.post(
    "/{calculator_id}/favorite",
    response_model=FavoriteToggleResponse,
    summary="Toggle favorite status",
    description="Toggle a calculator's favorite status for the user.",
)
async def toggle_calculator_favorite(
    calculator_id: str,
    x_user_id: str = Header(default="anonymous", alias="X-User-ID"),
) -> FavoriteToggleResponse:
    """Toggle favorite status for a calculator.

    If the calculator is currently a favorite, it will be unfavorited.
    If not a favorite, it will be added to favorites.

    User is identified by the X-User-ID header.
    """
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()

    try:
        is_favorite = service.toggle_favorite(x_user_id, calculator_id)
        return FavoriteToggleResponse(
            calculator_id=calculator_id,
            is_favorite=is_favorite,
            message="Added to favorites" if is_favorite else "Removed from favorites",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@clinical_router.get(
    "/categories/list",
    response_model=list[CategoryInfo],
    summary="List calculator categories",
    description="Get all clinical calculator categories with counts.",
)
async def list_clinical_categories() -> list[CategoryInfo]:
    """Get all calculator categories.

    Returns categories with their calculator counts:
    - cardiovascular
    - renal
    - hepatic
    - critical_care
    - general
    - laboratory
    """
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()
    return [CategoryInfo(**cat) for cat in service.get_categories()]


# =============================================================================
# Data-Driven Calculator Endpoints (using calculator_definitions)
# =============================================================================

# Create a separate router for data-driven calculators
data_driven_router = APIRouter(prefix="/calculators/definitions", tags=["Data-Driven Calculators"])


@data_driven_router.get(
    "",
    summary="List all data-driven calculators",
    description="Get a list of all available data-driven clinical calculators.",
)
async def list_data_driven_calculators(
    category: str | None = Query(None, description="Filter by category"),
    calc_type: str | None = Query(None, description="Filter by calculator type (criteria, equation, etc.)"),
) -> DataDrivenCalculatorListResponse:
    """List all data-driven calculators.

    Returns summaries of all available data-driven calculators including:
    - 201 point-based scoring calculators (CHA2DS2-VASc, Wells, CURB-65, etc.)
    - Risk assessment tools
    - Clinical decision support scores

    Supports filtering by category and calculator type.
    """
    from app.schemas.calculators import (
        DataDrivenCalculatorListItem,
        DataDrivenCalculatorListResponse,
    )
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()
    calculators = service.list_data_driven_calculators(category=category, calc_type=calc_type)

    return DataDrivenCalculatorListResponse(
        calculators=[DataDrivenCalculatorListItem(**c) for c in calculators],
        total_count=len(calculators),
    )


@data_driven_router.get(
    "/{calculator_id}",
    summary="Get data-driven calculator definition",
    description="Get full details of a data-driven calculator including all criteria and scoring rules.",
)
async def get_data_driven_calculator(
    calculator_id: str = Path(..., description="Calculator identifier"),
) -> DataDrivenCalculatorDetail:
    """Get detailed definition of a data-driven calculator.

    Returns the complete calculator definition including:
    - Scoring criteria (boolean, multi-level, threshold)
    - Age-based scoring rules (if applicable)
    - Score interpretation thresholds
    - Risk levels and recommendations
    - Literature references

    This endpoint provides all information needed to render the calculator
    form and interpret results on the frontend.
    """
    from app.schemas.calculators import (
        DataDrivenCalculatorDetail,
        InterpretationSchema,
        CalculatorProvenanceSchema,
        CitationSchema,
        ValidationStudySchema,
        ClinicalPearlSchema,
        UsageGuidanceSchema,
        GuidelineReferenceSchema,
    )
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()
    calc = service.get_data_driven_calculator(calculator_id)

    if not calc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data-driven calculator not found: {calculator_id}",
        )

    # Convert interpretations to schema
    interpretations = [
        InterpretationSchema(**interp) for interp in calc.get("interpretations", [])
    ]

    # Convert provenance to schema if present
    provenance_schema = None
    if calc.get("provenance"):
        prov = calc["provenance"]
        provenance_schema = CalculatorProvenanceSchema(
            original_citation=CitationSchema(**prov["original_citation"]) if prov.get("original_citation") else None,
            evidence_level=prov.get("evidence_level"),
            evidence_summary=prov.get("evidence_summary"),
            validation_studies=[
                ValidationStudySchema(
                    citation=CitationSchema(**vs["citation"]),
                    population=vs["population"],
                    sample_size=vs.get("sample_size"),
                    setting=vs.get("setting"),
                    performance_auc=vs.get("performance_auc"),
                    validation_outcome=vs["validation_outcome"],
                    notes=vs.get("notes"),
                )
                for vs in prov.get("validation_studies", [])
            ],
            overall_validation=prov.get("overall_validation"),
            clinical_pearls=[
                ClinicalPearlSchema(**pearl) for pearl in prov.get("clinical_pearls", [])
            ],
            pitfalls=prov.get("pitfalls", []),
            usage_guidance=UsageGuidanceSchema(**prov["usage_guidance"]) if prov.get("usage_guidance") else None,
            related_guidelines=[
                GuidelineReferenceSchema(**g) for g in prov.get("related_guidelines", [])
            ],
            related_calculator_ids=prov.get("related_calculator_ids", []),
            mdcalc_url=prov.get("mdcalc_url"),
        )

    return DataDrivenCalculatorDetail(
        id=calc["id"],
        name=calc["name"],
        short_name=calc["short_name"],
        category=calc["category"],
        calc_type=calc["calc_type"],
        description=calc.get("description", ""),
        score_unit=calc.get("score_unit", "points"),
        criteria=calc.get("criteria", []),
        has_age_scoring=calc.get("has_age_scoring", False),
        interpretations=interpretations,
        references=calc.get("references", []),
        notes=calc.get("notes", []),
        provenance=provenance_schema,
    )


@data_driven_router.post(
    "/{calculator_id}/calculate",
    summary="Calculate using data-driven engine",
    description="Execute a data-driven calculator with provided values.",
)
async def calculate_data_driven(
    calculator_id: str = Path(..., description="Calculator identifier"),
    request: dict[str, Any] | None = None,
) -> DataDrivenCalculationResponse:
    """Execute a data-driven calculator.

    Calculates the score using the data-driven engine and returns:
    - Calculated score with unit
    - Risk level classification
    - Clinical interpretation
    - Recommendations based on score
    - Score component breakdown

    Example request for CHA2DS2-VASc:
    ```json
    {
        "values": {
            "congestive_heart_failure": true,
            "hypertension": true,
            "diabetes_mellitus": false,
            "stroke_tia_thromboembolism": false,
            "vascular_disease": true,
            "sex_female": false
        },
        "age": 72
    }
    ```

    Example request for Wells PE:
    ```json
    {
        "values": {
            "clinical_dvt_signs": true,
            "pe_most_likely": true,
            "heart_rate_over_100": false,
            "immobilization_surgery": false,
            "previous_pe_dvt": true,
            "hemoptysis": false,
            "malignancy": false
        }
    }
    ```
    """
    from app.schemas.calculators import DataDrivenCalculationResponse
    from app.services.clinical_calculator_service import get_clinical_calculator_service

    service = get_clinical_calculator_service()

    # Parse request body
    if request is None:
        request = {}

    values = request.get("values", {})
    age = request.get("age")

    try:
        result = service.calculate_data_driven(calculator_id, values, age)

        return DataDrivenCalculationResponse(
            calculator_id=calculator_id,
            calculator_name=result.calculator_name,
            score=result.score,
            score_unit=result.score_unit,
            risk_level=result.risk_level.value,
            interpretation=result.interpretation,
            recommendations=result.recommendations,
            components=result.components,
            references=result.references,
            warnings=result.warnings,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
