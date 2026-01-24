"""Medication Reconciliation API endpoints.

Provides:
- POST /medications/reconcile - Compare two medication lists
- GET /medications/reconcile/{id} - Retrieve a reconciliation result
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.med_reconciliation_service import get_med_reconciliation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medications", tags=["medication-reconciliation"])


class MedicationItem(BaseModel):
    name: str = Field(..., description="Medication name")
    dose: str = Field("", description="Dose (e.g., '10mg')")
    frequency: str = Field("", description="Frequency (e.g., 'BID')")
    route: str = Field("", description="Route (e.g., 'oral')")
    drug_class: str = Field("", description="Drug class (e.g., 'anticoagulant')")
    rxnorm_code: str = Field("", description="RxNorm code")


class ReconcileRequest(BaseModel):
    source_meds: list[MedicationItem] = Field(..., description="Source medication list")
    target_meds: list[MedicationItem] = Field(..., description="Target medication list")
    source_label: str = Field("admission", description="Label for source list")
    target_label: str = Field("discharge", description="Label for target list")


@router.post("/reconcile")
async def reconcile_medications(request: ReconcileRequest) -> dict[str, Any]:
    """Compare two medication lists and identify discrepancies."""
    service = get_med_reconciliation_service()
    result = service.reconcile(
        source_meds=[m.model_dump() for m in request.source_meds],
        target_meds=[m.model_dump() for m in request.target_meds],
        source_label=request.source_label,
        target_label=request.target_label,
    )

    return {
        "id": result.id,
        "source_label": result.source_label,
        "target_label": result.target_label,
        "source_count": result.source_count,
        "target_count": result.target_count,
        "matched_count": len(result.matched),
        "discrepancy_count": len(result.discrepancies),
        "discrepancies": [
            {
                "type": d.type.value,
                "severity": d.severity.value,
                "medication_name": d.medication_name,
                "details": d.details,
            }
            for d in result.discrepancies
        ],
    }


@router.get("/reconcile/{reconciliation_id}")
async def get_reconciliation(reconciliation_id: str) -> dict[str, Any]:
    """Retrieve a previous reconciliation result."""
    service = get_med_reconciliation_service()
    result = service.get_result(reconciliation_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    return {
        "id": result.id,
        "source_label": result.source_label,
        "target_label": result.target_label,
        "source_count": result.source_count,
        "target_count": result.target_count,
        "matched_count": len(result.matched),
        "discrepancy_count": len(result.discrepancies),
        "discrepancies": [
            {
                "type": d.type.value,
                "severity": d.severity.value,
                "medication_name": d.medication_name,
                "details": d.details,
            }
            for d in result.discrepancies
        ],
    }
