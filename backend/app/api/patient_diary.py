"""Patient Diary / eDiary Management API endpoints (EDIARY-MGT).

Provides comprehensive eDiary operations: diary entry tracking with CRUD,
symptom recording, diary schedule management, compliance monitoring,
diary form validation, and eDiary operational metrics.

Endpoints:
    POST   /patient-diary/entries                          - Create diary entry
    GET    /patient-diary/entries                           - List diary entries
    GET    /patient-diary/entries/{entry_id}                - Get single entry
    PUT    /patient-diary/entries/{entry_id}                - Update entry
    DELETE /patient-diary/entries/{entry_id}                - Delete entry
    POST   /patient-diary/symptoms                         - Create symptom record
    GET    /patient-diary/symptoms                          - List symptom records
    GET    /patient-diary/symptoms/{record_id}              - Get single symptom
    PUT    /patient-diary/symptoms/{record_id}              - Update symptom
    DELETE /patient-diary/symptoms/{record_id}              - Delete symptom
    POST   /patient-diary/schedules                        - Create schedule
    GET    /patient-diary/schedules                         - List schedules
    GET    /patient-diary/schedules/{schedule_id}           - Get single schedule
    PUT    /patient-diary/schedules/{schedule_id}           - Update schedule
    DELETE /patient-diary/schedules/{schedule_id}           - Delete schedule
    POST   /patient-diary/compliance                       - Create compliance record
    GET    /patient-diary/compliance                        - List compliance records
    GET    /patient-diary/compliance/{compliance_id}        - Get single compliance
    PUT    /patient-diary/compliance/{compliance_id}        - Update compliance
    DELETE /patient-diary/compliance/{compliance_id}        - Delete compliance
    POST   /patient-diary/validations                      - Create validation
    GET    /patient-diary/validations                       - List validations
    GET    /patient-diary/validations/{validation_id}       - Get single validation
    PUT    /patient-diary/validations/{validation_id}       - Update validation
    DELETE /patient-diary/validations/{validation_id}       - Delete validation
    GET    /patient-diary/metrics                           - eDiary dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_diary import (
    ComplianceLevel,
    DiaryCompliance,
    DiaryComplianceCreate,
    DiaryComplianceListResponse,
    DiaryComplianceUpdate,
    DiaryEntry,
    DiaryEntryCreate,
    DiaryEntryListResponse,
    DiaryEntryUpdate,
    DiarySchedule,
    DiaryScheduleCreate,
    DiaryScheduleListResponse,
    DiaryScheduleUpdate,
    DiaryType,
    DiaryValidation,
    DiaryValidationCreate,
    DiaryValidationListResponse,
    DiaryValidationUpdate,
    EntryStatus,
    PatientDiaryMetrics,
    SymptomRecord,
    SymptomRecordCreate,
    SymptomRecordListResponse,
    SymptomRecordUpdate,
    ValidationStatus,
)
from app.services.patient_diary_service import get_patient_diary_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-diary",
    tags=["Patient Diary"],
)


# ---------------------------------------------------------------------------
# Diary Entries
# ---------------------------------------------------------------------------


@router.post(
    "/entries",
    response_model=DiaryEntry,
    status_code=201,
    summary="Create a diary entry",
)
async def create_diary_entry(payload: DiaryEntryCreate) -> DiaryEntry:
    svc = get_patient_diary_service()
    return svc.create_diary_entry(payload)


@router.get(
    "/entries",
    response_model=DiaryEntryListResponse,
    summary="List diary entries",
    description="Retrieve diary entries with optional filtering by trial, subject, status, and diary type.",
)
async def list_diary_entries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    status: Optional[EntryStatus] = Query(None, description="Filter by entry status"),
    diary_type: Optional[DiaryType] = Query(None, description="Filter by diary type"),
) -> DiaryEntryListResponse:
    svc = get_patient_diary_service()
    items = svc.list_diary_entries(
        trial_id=trial_id, subject_id=subject_id, status=status, diary_type=diary_type
    )
    return DiaryEntryListResponse(items=items, total=len(items))


@router.get(
    "/entries/{entry_id}",
    response_model=DiaryEntry,
    summary="Get a diary entry",
)
async def get_diary_entry(entry_id: str) -> DiaryEntry:
    svc = get_patient_diary_service()
    entry = svc.get_diary_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Diary entry '{entry_id}' not found")
    return entry


@router.put(
    "/entries/{entry_id}",
    response_model=DiaryEntry,
    summary="Update a diary entry",
)
async def update_diary_entry(entry_id: str, payload: DiaryEntryUpdate) -> DiaryEntry:
    svc = get_patient_diary_service()
    updated = svc.update_diary_entry(entry_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Diary entry '{entry_id}' not found")
    return updated


@router.delete(
    "/entries/{entry_id}",
    status_code=204,
    summary="Delete a diary entry",
)
async def delete_diary_entry(entry_id: str) -> None:
    svc = get_patient_diary_service()
    deleted = svc.delete_diary_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Diary entry '{entry_id}' not found")


# ---------------------------------------------------------------------------
# Symptom Records
# ---------------------------------------------------------------------------


@router.post(
    "/symptoms",
    response_model=SymptomRecord,
    status_code=201,
    summary="Create a symptom record",
)
async def create_symptom_record(payload: SymptomRecordCreate) -> SymptomRecord:
    svc = get_patient_diary_service()
    return svc.create_symptom_record(payload)


@router.get(
    "/symptoms",
    response_model=SymptomRecordListResponse,
    summary="List symptom records",
    description="Retrieve symptom records with optional filtering by trial, subject, and entry.",
)
async def list_symptom_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    entry_id: Optional[str] = Query(None, description="Filter by diary entry ID"),
) -> SymptomRecordListResponse:
    svc = get_patient_diary_service()
    items = svc.list_symptom_records(
        trial_id=trial_id, subject_id=subject_id, entry_id=entry_id
    )
    return SymptomRecordListResponse(items=items, total=len(items))


@router.get(
    "/symptoms/{record_id}",
    response_model=SymptomRecord,
    summary="Get a symptom record",
)
async def get_symptom_record(record_id: str) -> SymptomRecord:
    svc = get_patient_diary_service()
    record = svc.get_symptom_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Symptom record '{record_id}' not found")
    return record


@router.put(
    "/symptoms/{record_id}",
    response_model=SymptomRecord,
    summary="Update a symptom record",
)
async def update_symptom_record(record_id: str, payload: SymptomRecordUpdate) -> SymptomRecord:
    svc = get_patient_diary_service()
    updated = svc.update_symptom_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Symptom record '{record_id}' not found")
    return updated


@router.delete(
    "/symptoms/{record_id}",
    status_code=204,
    summary="Delete a symptom record",
)
async def delete_symptom_record(record_id: str) -> None:
    svc = get_patient_diary_service()
    deleted = svc.delete_symptom_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Symptom record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Diary Schedules
# ---------------------------------------------------------------------------


@router.post(
    "/schedules",
    response_model=DiarySchedule,
    status_code=201,
    summary="Create a diary schedule",
)
async def create_diary_schedule(payload: DiaryScheduleCreate) -> DiarySchedule:
    svc = get_patient_diary_service()
    return svc.create_diary_schedule(payload)


@router.get(
    "/schedules",
    response_model=DiaryScheduleListResponse,
    summary="List diary schedules",
    description="Retrieve diary schedules with optional filtering by trial, diary type, and active status.",
)
async def list_diary_schedules(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    diary_type: Optional[DiaryType] = Query(None, description="Filter by diary type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> DiaryScheduleListResponse:
    svc = get_patient_diary_service()
    items = svc.list_diary_schedules(
        trial_id=trial_id, diary_type=diary_type, is_active=is_active
    )
    return DiaryScheduleListResponse(items=items, total=len(items))


@router.get(
    "/schedules/{schedule_id}",
    response_model=DiarySchedule,
    summary="Get a diary schedule",
)
async def get_diary_schedule(schedule_id: str) -> DiarySchedule:
    svc = get_patient_diary_service()
    schedule = svc.get_diary_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Diary schedule '{schedule_id}' not found")
    return schedule


@router.put(
    "/schedules/{schedule_id}",
    response_model=DiarySchedule,
    summary="Update a diary schedule",
)
async def update_diary_schedule(schedule_id: str, payload: DiaryScheduleUpdate) -> DiarySchedule:
    svc = get_patient_diary_service()
    updated = svc.update_diary_schedule(schedule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Diary schedule '{schedule_id}' not found")
    return updated


@router.delete(
    "/schedules/{schedule_id}",
    status_code=204,
    summary="Delete a diary schedule",
)
async def delete_diary_schedule(schedule_id: str) -> None:
    svc = get_patient_diary_service()
    deleted = svc.delete_diary_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Diary schedule '{schedule_id}' not found")


# ---------------------------------------------------------------------------
# Diary Compliance
# ---------------------------------------------------------------------------


@router.post(
    "/compliance",
    response_model=DiaryCompliance,
    status_code=201,
    summary="Create a compliance record",
)
async def create_diary_compliance(payload: DiaryComplianceCreate) -> DiaryCompliance:
    svc = get_patient_diary_service()
    return svc.create_diary_compliance(payload)


@router.get(
    "/compliance",
    response_model=DiaryComplianceListResponse,
    summary="List compliance records",
    description="Retrieve compliance records with optional filtering by trial, subject, and compliance level.",
)
async def list_diary_compliance(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    compliance_level: Optional[ComplianceLevel] = Query(None, description="Filter by compliance level"),
) -> DiaryComplianceListResponse:
    svc = get_patient_diary_service()
    items = svc.list_diary_compliance(
        trial_id=trial_id, subject_id=subject_id, compliance_level=compliance_level
    )
    return DiaryComplianceListResponse(items=items, total=len(items))


@router.get(
    "/compliance/{compliance_id}",
    response_model=DiaryCompliance,
    summary="Get a compliance record",
)
async def get_diary_compliance(compliance_id: str) -> DiaryCompliance:
    svc = get_patient_diary_service()
    compliance = svc.get_diary_compliance(compliance_id)
    if compliance is None:
        raise HTTPException(status_code=404, detail=f"Compliance record '{compliance_id}' not found")
    return compliance


@router.put(
    "/compliance/{compliance_id}",
    response_model=DiaryCompliance,
    summary="Update a compliance record",
)
async def update_diary_compliance(compliance_id: str, payload: DiaryComplianceUpdate) -> DiaryCompliance:
    svc = get_patient_diary_service()
    updated = svc.update_diary_compliance(compliance_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Compliance record '{compliance_id}' not found")
    return updated


@router.delete(
    "/compliance/{compliance_id}",
    status_code=204,
    summary="Delete a compliance record",
)
async def delete_diary_compliance(compliance_id: str) -> None:
    svc = get_patient_diary_service()
    deleted = svc.delete_diary_compliance(compliance_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Compliance record '{compliance_id}' not found")


# ---------------------------------------------------------------------------
# Diary Validations
# ---------------------------------------------------------------------------


@router.post(
    "/validations",
    response_model=DiaryValidation,
    status_code=201,
    summary="Create a validation record",
)
async def create_diary_validation(payload: DiaryValidationCreate) -> DiaryValidation:
    svc = get_patient_diary_service()
    return svc.create_diary_validation(payload)


@router.get(
    "/validations",
    response_model=DiaryValidationListResponse,
    summary="List validation records",
    description="Retrieve validation records with optional filtering by trial, entry, and validation status.",
)
async def list_diary_validations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    entry_id: Optional[str] = Query(None, description="Filter by diary entry ID"),
    validation_status: Optional[ValidationStatus] = Query(None, description="Filter by validation status"),
) -> DiaryValidationListResponse:
    svc = get_patient_diary_service()
    items = svc.list_diary_validations(
        trial_id=trial_id, entry_id=entry_id, validation_status=validation_status
    )
    return DiaryValidationListResponse(items=items, total=len(items))


@router.get(
    "/validations/{validation_id}",
    response_model=DiaryValidation,
    summary="Get a validation record",
)
async def get_diary_validation(validation_id: str) -> DiaryValidation:
    svc = get_patient_diary_service()
    validation = svc.get_diary_validation(validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return validation


@router.put(
    "/validations/{validation_id}",
    response_model=DiaryValidation,
    summary="Update a validation record",
)
async def update_diary_validation(validation_id: str, payload: DiaryValidationUpdate) -> DiaryValidation:
    svc = get_patient_diary_service()
    updated = svc.update_diary_validation(validation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")
    return updated


@router.delete(
    "/validations/{validation_id}",
    status_code=204,
    summary="Delete a validation record",
)
async def delete_diary_validation(validation_id: str) -> None:
    svc = get_patient_diary_service()
    deleted = svc.delete_diary_validation(validation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Validation '{validation_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PatientDiaryMetrics,
    summary="Get eDiary dashboard metrics",
    description="Aggregated patient diary metrics across all trials and subjects.",
)
async def get_metrics() -> PatientDiaryMetrics:
    svc = get_patient_diary_service()
    return svc.get_metrics()
