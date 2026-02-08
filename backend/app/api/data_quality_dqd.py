"""OHDSI Data Quality Dashboard (DQD) API endpoints.

CDO-3: Provides endpoints to run DQD checks against OMOP-aligned clinical facts.

Endpoints:
- GET /data-quality/dqd/definitions - List all available check definitions
- GET /data-quality/dqd - Run all DQD checks and return report
- GET /data-quality/dqd/{check_id} - Run a specific check by ID
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.dqd import DQDCheckDefinition, DQDCheckResult, DQDReport
from app.services.dqd_check_service import DQDCheckService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-quality/dqd", tags=["data-quality-dqd"])

_service = DQDCheckService()


@router.get(
    "/definitions",
    response_model=list[DQDCheckDefinition],
    summary="List all DQD check definitions",
)
async def get_check_definitions() -> list[DQDCheckDefinition]:
    """Return definitions of all available DQD checks.

    Each definition includes the check ID, name, category,
    description, and pass/warn thresholds.
    """
    return _service.get_check_definitions()


@router.get(
    "",
    response_model=DQDReport,
    summary="Run all DQD checks",
)
async def run_all_checks(
    db: AsyncSession = Depends(get_db),
) -> DQDReport:
    """Run all OHDSI DQD checks and return a full quality report.

    Executes completeness, conformance, and plausibility checks
    across the clinical facts table. Returns individual check
    results and an overall quality score.
    """
    try:
        return await _service.run_all_checks(db)
    except Exception:
        logger.exception("Error running DQD checks")
        raise HTTPException(status_code=500, detail="Error running DQD checks")


@router.get(
    "/{check_id}",
    response_model=DQDCheckResult,
    summary="Run a specific DQD check",
)
async def run_single_check(
    check_id: str,
    db: AsyncSession = Depends(get_db),
) -> DQDCheckResult:
    """Run a single DQD check by its check ID.

    Valid check IDs can be obtained from the /definitions endpoint.

    Args:
        check_id: The check identifier (e.g. 'COMP-001')
    """
    try:
        return await _service.run_check(check_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Error running DQD check %s", check_id)
        raise HTTPException(
            status_code=500,
            detail=f"Error running DQD check {check_id}",
        )
