"""Pydantic schemas for OHDSI Data Quality Dashboard (DQD) checks.

CDO-3: Implements DQD check result, report, and definition schemas
adapted for the platform's OMOP-aligned clinical facts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DQDCategory(str, Enum):
    """OHDSI DQD check categories."""

    COMPLETENESS = "completeness"
    CONFORMANCE = "conformance"
    PLAUSIBILITY = "plausibility"


class DQDStatus(str, Enum):
    """Status of a DQD check result."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class DQDCheckDefinition(BaseModel):
    """Definition of a single DQD check."""

    check_id: str = Field(..., description="Unique identifier for the check")
    name: str = Field(..., description="Human-readable check name")
    category: DQDCategory = Field(..., description="DQD category: completeness, conformance, or plausibility")
    description: str = Field(..., description="Detailed description of what this check verifies")
    threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pass threshold as a decimal (e.g. 0.95 = 95%)",
    )
    warn_threshold: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Warning threshold - below pass but above this is WARN",
    )
    sql_template: str | None = Field(
        None,
        description="Optional SQL template used by this check",
    )


class DQDFailingExample(BaseModel):
    """An example of a record that failed a DQD check."""

    record_id: str | None = Field(None, description="ID of the failing record")
    patient_id: str | None = Field(None, description="Patient ID if applicable")
    field: str | None = Field(None, description="Field that failed validation")
    value: str | None = Field(None, description="The invalid value")
    reason: str = Field(..., description="Why this record failed the check")


class DQDCheckResult(BaseModel):
    """Result of running a single DQD check."""

    check_id: str = Field(..., description="Unique identifier for the check")
    check_name: str = Field(..., description="Human-readable check name")
    category: DQDCategory = Field(..., description="DQD category")
    description: str = Field(..., description="What this check verifies")
    passed: int = Field(..., ge=0, description="Number of records that passed")
    failed: int = Field(..., ge=0, description="Number of records that failed")
    total: int = Field(..., ge=0, description="Total records evaluated")
    pass_rate: float = Field(..., ge=0.0, le=1.0, description="Pass rate as decimal")
    threshold: float = Field(..., ge=0.0, le=1.0, description="Required pass threshold")
    status: DQDStatus = Field(..., description="PASS, WARN, or FAIL")
    failing_examples: list[DQDFailingExample] = Field(
        default_factory=list,
        description="Sample of failing records (max 5)",
    )


class DQDReport(BaseModel):
    """Full report from running all DQD checks."""

    timestamp: datetime = Field(..., description="When the report was generated")
    total_checks: int = Field(..., ge=0, description="Total number of checks run")
    passed: int = Field(..., ge=0, description="Number of checks that passed")
    warned: int = Field(..., ge=0, description="Number of checks with warnings")
    failed: int = Field(..., ge=0, description="Number of checks that failed")
    results: list[DQDCheckResult] = Field(
        default_factory=list,
        description="Individual check results",
    )
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall quality score (fraction of checks passing)",
    )
