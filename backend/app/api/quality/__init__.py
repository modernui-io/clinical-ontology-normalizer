"""Quality API Module.

This module provides quality measure tracking and data quality dashboard endpoints.
It combines two focused routers:
- quality_checks: Quality measure validation and rule endpoints (HEDIS, CQM)
- quality_reports: Data Quality Dashboard (DQD) reporting endpoints

The combined router is exposed at the module level for backwards compatibility.
"""

from __future__ import annotations

from fastapi import APIRouter

# Import the sub-routers
from app.api.quality.quality_checks import router as checks_router
from app.api.quality.quality_reports import router as reports_router

# Re-export all models from quality_checks for backwards compatibility
from app.api.quality.quality_checks import (
    # Enums
    MeasureCategoryAPI,
    MeasureTypeAPI,
    MeasurePriorityAPI,
    ComplianceStatusAPI,
    # Request/Response Models
    AgeRangeResponse,
    EligibilityCriteriaResponse,
    QualityMeasureResponse,
    MeasureListResponse,
    PatientDataInput,
    EvaluateRequest,
    PatientGapResponse,
    MeasureResultResponse,
    EvaluationSummary,
    EvaluateResponse,
    GapsRequest,
    GapsResponse,
    MeasurePerformanceResponse,
    PerformanceRequest,
    PerformanceResponse,
)

# Re-export all models from quality_reports for backwards compatibility
from app.api.quality.quality_reports import (
    # Enums
    DQDCategoryAPI,
    DQDSubcategoryAPI,
    DQDSeverityAPI,
    DQDStatusAPI,
    OMOPTableAPI,
    # Response Models
    DQDCheckResultResponse,
    DQDIssueResponse,
    DQDCategorySummaryResponse,
    DQDTableSummaryResponse,
    DQDSummaryResponse,
    DQDHistoryEntryResponse,
    DQDCheckListResponse,
    DQDHistoryResponse,
    DQDRunResponse,
    DQDIssueListResponse,
)

# Create the combined router
router = APIRouter()

# Include both sub-routers (they both have prefix="/quality")
# We need to include them without their prefixes since we want the combined router
# to have the same structure as the original
router.include_router(checks_router)
router.include_router(reports_router)

__all__ = [
    # Main router
    "router",
    # Quality Checks Enums
    "MeasureCategoryAPI",
    "MeasureTypeAPI",
    "MeasurePriorityAPI",
    "ComplianceStatusAPI",
    # Quality Checks Models
    "AgeRangeResponse",
    "EligibilityCriteriaResponse",
    "QualityMeasureResponse",
    "MeasureListResponse",
    "PatientDataInput",
    "EvaluateRequest",
    "PatientGapResponse",
    "MeasureResultResponse",
    "EvaluationSummary",
    "EvaluateResponse",
    "GapsRequest",
    "GapsResponse",
    "MeasurePerformanceResponse",
    "PerformanceRequest",
    "PerformanceResponse",
    # DQD Enums
    "DQDCategoryAPI",
    "DQDSubcategoryAPI",
    "DQDSeverityAPI",
    "DQDStatusAPI",
    "OMOPTableAPI",
    # DQD Models
    "DQDCheckResultResponse",
    "DQDIssueResponse",
    "DQDCategorySummaryResponse",
    "DQDTableSummaryResponse",
    "DQDSummaryResponse",
    "DQDHistoryEntryResponse",
    "DQDCheckListResponse",
    "DQDHistoryResponse",
    "DQDRunResponse",
    "DQDIssueListResponse",
]
