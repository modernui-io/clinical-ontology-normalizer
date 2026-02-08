"""Gold Standard Dataset API endpoints.

Provides endpoints for managing curated gold standard datasets
used to evaluate NLP extraction, OMOP mapping, trial screening,
and assertion detection accuracy:
- Create and list datasets
- Add annotations
- Evaluate predictions against gold standard
- Compute inter-annotator agreement
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.gold_standard import (
    AddAnnotationRequest,
    Annotation,
    CreateDatasetRequest,
    DatasetListResponse,
    DatasetWithAnnotations,
    EvaluateRequest,
    EvaluationResult,
    GoldStandardDataset,
    GoldStandardDomain,
    InterAnnotatorAgreement,
)
from app.services.gold_standard_service import get_gold_standard_service

router = APIRouter(prefix="/ml/gold-standard", tags=["Gold Standard Datasets"])


# ============================================================================
# Dataset management
# ============================================================================


@router.post(
    "",
    response_model=GoldStandardDataset,
    summary="Create a gold standard dataset",
    description="Create a new versioned gold standard dataset for evaluation benchmarking.",
)
async def create_dataset(request: CreateDatasetRequest) -> GoldStandardDataset:
    """Create a gold standard dataset."""
    service = get_gold_standard_service()
    return service.create_dataset(
        name=request.name,
        domain=request.domain,
        description=request.description,
        version=request.version,
    )


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List gold standard datasets",
    description="List all gold standard datasets, optionally filtered by domain.",
)
async def list_datasets(
    domain: GoldStandardDomain | None = Query(
        None, description="Filter by evaluation domain"
    ),
) -> DatasetListResponse:
    """List all gold standard datasets."""
    service = get_gold_standard_service()
    datasets = service.list_datasets(domain=domain)
    return DatasetListResponse(total=len(datasets), datasets=datasets)


@router.get(
    "/{name}",
    response_model=DatasetWithAnnotations,
    summary="Get a dataset with annotations",
    description="Retrieve a gold standard dataset by name with all annotations.",
)
async def get_dataset(
    name: str,
    version: str | None = Query(None, description="Specific version to retrieve"),
) -> DatasetWithAnnotations:
    """Get a dataset with its annotations."""
    service = get_gold_standard_service()
    dataset = service.get_dataset(name, version=version)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{name}' not found"
            + (f" (version {version})" if version else ""),
        )
    annotations = service.get_annotations(dataset.id)
    return DatasetWithAnnotations(dataset=dataset, annotations=annotations)


# ============================================================================
# Annotation management
# ============================================================================


@router.post(
    "/{name}/annotations",
    response_model=Annotation,
    summary="Add an annotation",
    description="Add a gold standard annotation to a dataset.",
)
async def add_annotation(
    name: str,
    request: AddAnnotationRequest,
    version: str | None = Query(None, description="Dataset version"),
) -> Annotation:
    """Add an annotation to a dataset."""
    service = get_gold_standard_service()
    dataset = service.get_dataset(name, version=version)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{name}' not found"
            + (f" (version {version})" if version else ""),
        )
    try:
        return service.add_annotation(
            dataset_id=dataset.id,
            input_data=request.input_data,
            expected_output=request.expected_output,
            annotator_id=request.annotator_id,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ============================================================================
# Evaluation
# ============================================================================


@router.post(
    "/{name}/evaluate",
    response_model=EvaluationResult,
    summary="Evaluate predictions",
    description="Evaluate predictions against the gold standard annotations in a dataset.",
)
async def evaluate(
    name: str,
    request: EvaluateRequest,
    version: str | None = Query(None, description="Dataset version"),
) -> EvaluationResult:
    """Evaluate predictions against gold standard."""
    service = get_gold_standard_service()
    dataset = service.get_dataset(name, version=version)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{name}' not found"
            + (f" (version {version})" if version else ""),
        )
    try:
        return service.evaluate_against(
            dataset_id=dataset.id,
            predictions=request.predictions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/{name}/iaa",
    response_model=InterAnnotatorAgreement,
    summary="Get inter-annotator agreement",
    description="Compute inter-annotator agreement metrics for a dataset.",
)
async def get_iaa(
    name: str,
    version: str | None = Query(None, description="Dataset version"),
) -> InterAnnotatorAgreement:
    """Get inter-annotator agreement for a dataset."""
    service = get_gold_standard_service()
    dataset = service.get_dataset(name, version=version)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{name}' not found"
            + (f" (version {version})" if version else ""),
        )
    try:
        return service.get_inter_annotator_agreement(dataset.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
