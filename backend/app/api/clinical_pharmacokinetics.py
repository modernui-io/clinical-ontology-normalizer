"""Clinical Pharmacokinetics API endpoints (CLIN-PK).

Provides comprehensive clinical PK operations: PK study management,
concentration data tracking, compartmental modeling, drug interaction
analysis, and exposure-response assessment with PK metrics.

Endpoints:
    GET    /clinical-pharmacokinetics/pk-studies                       - List PK studies
    GET    /clinical-pharmacokinetics/pk-studies/{study_id}            - Get single study
    POST   /clinical-pharmacokinetics/pk-studies                       - Create study
    PUT    /clinical-pharmacokinetics/pk-studies/{study_id}            - Update study
    DELETE /clinical-pharmacokinetics/pk-studies/{study_id}            - Delete study
    GET    /clinical-pharmacokinetics/concentration-data               - List concentration data
    GET    /clinical-pharmacokinetics/concentration-data/{data_id}     - Get single record
    POST   /clinical-pharmacokinetics/concentration-data               - Create record
    PUT    /clinical-pharmacokinetics/concentration-data/{data_id}     - Update record
    DELETE /clinical-pharmacokinetics/concentration-data/{data_id}     - Delete record
    GET    /clinical-pharmacokinetics/compartmental-models             - List models
    GET    /clinical-pharmacokinetics/compartmental-models/{model_id}  - Get single model
    POST   /clinical-pharmacokinetics/compartmental-models             - Create model
    PUT    /clinical-pharmacokinetics/compartmental-models/{model_id}  - Update model
    DELETE /clinical-pharmacokinetics/compartmental-models/{model_id}  - Delete model
    GET    /clinical-pharmacokinetics/drug-interactions                - List interactions
    GET    /clinical-pharmacokinetics/drug-interactions/{id}           - Get single interaction
    POST   /clinical-pharmacokinetics/drug-interactions                - Create interaction
    PUT    /clinical-pharmacokinetics/drug-interactions/{id}           - Update interaction
    DELETE /clinical-pharmacokinetics/drug-interactions/{id}           - Delete interaction
    GET    /clinical-pharmacokinetics/exposure-responses               - List E-R analyses
    GET    /clinical-pharmacokinetics/exposure-responses/{id}          - Get single E-R
    POST   /clinical-pharmacokinetics/exposure-responses               - Create E-R
    PUT    /clinical-pharmacokinetics/exposure-responses/{id}          - Update E-R
    DELETE /clinical-pharmacokinetics/exposure-responses/{id}          - Delete E-R
    GET    /clinical-pharmacokinetics/metrics                          - PK metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_pharmacokinetics import (
    ClinicalPharmacokineticsMetrics,
    CompartmentalModel,
    CompartmentalModelCreate,
    CompartmentalModelListResponse,
    CompartmentalModelUpdate,
    ConcentrationData,
    ConcentrationDataCreate,
    ConcentrationDataListResponse,
    ConcentrationDataUpdate,
    DrugInteraction,
    DrugInteractionCreate,
    DrugInteractionListResponse,
    DrugInteractionUpdate,
    ExposureResponse,
    ExposureResponseCreate,
    ExposureResponseListResponse,
    ExposureResponseUpdate,
    InteractionSeverity,
    InteractionType,
    ModelType,
    PKStudy,
    PKStudyCreate,
    PKStudyListResponse,
    PKStudyStatus,
    PKStudyType,
    PKStudyUpdate,
)
from app.services.clinical_pharmacokinetics_service import (
    get_clinical_pharmacokinetics_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-pharmacokinetics",
    tags=["Clinical Pharmacokinetics"],
)


# ---------------------------------------------------------------------------
# PK Studies
# ---------------------------------------------------------------------------


@router.get(
    "/pk-studies",
    response_model=PKStudyListResponse,
    summary="List PK studies",
    description="Retrieve PK studies with optional filtering by trial, study type, and status.",
)
async def list_pk_studies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_type: Optional[PKStudyType] = Query(None, description="Filter by study type"),
    status: Optional[PKStudyStatus] = Query(None, description="Filter by study status"),
) -> PKStudyListResponse:
    svc = get_clinical_pharmacokinetics_service()
    items = svc.list_pk_studies(trial_id=trial_id, study_type=study_type, status=status)
    return PKStudyListResponse(items=items, total=len(items))


@router.get(
    "/pk-studies/{study_id}",
    response_model=PKStudy,
    summary="Get a PK study",
)
async def get_pk_study(study_id: str) -> PKStudy:
    svc = get_clinical_pharmacokinetics_service()
    study = svc.get_pk_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"PK study '{study_id}' not found")
    return study


@router.post(
    "/pk-studies",
    response_model=PKStudy,
    status_code=201,
    summary="Create a PK study",
)
async def create_pk_study(payload: PKStudyCreate) -> PKStudy:
    svc = get_clinical_pharmacokinetics_service()
    return svc.create_pk_study(payload)


@router.put(
    "/pk-studies/{study_id}",
    response_model=PKStudy,
    summary="Update a PK study",
)
async def update_pk_study(study_id: str, payload: PKStudyUpdate) -> PKStudy:
    svc = get_clinical_pharmacokinetics_service()
    updated = svc.update_pk_study(study_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"PK study '{study_id}' not found")
    return updated


@router.delete(
    "/pk-studies/{study_id}",
    status_code=204,
    summary="Delete a PK study",
)
async def delete_pk_study(study_id: str) -> None:
    svc = get_clinical_pharmacokinetics_service()
    deleted = svc.delete_pk_study(study_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"PK study '{study_id}' not found")


# ---------------------------------------------------------------------------
# Concentration Data
# ---------------------------------------------------------------------------


@router.get(
    "/concentration-data",
    response_model=ConcentrationDataListResponse,
    summary="List concentration data",
    description="Retrieve concentration data with optional filtering by trial, study, and subject.",
)
async def list_concentration_data(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> ConcentrationDataListResponse:
    svc = get_clinical_pharmacokinetics_service()
    items = svc.list_concentration_data(
        trial_id=trial_id, study_id=study_id, subject_id=subject_id
    )
    return ConcentrationDataListResponse(items=items, total=len(items))


@router.get(
    "/concentration-data/{data_id}",
    response_model=ConcentrationData,
    summary="Get a concentration data record",
)
async def get_concentration_data(data_id: str) -> ConcentrationData:
    svc = get_clinical_pharmacokinetics_service()
    record = svc.get_concentration_data(data_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Concentration data '{data_id}' not found"
        )
    return record


@router.post(
    "/concentration-data",
    response_model=ConcentrationData,
    status_code=201,
    summary="Create a concentration data record",
)
async def create_concentration_data(payload: ConcentrationDataCreate) -> ConcentrationData:
    svc = get_clinical_pharmacokinetics_service()
    return svc.create_concentration_data(payload)


@router.put(
    "/concentration-data/{data_id}",
    response_model=ConcentrationData,
    summary="Update a concentration data record",
)
async def update_concentration_data(
    data_id: str, payload: ConcentrationDataUpdate
) -> ConcentrationData:
    svc = get_clinical_pharmacokinetics_service()
    updated = svc.update_concentration_data(data_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Concentration data '{data_id}' not found"
        )
    return updated


@router.delete(
    "/concentration-data/{data_id}",
    status_code=204,
    summary="Delete a concentration data record",
)
async def delete_concentration_data(data_id: str) -> None:
    svc = get_clinical_pharmacokinetics_service()
    deleted = svc.delete_concentration_data(data_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Concentration data '{data_id}' not found"
        )


# ---------------------------------------------------------------------------
# Compartmental Models
# ---------------------------------------------------------------------------


@router.get(
    "/compartmental-models",
    response_model=CompartmentalModelListResponse,
    summary="List compartmental models",
    description="Retrieve compartmental models with optional filtering by trial, study, and model type.",
)
async def list_compartmental_models(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    model_type: Optional[ModelType] = Query(None, description="Filter by model type"),
) -> CompartmentalModelListResponse:
    svc = get_clinical_pharmacokinetics_service()
    items = svc.list_compartmental_models(
        trial_id=trial_id, study_id=study_id, model_type=model_type
    )
    return CompartmentalModelListResponse(items=items, total=len(items))


@router.get(
    "/compartmental-models/{model_id}",
    response_model=CompartmentalModel,
    summary="Get a compartmental model",
)
async def get_compartmental_model(model_id: str) -> CompartmentalModel:
    svc = get_clinical_pharmacokinetics_service()
    model = svc.get_compartmental_model(model_id)
    if model is None:
        raise HTTPException(
            status_code=404, detail=f"Compartmental model '{model_id}' not found"
        )
    return model


@router.post(
    "/compartmental-models",
    response_model=CompartmentalModel,
    status_code=201,
    summary="Create a compartmental model",
)
async def create_compartmental_model(payload: CompartmentalModelCreate) -> CompartmentalModel:
    svc = get_clinical_pharmacokinetics_service()
    return svc.create_compartmental_model(payload)


@router.put(
    "/compartmental-models/{model_id}",
    response_model=CompartmentalModel,
    summary="Update a compartmental model",
)
async def update_compartmental_model(
    model_id: str, payload: CompartmentalModelUpdate
) -> CompartmentalModel:
    svc = get_clinical_pharmacokinetics_service()
    updated = svc.update_compartmental_model(model_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Compartmental model '{model_id}' not found"
        )
    return updated


@router.delete(
    "/compartmental-models/{model_id}",
    status_code=204,
    summary="Delete a compartmental model",
)
async def delete_compartmental_model(model_id: str) -> None:
    svc = get_clinical_pharmacokinetics_service()
    deleted = svc.delete_compartmental_model(model_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Compartmental model '{model_id}' not found"
        )


# ---------------------------------------------------------------------------
# Drug Interactions
# ---------------------------------------------------------------------------


@router.get(
    "/drug-interactions",
    response_model=DrugInteractionListResponse,
    summary="List drug interactions",
    description="Retrieve drug interactions with optional filtering by trial, interaction type, and severity.",
)
async def list_drug_interactions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    interaction_type: Optional[InteractionType] = Query(
        None, description="Filter by interaction type"
    ),
    severity: Optional[InteractionSeverity] = Query(
        None, description="Filter by severity"
    ),
) -> DrugInteractionListResponse:
    svc = get_clinical_pharmacokinetics_service()
    items = svc.list_drug_interactions(
        trial_id=trial_id, interaction_type=interaction_type, severity=severity
    )
    return DrugInteractionListResponse(items=items, total=len(items))


@router.get(
    "/drug-interactions/{interaction_id}",
    response_model=DrugInteraction,
    summary="Get a drug interaction",
)
async def get_drug_interaction(interaction_id: str) -> DrugInteraction:
    svc = get_clinical_pharmacokinetics_service()
    interaction = svc.get_drug_interaction(interaction_id)
    if interaction is None:
        raise HTTPException(
            status_code=404, detail=f"Drug interaction '{interaction_id}' not found"
        )
    return interaction


@router.post(
    "/drug-interactions",
    response_model=DrugInteraction,
    status_code=201,
    summary="Create a drug interaction",
)
async def create_drug_interaction(payload: DrugInteractionCreate) -> DrugInteraction:
    svc = get_clinical_pharmacokinetics_service()
    return svc.create_drug_interaction(payload)


@router.put(
    "/drug-interactions/{interaction_id}",
    response_model=DrugInteraction,
    summary="Update a drug interaction",
)
async def update_drug_interaction(
    interaction_id: str, payload: DrugInteractionUpdate
) -> DrugInteraction:
    svc = get_clinical_pharmacokinetics_service()
    updated = svc.update_drug_interaction(interaction_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Drug interaction '{interaction_id}' not found"
        )
    return updated


@router.delete(
    "/drug-interactions/{interaction_id}",
    status_code=204,
    summary="Delete a drug interaction",
)
async def delete_drug_interaction(interaction_id: str) -> None:
    svc = get_clinical_pharmacokinetics_service()
    deleted = svc.delete_drug_interaction(interaction_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Drug interaction '{interaction_id}' not found"
        )


# ---------------------------------------------------------------------------
# Exposure-Response
# ---------------------------------------------------------------------------


@router.get(
    "/exposure-responses",
    response_model=ExposureResponseListResponse,
    summary="List exposure-response analyses",
    description="Retrieve exposure-response analyses with optional filtering by trial, study, and significance.",
)
async def list_exposure_responses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    significant_only: Optional[bool] = Query(
        None, description="Only significant relationships"
    ),
) -> ExposureResponseListResponse:
    svc = get_clinical_pharmacokinetics_service()
    items = svc.list_exposure_responses(
        trial_id=trial_id, study_id=study_id, significant_only=significant_only
    )
    return ExposureResponseListResponse(items=items, total=len(items))


@router.get(
    "/exposure-responses/{er_id}",
    response_model=ExposureResponse,
    summary="Get an exposure-response analysis",
)
async def get_exposure_response(er_id: str) -> ExposureResponse:
    svc = get_clinical_pharmacokinetics_service()
    er = svc.get_exposure_response(er_id)
    if er is None:
        raise HTTPException(
            status_code=404, detail=f"Exposure-response '{er_id}' not found"
        )
    return er


@router.post(
    "/exposure-responses",
    response_model=ExposureResponse,
    status_code=201,
    summary="Create an exposure-response analysis",
)
async def create_exposure_response(payload: ExposureResponseCreate) -> ExposureResponse:
    svc = get_clinical_pharmacokinetics_service()
    return svc.create_exposure_response(payload)


@router.put(
    "/exposure-responses/{er_id}",
    response_model=ExposureResponse,
    summary="Update an exposure-response analysis",
)
async def update_exposure_response(
    er_id: str, payload: ExposureResponseUpdate
) -> ExposureResponse:
    svc = get_clinical_pharmacokinetics_service()
    updated = svc.update_exposure_response(er_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Exposure-response '{er_id}' not found"
        )
    return updated


@router.delete(
    "/exposure-responses/{er_id}",
    status_code=204,
    summary="Delete an exposure-response analysis",
)
async def delete_exposure_response(er_id: str) -> None:
    svc = get_clinical_pharmacokinetics_service()
    deleted = svc.delete_exposure_response(er_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Exposure-response '{er_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalPharmacokineticsMetrics,
    summary="Get clinical pharmacokinetics metrics",
    description="Aggregated metrics across all clinical pharmacokinetics operations.",
)
async def get_metrics() -> ClinicalPharmacokineticsMetrics:
    svc = get_clinical_pharmacokinetics_service()
    return svc.get_metrics()
