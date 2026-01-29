"""Calculator Builder Service for Custom Clinical Calculators.

Provides safe formula evaluation without using exec/eval on arbitrary code.
Uses a custom DSL parser and evaluator for mathematical expressions.

Supported Features:
- Arithmetic: +, -, *, /, ^ (power)
- Comparison: >, <, >=, <=, ==, !=
- Logical: and, or, not
- Functions: min(), max(), abs(), round(), sqrt(), log(), log10(), pow(), exp()
- Conditional: if(condition, true_value, false_value)
- Variables: $variable_name (references input values)
- Lookup tables: lookup($value, table_name)
"""

import logging
import math
import operator
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


class TokenType(str, Enum):
    """Token types for the formula parser."""

    NUMBER = "NUMBER"
    VARIABLE = "VARIABLE"
    FUNCTION = "FUNCTION"
    OPERATOR = "OPERATOR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    COMPARISON = "COMPARISON"
    LOGICAL = "LOGICAL"
    EOF = "EOF"


@dataclass
class Token:
    """Token produced by the lexer."""

    type: TokenType
    value: Any
    position: int = 0


@dataclass
class FormulaValidationResult:
    """Result of formula validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    variables_used: list[str] = field(default_factory=list)
    functions_used: list[str] = field(default_factory=list)


@dataclass
class CalculatorExecutionResult:
    """Result of executing a calculator."""

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


@dataclass
class CalculatorInputDefinition:
    """Definition of a calculator input parameter."""

    name: str
    type: str  # number, integer, boolean, select, radio
    label: str
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    default_value: Any = None
    required: bool = True
    options: list[dict[str, Any]] | None = None  # For select/radio
    description: str | None = None


@dataclass
class InterpretationRule:
    """Rule for interpreting calculator results."""

    min_value: float | None = None
    max_value: float | None = None
    exact_value: Any = None
    label: str = ""
    risk_level: str = "low"
    recommendations: list[str] = field(default_factory=list)


class FormulaLexer:
    """Tokenizer for formula strings."""

    OPERATORS = {"+", "-", "*", "/", "^"}
    COMPARISONS = {"<", ">", "<=", ">=", "==", "!="}
    LOGICAL = {"and", "or", "not"}
    FUNCTIONS = {
        "min", "max", "abs", "round", "sqrt", "log", "log10", "pow", "exp",
        "if", "floor", "ceil", "sin", "cos", "tan", "lookup"
    }

    def __init__(self, formula: str):
        self.formula = formula
        self.pos = 0
        self.length = len(formula)

    def peek(self, offset: int = 0) -> str | None:
        """Look at character at current position + offset."""
        pos = self.pos + offset
        if pos < self.length:
            return self.formula[pos]
        return None

    def advance(self) -> str | None:
        """Move to next character and return it."""
        if self.pos < self.length:
            char = self.formula[self.pos]
            self.pos += 1
            return char
        return None

    def skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.pos < self.length and self.formula[self.pos].isspace():
            self.pos += 1

    def tokenize(self) -> list[Token]:
        """Convert formula string to tokens."""
        tokens = []

        while self.pos < self.length:
            self.skip_whitespace()
            if self.pos >= self.length:
                break

            start_pos = self.pos
            char = self.formula[self.pos]

            # Numbers (including decimals)
            if char.isdigit() or (char == "." and self.peek(1) and self.peek(1).isdigit()):
                tokens.append(self._read_number())

            # Variables ($name)
            elif char == "$":
                tokens.append(self._read_variable())

            # Parentheses
            elif char == "(":
                tokens.append(Token(TokenType.LPAREN, "(", start_pos))
                self.advance()
            elif char == ")":
                tokens.append(Token(TokenType.RPAREN, ")", start_pos))
                self.advance()

            # Comma
            elif char == ",":
                tokens.append(Token(TokenType.COMMA, ",", start_pos))
                self.advance()

            # Comparison operators (must check before single-char operators)
            elif char in "<>=!":
                tokens.append(self._read_comparison())

            # Operators
            elif char in self.OPERATORS:
                tokens.append(Token(TokenType.OPERATOR, char, start_pos))
                self.advance()

            # Identifiers (functions, logical operators)
            elif char.isalpha() or char == "_":
                tokens.append(self._read_identifier())

            else:
                raise ValueError(f"Unexpected character '{char}' at position {start_pos}")

        tokens.append(Token(TokenType.EOF, None, self.pos))
        return tokens

    def _read_number(self) -> Token:
        """Read a number (integer or float)."""
        start = self.pos
        has_decimal = False

        while self.pos < self.length:
            char = self.formula[self.pos]
            if char.isdigit():
                self.advance()
            elif char == "." and not has_decimal:
                has_decimal = True
                self.advance()
            else:
                break

        value = self.formula[start:self.pos]
        return Token(TokenType.NUMBER, float(value), start)

    def _read_variable(self) -> Token:
        """Read a variable ($name)."""
        start = self.pos
        self.advance()  # Skip $

        var_start = self.pos
        while self.pos < self.length and (self.formula[self.pos].isalnum() or self.formula[self.pos] == "_"):
            self.advance()

        name = self.formula[var_start:self.pos]
        if not name:
            raise ValueError(f"Expected variable name after $ at position {start}")

        return Token(TokenType.VARIABLE, name, start)

    def _read_comparison(self) -> Token:
        """Read a comparison operator."""
        start = self.pos
        char = self.formula[self.pos]
        self.advance()

        # Check for two-character operators
        if self.pos < self.length and self.formula[self.pos] == "=":
            self.advance()
            op = char + "="
        else:
            op = char

        if op not in self.COMPARISONS and op not in {"<", ">"}:
            raise ValueError(f"Invalid comparison operator '{op}' at position {start}")

        return Token(TokenType.COMPARISON, op, start)

    def _read_identifier(self) -> Token:
        """Read an identifier (function name or logical operator)."""
        start = self.pos
        while self.pos < self.length and (self.formula[self.pos].isalnum() or self.formula[self.pos] == "_"):
            self.advance()

        name = self.formula[start:self.pos].lower()

        if name in self.LOGICAL:
            return Token(TokenType.LOGICAL, name, start)
        elif name in self.FUNCTIONS:
            return Token(TokenType.FUNCTION, name, start)
        else:
            raise ValueError(f"Unknown identifier '{name}' at position {start}")


class FormulaParser:
    """Parser for formula tokens into an AST."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Token:
        """Get current token."""
        return self.tokens[self.pos]

    def advance(self) -> Token:
        """Move to next token and return it."""
        token = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        """Expect a specific token type."""
        token = self.current_token()
        if token.type != token_type:
            raise ValueError(f"Expected {token_type.value}, got {token.type.value} at position {token.position}")
        return self.advance()

    def parse(self) -> dict:
        """Parse the formula into an AST."""
        ast = self._parse_logical_or()
        if self.current_token().type != TokenType.EOF:
            raise ValueError(f"Unexpected token at position {self.current_token().position}")
        return ast

    def _parse_logical_or(self) -> dict:
        """Parse logical OR expressions."""
        left = self._parse_logical_and()

        while self.current_token().type == TokenType.LOGICAL and self.current_token().value == "or":
            self.advance()
            right = self._parse_logical_and()
            left = {"type": "logical", "op": "or", "left": left, "right": right}

        return left

    def _parse_logical_and(self) -> dict:
        """Parse logical AND expressions."""
        left = self._parse_logical_not()

        while self.current_token().type == TokenType.LOGICAL and self.current_token().value == "and":
            self.advance()
            right = self._parse_logical_not()
            left = {"type": "logical", "op": "and", "left": left, "right": right}

        return left

    def _parse_logical_not(self) -> dict:
        """Parse logical NOT expressions."""
        if self.current_token().type == TokenType.LOGICAL and self.current_token().value == "not":
            self.advance()
            operand = self._parse_logical_not()
            return {"type": "unary", "op": "not", "operand": operand}

        return self._parse_comparison()

    def _parse_comparison(self) -> dict:
        """Parse comparison expressions."""
        left = self._parse_additive()

        if self.current_token().type == TokenType.COMPARISON:
            op = self.advance().value
            right = self._parse_additive()
            return {"type": "comparison", "op": op, "left": left, "right": right}

        return left

    def _parse_additive(self) -> dict:
        """Parse addition and subtraction."""
        left = self._parse_multiplicative()

        while self.current_token().type == TokenType.OPERATOR and self.current_token().value in "+-":
            op = self.advance().value
            right = self._parse_multiplicative()
            left = {"type": "binary", "op": op, "left": left, "right": right}

        return left

    def _parse_multiplicative(self) -> dict:
        """Parse multiplication and division."""
        left = self._parse_power()

        while self.current_token().type == TokenType.OPERATOR and self.current_token().value in "*/":
            op = self.advance().value
            right = self._parse_power()
            left = {"type": "binary", "op": op, "left": left, "right": right}

        return left

    def _parse_power(self) -> dict:
        """Parse exponentiation (right-associative)."""
        left = self._parse_unary()

        if self.current_token().type == TokenType.OPERATOR and self.current_token().value == "^":
            self.advance()
            right = self._parse_power()  # Right-associative
            return {"type": "binary", "op": "^", "left": left, "right": right}

        return left

    def _parse_unary(self) -> dict:
        """Parse unary operators."""
        if self.current_token().type == TokenType.OPERATOR and self.current_token().value == "-":
            self.advance()
            operand = self._parse_unary()
            return {"type": "unary", "op": "-", "operand": operand}

        return self._parse_primary()

    def _parse_primary(self) -> dict:
        """Parse primary expressions (numbers, variables, functions, parentheses)."""
        token = self.current_token()

        if token.type == TokenType.NUMBER:
            self.advance()
            return {"type": "number", "value": token.value}

        elif token.type == TokenType.VARIABLE:
            self.advance()
            return {"type": "variable", "name": token.value}

        elif token.type == TokenType.FUNCTION:
            return self._parse_function_call()

        elif token.type == TokenType.LPAREN:
            self.advance()
            expr = self._parse_logical_or()
            self.expect(TokenType.RPAREN)
            return expr

        else:
            raise ValueError(f"Unexpected token {token.type.value} at position {token.position}")

    def _parse_function_call(self) -> dict:
        """Parse function call."""
        func_name = self.advance().value
        self.expect(TokenType.LPAREN)

        args = []
        if self.current_token().type != TokenType.RPAREN:
            args.append(self._parse_logical_or())

            while self.current_token().type == TokenType.COMMA:
                self.advance()
                args.append(self._parse_logical_or())

        self.expect(TokenType.RPAREN)
        return {"type": "function", "name": func_name, "args": args}


class FormulaEvaluator:
    """Safe evaluator for formula ASTs."""

    OPERATORS: dict[str, Callable] = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
        "^": operator.pow,
    }

    COMPARISONS: dict[str, Callable] = {
        "<": operator.lt,
        ">": operator.gt,
        "<=": operator.le,
        ">=": operator.ge,
        "==": operator.eq,
        "!=": operator.ne,
    }

    FUNCTIONS: dict[str, Callable] = {
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "pow": pow,
        "exp": math.exp,
        "floor": math.floor,
        "ceil": math.ceil,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
    }

    def __init__(self, variables: dict[str, Any], lookup_tables: dict[str, list[dict]] | None = None):
        self.variables = variables
        self.lookup_tables = lookup_tables or {}

    def evaluate(self, ast: dict) -> float | bool:
        """Evaluate an AST node."""
        node_type = ast["type"]

        if node_type == "number":
            return ast["value"]

        elif node_type == "variable":
            name = ast["name"]
            if name not in self.variables:
                raise ValueError(f"Unknown variable: ${name}")
            return self.variables[name]

        elif node_type == "binary":
            left = self.evaluate(ast["left"])
            right = self.evaluate(ast["right"])
            op = ast["op"]

            if op not in self.OPERATORS:
                raise ValueError(f"Unknown operator: {op}")

            # Handle division by zero
            if op == "/" and right == 0:
                raise ValueError("Division by zero")

            return self.OPERATORS[op](left, right)

        elif node_type == "unary":
            operand = self.evaluate(ast["operand"])
            op = ast["op"]

            if op == "-":
                return -operand
            elif op == "not":
                return not operand
            else:
                raise ValueError(f"Unknown unary operator: {op}")

        elif node_type == "comparison":
            left = self.evaluate(ast["left"])
            right = self.evaluate(ast["right"])
            op = ast["op"]

            if op not in self.COMPARISONS:
                raise ValueError(f"Unknown comparison operator: {op}")

            return self.COMPARISONS[op](left, right)

        elif node_type == "logical":
            op = ast["op"]
            left = self.evaluate(ast["left"])

            if op == "and":
                # Short-circuit evaluation
                if not left:
                    return False
                return bool(self.evaluate(ast["right"]))
            elif op == "or":
                if left:
                    return True
                return bool(self.evaluate(ast["right"]))
            else:
                raise ValueError(f"Unknown logical operator: {op}")

        elif node_type == "function":
            return self._evaluate_function(ast)

        else:
            raise ValueError(f"Unknown node type: {node_type}")

    def _evaluate_function(self, ast: dict) -> float | bool:
        """Evaluate a function call."""
        func_name = ast["name"]
        args = [self.evaluate(arg) for arg in ast["args"]]

        # Special handling for 'if' function
        if func_name == "if":
            if len(args) != 3:
                raise ValueError("if() requires exactly 3 arguments: condition, true_value, false_value")
            condition, true_val, false_val = args
            return true_val if condition else false_val

        # Special handling for 'lookup' function
        if func_name == "lookup":
            if len(args) < 2:
                raise ValueError("lookup() requires at least 2 arguments: value, table_name")
            value = args[0]
            table_name = args[1] if isinstance(args[1], str) else str(args[1])
            return self._lookup_value(value, table_name)

        # Standard math functions
        if func_name in self.FUNCTIONS:
            return self.FUNCTIONS[func_name](*args)

        raise ValueError(f"Unknown function: {func_name}")

    def _lookup_value(self, value: float, table_name: str) -> float:
        """Look up a value in a lookup table."""
        if table_name not in self.lookup_tables:
            raise ValueError(f"Unknown lookup table: {table_name}")

        table = self.lookup_tables[table_name]
        for entry in table:
            min_val = entry.get("min", float("-inf"))
            max_val = entry.get("max", float("inf"))
            if min_val <= value < max_val:
                return entry.get("value", entry.get("score", 0))

        # Return default or last entry
        if table:
            return table[-1].get("value", table[-1].get("score", 0))
        return 0


class CalculatorBuilderService:
    """Service for building and executing custom clinical calculators.

    Features:
    - Safe formula evaluation (no exec/eval)
    - Input validation
    - Result interpretation with risk levels
    - Lookup table support
    - Audit trail for executions

    Usage:
        service = CalculatorBuilderService()

        # Create a calculator
        calc_id = service.create_calculator(
            name="Custom BMI",
            formula="$weight / ($height / 100) ^ 2",
            inputs=[
                {"name": "weight", "type": "number", "label": "Weight", "unit": "kg"},
                {"name": "height", "type": "number", "label": "Height", "unit": "cm"},
            ]
        )

        # Execute it
        result = service.execute_calculator(calc_id, {"weight": 70, "height": 175})
    """

    # Built-in example calculators
    BUILTIN_CALCULATORS: dict[str, dict] = {
        "custom_bmi": {
            "name": "Custom BMI with Categories",
            "description": "Body Mass Index calculator with WHO category classification",
            "formula": "$weight / ($height / 100) ^ 2",
            "output_type": "score",
            "output_unit": "kg/m2",
            "inputs": [
                {
                    "name": "weight",
                    "type": "number",
                    "label": "Weight",
                    "unit": "kg",
                    "min_value": 1,
                    "max_value": 500,
                    "required": True,
                },
                {
                    "name": "height",
                    "type": "number",
                    "label": "Height",
                    "unit": "cm",
                    "min_value": 30,
                    "max_value": 300,
                    "required": True,
                },
            ],
            "interpretation_rules": [
                {"min": 0, "max": 16, "label": "Severe Thinness", "risk_level": "high"},
                {"min": 16, "max": 17, "label": "Moderate Thinness", "risk_level": "moderate_high"},
                {"min": 17, "max": 18.5, "label": "Mild Thinness", "risk_level": "moderate"},
                {"min": 18.5, "max": 25, "label": "Normal", "risk_level": "low"},
                {"min": 25, "max": 30, "label": "Overweight", "risk_level": "moderate"},
                {"min": 30, "max": 35, "label": "Obese Class I", "risk_level": "high"},
                {"min": 35, "max": 40, "label": "Obese Class II", "risk_level": "high"},
                {"min": 40, "max": 1000, "label": "Obese Class III", "risk_level": "very_high"},
            ],
            "recommendations": {
                "high": ["Consult healthcare provider", "Nutritional assessment recommended"],
                "moderate_high": ["Monitor weight regularly", "Consider dietary counseling"],
                "moderate": ["Lifestyle modifications may be beneficial"],
                "low": ["Maintain healthy lifestyle"],
                "very_high": ["Urgent medical evaluation recommended", "Consider specialist referral"],
            },
            "references": ["WHO BMI Classification", "NHLBI Obesity Guidelines"],
            "category": "anthropometric",
            "is_builtin": True,
        },
        "medication_dosing": {
            "name": "Medication Dosing (eGFR-based)",
            "description": "Adjust medication dose based on kidney function (eGFR)",
            "formula": "if($egfr < 15, $base_dose * 0.25, if($egfr < 30, $base_dose * 0.5, if($egfr < 60, $base_dose * 0.75, $base_dose)))",
            "output_type": "number",
            "output_unit": "mg",
            "inputs": [
                {
                    "name": "base_dose",
                    "type": "number",
                    "label": "Base Dose",
                    "unit": "mg",
                    "min_value": 0.1,
                    "max_value": 10000,
                    "required": True,
                },
                {
                    "name": "egfr",
                    "type": "number",
                    "label": "eGFR",
                    "unit": "mL/min/1.73m2",
                    "min_value": 0,
                    "max_value": 200,
                    "required": True,
                },
            ],
            "interpretation_rules": [
                {"min": 0, "max": 25, "label": "Severe Reduction (75%)", "risk_level": "high"},
                {"min": 25, "max": 50, "label": "Moderate Reduction (50%)", "risk_level": "moderate_high"},
                {"min": 50, "max": 75, "label": "Mild Reduction (25%)", "risk_level": "moderate"},
                {"min": 75, "max": 100, "label": "No Adjustment", "risk_level": "low"},
            ],
            "recommendations": {
                "high": [
                    "Significant dose reduction required",
                    "Consider alternative medication",
                    "Monitor for toxicity",
                ],
                "moderate_high": [
                    "50% dose reduction recommended",
                    "Monitor renal function closely",
                ],
                "moderate": [
                    "25% dose reduction may be warranted",
                    "Reassess at next visit",
                ],
                "low": [
                    "Standard dosing appropriate",
                ],
            },
            "references": ["FDA Renal Dosing Guidelines", "Lexicomp Drug Information"],
            "category": "pharmacology",
            "is_builtin": True,
        },
        "anion_gap": {
            "name": "Anion Gap Calculator",
            "description": "Calculate serum anion gap for metabolic acidosis evaluation",
            "formula": "$sodium - ($chloride + $bicarbonate)",
            "output_type": "score",
            "output_unit": "mEq/L",
            "inputs": [
                {
                    "name": "sodium",
                    "type": "number",
                    "label": "Sodium",
                    "unit": "mEq/L",
                    "min_value": 100,
                    "max_value": 180,
                    "required": True,
                },
                {
                    "name": "chloride",
                    "type": "number",
                    "label": "Chloride",
                    "unit": "mEq/L",
                    "min_value": 70,
                    "max_value": 130,
                    "required": True,
                },
                {
                    "name": "bicarbonate",
                    "type": "number",
                    "label": "Bicarbonate (CO2)",
                    "unit": "mEq/L",
                    "min_value": 5,
                    "max_value": 50,
                    "required": True,
                },
            ],
            "interpretation_rules": [
                {"min": -100, "max": 3, "label": "Low (consider lab error)", "risk_level": "moderate"},
                {"min": 3, "max": 12, "label": "Normal", "risk_level": "low"},
                {"min": 12, "max": 20, "label": "Elevated", "risk_level": "moderate"},
                {"min": 20, "max": 100, "label": "High (metabolic acidosis)", "risk_level": "high"},
            ],
            "recommendations": {
                "low": [
                    "Verify lab values for accuracy",
                    "Consider hypoalbuminemia, lithium toxicity, or lab error",
                ],
                "moderate": [
                    "Evaluate for causes of elevated anion gap",
                    "Consider MUDPILES mnemonic",
                ],
                "high": [
                    "Urgent evaluation for high anion gap metabolic acidosis",
                    "Consider: ketoacidosis, lactic acidosis, toxins, renal failure",
                    "Check serum lactate, ketones, and toxicology",
                ],
            },
            "references": ["Seifter JL. NEJM 2014", "Kraut JA, Madias NE. CJASN 2007"],
            "category": "laboratory",
            "is_builtin": True,
        },
        "corrected_calcium": {
            "name": "Corrected Calcium",
            "description": "Calculate albumin-corrected calcium level",
            "formula": "$calcium + 0.8 * (4 - $albumin)",
            "output_type": "score",
            "output_unit": "mg/dL",
            "inputs": [
                {
                    "name": "calcium",
                    "type": "number",
                    "label": "Total Calcium",
                    "unit": "mg/dL",
                    "min_value": 4,
                    "max_value": 20,
                    "required": True,
                },
                {
                    "name": "albumin",
                    "type": "number",
                    "label": "Serum Albumin",
                    "unit": "g/dL",
                    "min_value": 0.5,
                    "max_value": 6,
                    "required": True,
                },
            ],
            "interpretation_rules": [
                {"min": 0, "max": 8.5, "label": "Hypocalcemia", "risk_level": "moderate_high"},
                {"min": 8.5, "max": 10.5, "label": "Normal", "risk_level": "low"},
                {"min": 10.5, "max": 12, "label": "Mild Hypercalcemia", "risk_level": "moderate"},
                {"min": 12, "max": 14, "label": "Moderate Hypercalcemia", "risk_level": "high"},
                {"min": 14, "max": 100, "label": "Severe Hypercalcemia", "risk_level": "very_high"},
            ],
            "recommendations": {
                "moderate_high": [
                    "Evaluate for vitamin D deficiency",
                    "Check PTH level",
                    "Consider calcium supplementation",
                ],
                "low": ["No intervention needed"],
                "moderate": [
                    "Evaluate for primary hyperparathyroidism",
                    "Check PTH and vitamin D levels",
                ],
                "high": [
                    "Urgent evaluation required",
                    "Consider IV hydration",
                    "Evaluate for malignancy or hyperparathyroidism",
                ],
                "very_high": [
                    "Medical emergency - IV hydration and calcitonin",
                    "Consider bisphosphonates",
                    "Evaluate for malignancy",
                ],
            },
            "references": ["Bushinsky DA, Monk RD. Lancet 1998"],
            "category": "laboratory",
            "is_builtin": True,
        },
        "osmolality_calculated": {
            "name": "Calculated Serum Osmolality",
            "description": "Calculate serum osmolality and osmolar gap",
            "formula": "2 * $sodium + $glucose / 18 + $bun / 2.8",
            "output_type": "score",
            "output_unit": "mOsm/kg",
            "inputs": [
                {
                    "name": "sodium",
                    "type": "number",
                    "label": "Sodium",
                    "unit": "mEq/L",
                    "min_value": 100,
                    "max_value": 180,
                    "required": True,
                },
                {
                    "name": "glucose",
                    "type": "number",
                    "label": "Glucose",
                    "unit": "mg/dL",
                    "min_value": 20,
                    "max_value": 2000,
                    "required": True,
                },
                {
                    "name": "bun",
                    "type": "number",
                    "label": "BUN",
                    "unit": "mg/dL",
                    "min_value": 1,
                    "max_value": 200,
                    "required": True,
                },
            ],
            "interpretation_rules": [
                {"min": 0, "max": 275, "label": "Low", "risk_level": "moderate"},
                {"min": 275, "max": 295, "label": "Normal", "risk_level": "low"},
                {"min": 295, "max": 310, "label": "Elevated", "risk_level": "moderate"},
                {"min": 310, "max": 1000, "label": "High", "risk_level": "high"},
            ],
            "recommendations": {
                "low": [
                    "Evaluate for hypotonic hyponatremia",
                    "Assess volume status",
                ],
                "moderate": [
                    "Compare with measured osmolality",
                    "Calculate osmolar gap if needed",
                ],
                "high": [
                    "Evaluate for toxic ingestion if osmolar gap elevated",
                    "Consider hyperosmolar hyperglycemic state",
                ],
            },
            "references": ["Dorwart WV, Chalmers L. Am J Med 1975"],
            "category": "laboratory",
            "is_builtin": True,
        },
    }

    def __init__(self) -> None:
        """Initialize the calculator builder service."""
        # In-memory storage for custom calculators (would be replaced with DB in production)
        self._custom_calculators: dict[str, dict] = {}
        self._execution_history: list[dict] = []

        # Initialize with built-in calculators
        for calc_id, calc_def in self.BUILTIN_CALCULATORS.items():
            self._custom_calculators[calc_id] = {
                "id": calc_id,
                **calc_def,
            }

        logger.info(f"CalculatorBuilderService initialized with {len(self.BUILTIN_CALCULATORS)} built-in calculators")

    def validate_formula(self, formula: str, expected_variables: list[str] | None = None) -> FormulaValidationResult:
        """Validate a formula string.

        Args:
            formula: The formula to validate.
            expected_variables: Optional list of expected variable names.

        Returns:
            FormulaValidationResult with validation status.
        """
        errors = []
        warnings = []
        variables_used = []
        functions_used = []

        try:
            # Tokenize
            lexer = FormulaLexer(formula)
            tokens = lexer.tokenize()

            # Extract variables and functions
            for token in tokens:
                if token.type == TokenType.VARIABLE:
                    if token.value not in variables_used:
                        variables_used.append(token.value)
                elif token.type == TokenType.FUNCTION:
                    if token.value not in functions_used:
                        functions_used.append(token.value)

            # Parse
            parser = FormulaParser(tokens)
            ast = parser.parse()

            # Check for expected variables
            if expected_variables:
                for var in expected_variables:
                    if var not in variables_used:
                        warnings.append(f"Input variable '${var}' is not used in the formula")

                for var in variables_used:
                    if var not in expected_variables:
                        errors.append(f"Unknown variable '${var}' - not in input definitions")

            # Try evaluating with dummy values
            dummy_vars = {var: 1.0 for var in variables_used}
            evaluator = FormulaEvaluator(dummy_vars)
            evaluator.evaluate(ast)

        except Exception as e:
            errors.append(str(e))

        return FormulaValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            variables_used=variables_used,
            functions_used=functions_used,
        )

    def create_calculator(
        self,
        name: str,
        formula: str,
        inputs: list[dict],
        description: str | None = None,
        output_type: str = "number",
        output_unit: str | None = None,
        interpretation_rules: list[dict] | None = None,
        recommendations: dict[str, list[str]] | None = None,
        references: list[str] | None = None,
        category: str | None = None,
        created_by: str | None = None,
    ) -> str:
        """Create a new custom calculator.

        Args:
            name: Calculator name.
            formula: Formula using the safe DSL.
            inputs: List of input definitions.
            description: Optional description.
            output_type: Type of output (number, percentage, category, score).
            output_unit: Unit for the output value.
            interpretation_rules: Rules for interpreting results.
            recommendations: Recommendations keyed by risk level.
            references: Citation references.
            category: Category for organization.
            created_by: User who created the calculator.

        Returns:
            Calculator ID.

        Raises:
            ValueError: If formula is invalid.
        """
        # Extract variable names from inputs
        input_vars = [inp["name"] for inp in inputs]

        # Validate formula
        validation = self.validate_formula(formula, input_vars)
        if not validation.is_valid:
            raise ValueError(f"Invalid formula: {'; '.join(validation.errors)}")

        # Generate ID
        calc_id = str(uuid4())

        # Store calculator
        self._custom_calculators[calc_id] = {
            "id": calc_id,
            "name": name,
            "description": description,
            "formula": formula,
            "inputs": inputs,
            "output_type": output_type,
            "output_unit": output_unit,
            "interpretation_rules": interpretation_rules or [],
            "recommendations": recommendations or {},
            "references": references or [],
            "category": category,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_builtin": False,
            "version": 1,
        }

        logger.info(f"Created custom calculator '{name}' with ID {calc_id}")
        return calc_id

    def update_calculator(self, calculator_id: str, updates: dict) -> bool:
        """Update an existing calculator.

        Args:
            calculator_id: ID of calculator to update.
            updates: Dictionary of fields to update.

        Returns:
            True if updated successfully.

        Raises:
            ValueError: If calculator not found or is built-in.
        """
        if calculator_id not in self._custom_calculators:
            raise ValueError(f"Calculator not found: {calculator_id}")

        calc = self._custom_calculators[calculator_id]

        if calc.get("is_builtin", False):
            raise ValueError("Cannot modify built-in calculators")

        # Validate formula if being updated
        if "formula" in updates:
            input_vars = [inp["name"] for inp in calc.get("inputs", [])]
            if "inputs" in updates:
                input_vars = [inp["name"] for inp in updates["inputs"]]

            validation = self.validate_formula(updates["formula"], input_vars)
            if not validation.is_valid:
                raise ValueError(f"Invalid formula: {'; '.join(validation.errors)}")

        # Apply updates
        allowed_fields = {
            "name", "description", "formula", "inputs", "output_type", "output_unit",
            "interpretation_rules", "recommendations", "references", "category",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                calc[field] = value

        calc["updated_at"] = datetime.now(timezone.utc).isoformat()
        calc["version"] = calc.get("version", 1) + 1

        logger.info(f"Updated calculator {calculator_id}")
        return True

    def delete_calculator(self, calculator_id: str) -> bool:
        """Delete a custom calculator.

        Args:
            calculator_id: ID of calculator to delete.

        Returns:
            True if deleted successfully.

        Raises:
            ValueError: If calculator not found or is built-in.
        """
        if calculator_id not in self._custom_calculators:
            raise ValueError(f"Calculator not found: {calculator_id}")

        calc = self._custom_calculators[calculator_id]

        if calc.get("is_builtin", False):
            raise ValueError("Cannot delete built-in calculators")

        del self._custom_calculators[calculator_id]
        logger.info(f"Deleted calculator {calculator_id}")
        return True

    def get_calculator(self, calculator_id: str) -> dict | None:
        """Get calculator definition by ID.

        Args:
            calculator_id: Calculator ID.

        Returns:
            Calculator definition or None if not found.
        """
        return self._custom_calculators.get(calculator_id)

    def list_calculators(
        self,
        category: str | None = None,
        include_builtin: bool = True,
        include_custom: bool = True,
    ) -> list[dict]:
        """List all available calculators.

        Args:
            category: Filter by category.
            include_builtin: Include built-in calculators.
            include_custom: Include custom calculators.

        Returns:
            List of calculator definitions.
        """
        result = []

        for calc_id, calc in self._custom_calculators.items():
            is_builtin = calc.get("is_builtin", False)

            if is_builtin and not include_builtin:
                continue
            if not is_builtin and not include_custom:
                continue
            if category and calc.get("category") != category:
                continue

            result.append({
                "id": calc_id,
                "name": calc["name"],
                "description": calc.get("description"),
                "category": calc.get("category"),
                "is_builtin": is_builtin,
                "output_type": calc.get("output_type", "number"),
                "output_unit": calc.get("output_unit"),
                "input_count": len(calc.get("inputs", [])),
            })

        return result

    def execute_calculator(
        self,
        calculator_id: str,
        input_values: dict[str, Any],
        patient_id: str | None = None,
        user_id: str | None = None,
    ) -> CalculatorExecutionResult:
        """Execute a calculator with given input values.

        Args:
            calculator_id: Calculator to execute.
            input_values: Input values keyed by input name.
            patient_id: Optional patient ID for audit trail.
            user_id: Optional user ID for audit trail.

        Returns:
            CalculatorExecutionResult with computed score and interpretation.

        Raises:
            ValueError: If calculator not found or inputs invalid.
        """
        start_time = time.perf_counter()

        if calculator_id not in self._custom_calculators:
            raise ValueError(f"Calculator not found: {calculator_id}")

        calc = self._custom_calculators[calculator_id]

        # Validate inputs
        validated_inputs = self._validate_inputs(calc, input_values)

        # Parse and evaluate formula
        lexer = FormulaLexer(calc["formula"])
        tokens = lexer.tokenize()
        parser = FormulaParser(tokens)
        ast = parser.parse()

        evaluator = FormulaEvaluator(validated_inputs)
        score = evaluator.evaluate(ast)

        # Ensure score is numeric
        if isinstance(score, bool):
            score = 1.0 if score else 0.0
        score = float(score)

        # Interpret result
        risk_level, interpretation, recommendations = self._interpret_result(calc, score)

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        result = CalculatorExecutionResult(
            calculator_id=calculator_id,
            calculator_name=calc["name"],
            score=round(score, 4),
            score_unit=calc.get("output_unit"),
            risk_level=risk_level,
            interpretation=interpretation,
            recommendations=recommendations,
            components={"formula": calc["formula"], "inputs": validated_inputs},
            references=calc.get("references", []),
            execution_time_ms=round(execution_time_ms, 2),
            inputs_used=validated_inputs,
        )

        # Store in history for audit
        self._execution_history.append({
            "calculator_id": calculator_id,
            "patient_id": patient_id,
            "user_id": user_id,
            "inputs": validated_inputs,
            "result": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return result

    def _validate_inputs(self, calc: dict, input_values: dict[str, Any]) -> dict[str, float]:
        """Validate and convert input values.

        Args:
            calc: Calculator definition.
            input_values: Raw input values.

        Returns:
            Validated and converted input values.

        Raises:
            ValueError: If inputs are invalid.
        """
        validated = {}
        input_defs = {inp["name"]: inp for inp in calc.get("inputs", [])}

        for name, definition in input_defs.items():
            # Check required
            if name not in input_values:
                if definition.get("required", True):
                    raise ValueError(f"Missing required input: {name}")
                elif definition.get("default_value") is not None:
                    validated[name] = float(definition["default_value"])
                continue

            value = input_values[name]

            # Type conversion
            inp_type = definition.get("type", "number")
            if inp_type in ("number", "integer"):
                try:
                    value = float(value)
                    if inp_type == "integer":
                        value = round(value)
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid numeric value for {name}: {value}")
            elif inp_type == "boolean":
                value = 1.0 if value else 0.0

            # Range validation
            min_val = definition.get("min_value")
            max_val = definition.get("max_value")
            if min_val is not None and value < min_val:
                raise ValueError(f"Value for {name} ({value}) is below minimum ({min_val})")
            if max_val is not None and value > max_val:
                raise ValueError(f"Value for {name} ({value}) is above maximum ({max_val})")

            validated[name] = float(value)

        return validated

    def _interpret_result(
        self,
        calc: dict,
        score: float,
    ) -> tuple[str | None, str | None, list[str]]:
        """Interpret a calculated result using interpretation rules.

        Args:
            calc: Calculator definition.
            score: Calculated score.

        Returns:
            Tuple of (risk_level, interpretation, recommendations).
        """
        rules = calc.get("interpretation_rules", [])
        rec_map = calc.get("recommendations", {})

        for rule in rules:
            min_val = rule.get("min", float("-inf"))
            max_val = rule.get("max", float("inf"))

            if min_val <= score < max_val:
                risk_level = rule.get("risk_level", "unknown")
                interpretation = rule.get("label", "")
                recommendations = rec_map.get(risk_level, [])
                return risk_level, interpretation, recommendations

        return None, None, []

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service statistics.
        """
        builtin_count = sum(1 for c in self._custom_calculators.values() if c.get("is_builtin"))
        custom_count = len(self._custom_calculators) - builtin_count

        return {
            "total_calculators": len(self._custom_calculators),
            "builtin_calculators": builtin_count,
            "custom_calculators": custom_count,
            "total_executions": len(self._execution_history),
            "categories": list(set(c.get("category") for c in self._custom_calculators.values() if c.get("category"))),
        }


# Singleton instance and lock
_calculator_builder_service: CalculatorBuilderService | None = None
_calculator_builder_lock = Lock()


def get_calculator_builder_service() -> CalculatorBuilderService:
    """Get the singleton CalculatorBuilderService instance.

    Returns:
        The singleton CalculatorBuilderService instance.
    """
    global _calculator_builder_service

    if _calculator_builder_service is None:
        with _calculator_builder_lock:
            if _calculator_builder_service is None:
                logger.info("Creating singleton CalculatorBuilderService instance")
                _calculator_builder_service = CalculatorBuilderService()

    return _calculator_builder_service


def reset_calculator_builder_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _calculator_builder_service
    with _calculator_builder_lock:
        _calculator_builder_service = None
