"""Clinical Outcome Assessment Management (COA-MGT) API endpoints.

Provides comprehensive COA operations: instrument management, assessment tracking,
instrument validation studies, translation/adaptation workflows, compliance reporting,
and operational metrics.

Endpoints:
    GET    /clinical-outcome-assessment/instruments                      - List instruments
    GET    /clinical-outcome-assessment/instruments/{instrument_id}      - Get single instrument
    POST   /clinical-outcome-assessment/instruments                      - Create instrument
    PUT    /clinical-outcome-assessment/instruments/{instrument_id}      - Update instrument
    DELETE /clinical-outcome-assessment/instruments/{instrument_id}      - Delete instrument
    GET    /clinical-outcome-assessment/assessments                      - List assessments
    GET    /clinical-outcome-assessment/assessments/{assessment_id}      - Get single assessment
    POST   /clinical-outcome-assessment/assessments                      - Create assessment
    PUT    /clinical-outcome-assessment/assessments/{assessment_id}      - Update assessment
    DELETE /clinical-outcome-assessment/assessments/{assessment_id}      - Delete assessment
    GET    /clinical-outcome-assessment/validations                      - List validations
    GET    /clinical-outcome-assessment/validations/{validation_id}      - Get single validation
    POST   /clinical-outcome-assessment/validations                      - Create validation
    PUT    /clinical-outcome-assessment/validations/{validation_id}      - Update validation
    DELETE /clinical-outcome-assessment/validations/{validation_id}      - Delete validation
    GET    /clinical-outcome-assessment/translations                     - List translations
    GET    /clinical-outcome-assessment/translations/{translation_id}    - Get single translation
    POST   /clinical-outcome-assessment/translations                     - Create translation
    PUT    /clinical-outcome-assessment/translations/{translation_id}    - Update translation
    DELETE /clinical-outcome-assessment/translations/{translation_id}    - Delete translation
    GET    /clinical-outcome-assessment/compliance-reports               - List compliance reports
    GET    /clinical-outcome-assessment/compliance-reports/{report_id}   - Get single report
    POST   /clinical-outcome-assessment/compliance-reports               - Create report
    PUT    /clinical-outcome-assessment/compliance-reports/{report_id}   - Update report
    DELETE /clinical-outcome-assessment/compliance-reports/{report_id}   - Delete report
    GET    /clinical-outcome-assessment/metrics                          - COA metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_outcome_assessment import (
    COAAssessment,
    COAAssessmentCreate,
    COAAssessmentListResponse,
    COAAssessmentUpdate,
    COAComplianceReport,
    COAComplianceReportCreate,
    COAComplianceReportListResponse,
    COAComplianceReportUpdate,
    COAInstrument,
    COAInstrumentCreate,
    COAInstrumentListResponse,
    COAInstrumentUpdate,
    COAMetrics,
    InstrumentValidation,
    InstrumentValidationCreate,
    InstrumentValidationListResponse,
    InstrumentValidationUpdate,
    TranslationAdaptation,
    TranslationAdaptationCreate,
    TranslationAdaptationListResponse,
    TranslationAdaptationUpdate,
)
from app.services.clinical_outcome_assessment_service import (
    get_clinical_outcome_assessment_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-outcome-assessment",
    tags=["Clinical Outcome Assessment"],
)


# ---------------------------------------------------------------------------
# Instrument Management
# ---------------------------------------------------------------------------


@router.get(
    "/instruments",
    response_model=COAInstrumentListResponse,
    summary="List COA instruments",
    description="Retrieve COA instruments with optional filtering by trial.",
)
async def list_instruments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> COAInstrumentListResponse:
    svc = get_clinical_outcome_assessment_service()
    items = svc.list_instruments(trial_id=trial_id)
    return COAInstrumentListResponse(items=items, total=len(items))


@router.get(
    "/instruments/{instrument_id}",
    response_model=COAInstrument,
    summary="Get a COA instrument",
)
async def get_instrument(instrument_id: str) -> COAInstrument:
    svc = get_clinical_outcome_assessment_service()
    instrument = svc.get_instrument(instrument_id)
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")
    return instrument


@router.post(
    "/instruments",
    response_model=COAInstrument,
    status_code=201,
    summary="Create a COA instrument",
)
async def create_instrument(payload: COAInstrumentCreate) -> COAInstrument:
    svc = get_clinical_outcome_assessment_service()
    return svc.create_instrument(payload)


@router.put(
    "/instruments/{instrument_id}",
    response_model=COAInstrument,
    summary="Update a COA instrument",
)
async def update_instrument(
    instrument_id: str, payload: COAInstrumentUpdate
) -> COAInstrument:
    svc = get_clinical_outcome_assessment_service()
    updated = svc.update_instrument(instrument_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")
    return updated


@router.delete(
    "/instruments/{instrument_id}",
    status_code=204,
    summary="Delete a COA instrument",
)
async def delete_instrument(instrument_id: str) -> None:
    svc = get_clinical_outcome_assessment_service()
    deleted = svc.delete_instrument(instrument_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")


# ---------------------------------------------------------------------------
# Assessment Management
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=COAAssessmentListResponse,
    summary="List COA assessments",
    description="Retrieve COA assessments with optional filtering by trial and instrument.",
)
async def list_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    instrument_id: Optional[str] = Query(None, description="Filter by instrument ID"),
) -> COAAssessmentListResponse:
    svc = get_clinical_outcome_assessment_service()
    items = svc.list_assessments(trial_id=trial_id, instrument_id=instrument_id)
    return COAAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=COAAssessment,
    summary="Get a COA assessment",
)
async def get_assessment(assessment_id: str) -> COAAssessment:
    svc = get_clinical_outcome_assessment_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=COAAssessment,
    status_code=201,
    summary="Create a COA assessment",
)
async def create_assessment(payload: COAAssessmentCreate) -> COAAssessment:
    svc = get_clinical_outcome_assessment_service()
    return svc.create_assessment(payload)


@router.put(
    "/assessments/{assessment_id}",
    response_model=COAAssessment,
    summary="Update a COA assessment",
)
async def update_assessment(
    assessment_id: str, payload: COAAssessmentUpdate
) -> COAAssessment:
    svc = get_clinical_outcome_assessment_service()
    updated = svc.update_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a COA assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_clinical_outcome_assessment_service()
    deleted = svc.delete_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Instrument Validation Management
# ---------------------------------------------------------------------------


@router.get(
    "/validations",
    response_model=InstrumentValidationListResponse,
    summary="List instrument validations",
    description="Retrieve instrument validations with optional filtering by instrument.",
)
async def list_validations(
    instrument_id: Optional[str] = Query(None, description="Filter by instrument ID"),
) -> InstrumentValidationListResponse:
    svc = get_clinical_outcome_assessment_service()
    items = svc.list_validations(instrument_id=instrument_id)
    return InstrumentValidationListResponse(items=items, total=len(items))


@router.get(
    "/validations/{validation_id}",
    response_model=InstrumentValidation,
    summary="Get an instrument validation",
)
async def get_validation(validation_id: str) -> InstrumentValidation:
    svc = get_clinical_outcome_assessment_service()
    validation = svc.get_validation(validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return validation


@router.post(
    "/validations",
    response_model=InstrumentValidation,
    status_code=201,
    summary="Create an instrument validation",
)
async def create_validation(payload: InstrumentValidationCreate) -> InstrumentValidation:
    svc = get_clinical_outcome_assessment_service()
    return svc.create_validation(payload)


@router.put(
    "/validations/{validation_id}",
    response_model=InstrumentValidation,
    summary="Update an instrument validation",
)
async def update_validation(
    validation_id: str, payload: InstrumentValidationUpdate
) -> InstrumentValidation:
    svc = get_clinical_outcome_assessment_service()
    updated = svc.update_validation(validation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return updated


@router.delete(
    "/validations/{validation_id}",
    status_code=204,
    summary="Delete an instrument validation",
)
async def delete_validation(validation_id: str) -> None:
    svc = get_clinical_outcome_assessment_service()
    deleted = svc.delete_validation(validation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")


# ---------------------------------------------------------------------------
# Translation/Adaptation Management
# ---------------------------------------------------------------------------


@router.get(
    "/translations",
    response_model=TranslationAdaptationListResponse,
    summary="List translation adaptations",
    description="Retrieve translation adaptations with optional filtering by instrument.",
)
async def list_translations(
    instrument_id: Optional[str] = Query(None, description="Filter by instrument ID"),
) -> TranslationAdaptationListResponse:
    svc = get_clinical_outcome_assessment_service()
    items = svc.list_translations(instrument_id=instrument_id)
    return TranslationAdaptationListResponse(items=items, total=len(items))


@router.get(
    "/translations/{translation_id}",
    response_model=TranslationAdaptation,
    summary="Get a translation adaptation",
)
async def get_translation(translation_id: str) -> TranslationAdaptation:
    svc = get_clinical_outcome_assessment_service()
    translation = svc.get_translation(translation_id)
    if translation is None:
        raise HTTPException(status_code=404, detail=f"Translation '{translation_id}' not found")
    return translation


@router.post(
    "/translations",
    response_model=TranslationAdaptation,
    status_code=201,
    summary="Create a translation adaptation",
)
async def create_translation(payload: TranslationAdaptationCreate) -> TranslationAdaptation:
    svc = get_clinical_outcome_assessment_service()
    return svc.create_translation(payload)


@router.put(
    "/translations/{translation_id}",
    response_model=TranslationAdaptation,
    summary="Update a translation adaptation",
)
async def update_translation(
    translation_id: str, payload: TranslationAdaptationUpdate
) -> TranslationAdaptation:
    svc = get_clinical_outcome_assessment_service()
    updated = svc.update_translation(translation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Translation '{translation_id}' not found")
    return updated


@router.delete(
    "/translations/{translation_id}",
    status_code=204,
    summary="Delete a translation adaptation",
)
async def delete_translation(translation_id: str) -> None:
    svc = get_clinical_outcome_assessment_service()
    deleted = svc.delete_translation(translation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Translation '{translation_id}' not found")


# ---------------------------------------------------------------------------
# Compliance Report Management
# ---------------------------------------------------------------------------


@router.get(
    "/compliance-reports",
    response_model=COAComplianceReportListResponse,
    summary="List COA compliance reports",
    description="Retrieve compliance reports with optional filtering by trial and instrument.",
)
async def list_compliance_reports(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    instrument_id: Optional[str] = Query(None, description="Filter by instrument ID"),
) -> COAComplianceReportListResponse:
    svc = get_clinical_outcome_assessment_service()
    items = svc.list_compliance_reports(trial_id=trial_id, instrument_id=instrument_id)
    return COAComplianceReportListResponse(items=items, total=len(items))


@router.get(
    "/compliance-reports/{report_id}",
    response_model=COAComplianceReport,
    summary="Get a COA compliance report",
)
async def get_compliance_report(report_id: str) -> COAComplianceReport:
    svc = get_clinical_outcome_assessment_service()
    report = svc.get_compliance_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Compliance report '{report_id}' not found")
    return report


@router.post(
    "/compliance-reports",
    response_model=COAComplianceReport,
    status_code=201,
    summary="Create a COA compliance report",
)
async def create_compliance_report(payload: COAComplianceReportCreate) -> COAComplianceReport:
    svc = get_clinical_outcome_assessment_service()
    return svc.create_compliance_report(payload)


@router.put(
    "/compliance-reports/{report_id}",
    response_model=COAComplianceReport,
    summary="Update a COA compliance report",
)
async def update_compliance_report(
    report_id: str, payload: COAComplianceReportUpdate
) -> COAComplianceReport:
    svc = get_clinical_outcome_assessment_service()
    updated = svc.update_compliance_report(report_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Compliance report '{report_id}' not found")
    return updated


@router.delete(
    "/compliance-reports/{report_id}",
    status_code=204,
    summary="Delete a COA compliance report",
)
async def delete_compliance_report(report_id: str) -> None:
    svc = get_clinical_outcome_assessment_service()
    deleted = svc.delete_compliance_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Compliance report '{report_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=COAMetrics,
    summary="Get COA metrics",
    description="Aggregated COA metrics including instrument counts, assessment compliance, "
                "validation coverage, translation progress, and data quality indicators.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> COAMetrics:
    svc = get_clinical_outcome_assessment_service()
    return svc.get_metrics(trial_id=trial_id)
