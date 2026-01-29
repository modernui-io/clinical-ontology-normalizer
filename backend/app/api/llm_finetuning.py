"""LLM Fine-tuning API Endpoints.

Provides REST API for LLM fine-tuning operations:
- POST /api/v1/llm/datasets - Create dataset
- GET /api/v1/llm/datasets - List datasets
- GET /api/v1/llm/datasets/{id} - Get dataset details
- DELETE /api/v1/llm/datasets/{id} - Delete dataset
- POST /api/v1/llm/finetune - Start fine-tuning job
- GET /api/v1/llm/jobs - List jobs
- GET /api/v1/llm/jobs/{id} - Get job status
- POST /api/v1/llm/jobs/{id}/cancel - Cancel job
- POST /api/v1/llm/evaluate - Evaluate model
- POST /api/v1/llm/deploy - Deploy model
- GET /api/v1/llm/deployments/{id} - Get deployment status
- POST /api/v1/llm/deployments/{id}/stop - Stop deployment
- POST /api/v1/llm/inference - Run inference
- GET /api/v1/llm/models - List fine-tuned models
- GET /api/v1/llm/models/{id} - Get model details
- DELETE /api/v1/llm/models/{id} - Delete model
- POST /api/v1/llm/models/compare - Compare models
"""

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.services.llm_finetuning_service import (
    AnnotationFormat,
    BaseModelType,
    Dataset,
    DatasetConfig,
    DatasetStatus,
    Deployment,
    DeploymentStatus,
    EvaluationResult,
    FineTuneConfig,
    FineTuneJob,
    FineTunedModel,
    FineTuningMethod,
    FineTuningTask,
    JobStatus,
    Prediction,
    TestData,
    TrainingExample,
    get_llm_finetuning_service,
)

router = APIRouter(prefix="/llm/finetune", tags=["LLM Fine-tuning"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateDatasetRequest(BaseModel):
    """Request to create a new dataset."""

    name: str = Field(..., min_length=1, max_length=200, description="Dataset name")
    description: str | None = Field(None, max_length=1000, description="Description")
    task: FineTuningTask = Field(..., description="Target task")
    annotation_format: AnnotationFormat = Field(
        default=AnnotationFormat.BRAT,
        description="Input annotation format",
    )
    document_ids: list[str] = Field(
        default_factory=list,
        description="Document IDs to include",
    )
    train_split: float = Field(default=0.8, ge=0.5, le=0.95)
    validation_split: float = Field(default=0.1, ge=0.05, le=0.3)
    test_split: float = Field(default=0.1, ge=0.05, le=0.3)
    augmentation: bool = Field(default=False)
    augmentation_factor: float = Field(default=2.0, ge=1.0, le=5.0)
    entity_types: list[str] | None = Field(None)
    label_mapping: dict[str, str] | None = Field(None)


class DatasetListResponse(BaseModel):
    """Response for listing datasets."""

    datasets: list[Dataset]
    total: int


class StartFineTuneRequest(BaseModel):
    """Request to start a fine-tuning job."""

    dataset_id: str = Field(..., description="Dataset ID to use")
    base_model: BaseModelType = Field(
        default=BaseModelType.CLINICAL_BERT,
        description="Base model",
    )
    method: FineTuningMethod = Field(
        default=FineTuningMethod.LORA,
        description="Fine-tuning method",
    )
    task: FineTuningTask = Field(..., description="Target task")
    model_name: str | None = Field(None, description="Custom output model name")

    # Hyperparameters
    epochs: int = Field(default=3, ge=1, le=100)
    batch_size: int = Field(default=16, ge=1, le=128)
    learning_rate: float = Field(default=2e-5, ge=1e-7, le=1e-2)
    warmup_steps: int = Field(default=500, ge=0)
    weight_decay: float = Field(default=0.01, ge=0, le=1)

    # LoRA specific
    lora_r: int = Field(default=8, ge=1, le=64)
    lora_alpha: int = Field(default=32, ge=1, le=128)
    lora_dropout: float = Field(default=0.1, ge=0, le=0.5)

    # Training settings
    eval_steps: int = Field(default=100, ge=10)
    save_steps: int = Field(default=500, ge=50)
    early_stopping_patience: int = Field(default=3, ge=1, le=10)
    seed: int = Field(default=42)
    fp16: bool = Field(default=True)


class JobListResponse(BaseModel):
    """Response for listing jobs."""

    jobs: list[FineTuneJob]
    total: int


class EvaluateModelRequest(BaseModel):
    """Request to evaluate a model."""

    model_id: str = Field(..., description="Model ID to evaluate")
    test_examples: list[dict[str, Any]] | None = Field(
        None,
        description="Optional custom test examples",
    )


class DeployModelRequest(BaseModel):
    """Request to deploy a model."""

    model_id: str = Field(..., description="Model ID to deploy")
    instance_type: str = Field(default="gpu.small", description="Instance type")
    min_replicas: int = Field(default=1, ge=1, le=10)
    max_replicas: int = Field(default=4, ge=1, le=20)
    auto_scale: bool = Field(default=True)


class InferenceRequest(BaseModel):
    """Request for model inference."""

    model_id: str = Field(..., description="Model ID to use")
    texts: list[str] = Field(..., min_length=1, max_length=100, description="Input texts")


class InferenceResponse(BaseModel):
    """Response from inference."""

    model_id: str
    predictions: list[Prediction]
    total_inference_time_ms: float


class ModelListResponse(BaseModel):
    """Response for listing models."""

    models: list[FineTunedModel]
    total: int


class CompareModelsRequest(BaseModel):
    """Request to compare models."""

    model_ids: list[str] = Field(..., min_length=2, max_length=10)


class ServiceStatsResponse(BaseModel):
    """Service statistics response."""

    total_datasets: int
    total_models: int
    total_jobs: int
    active_jobs: int
    total_deployments: int
    active_deployments: int


# ============================================================================
# Dataset Endpoints
# ============================================================================


@router.post(
    "/datasets",
    response_model=Dataset,
    summary="Create a new dataset",
    description="Create a new fine-tuning dataset from clinical documents.",
)
async def create_dataset(request: CreateDatasetRequest) -> Dataset:
    """Create a new fine-tuning dataset.

    Processes annotated clinical documents into a format suitable for
    training NLP models on tasks like NER, classification, etc.
    """
    try:
        service = get_llm_finetuning_service()

        config = DatasetConfig(
            name=request.name,
            description=request.description,
            task=request.task,
            annotation_format=request.annotation_format,
            document_ids=request.document_ids,
            train_split=request.train_split,
            validation_split=request.validation_split,
            test_split=request.test_split,
            augmentation=request.augmentation,
            augmentation_factor=request.augmentation_factor,
            entity_types=request.entity_types,
            label_mapping=request.label_mapping,
        )

        return service.create_dataset(config)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-7: Log full error, return sanitized message
        logger.error(f"Failed to create dataset: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create dataset. Please try again.")


@router.get(
    "/datasets",
    response_model=DatasetListResponse,
    summary="List datasets",
    description="List all fine-tuning datasets, optionally filtered by task or status.",
)
async def list_datasets(
    task: FineTuningTask | None = Query(None, description="Filter by task"),
    status: DatasetStatus | None = Query(None, description="Filter by status"),
) -> DatasetListResponse:
    """List all fine-tuning datasets."""
    service = get_llm_finetuning_service()
    datasets = service.list_datasets(task=task, status=status)
    return DatasetListResponse(datasets=datasets, total=len(datasets))


@router.get(
    "/datasets/{dataset_id}",
    response_model=Dataset,
    summary="Get dataset details",
    description="Get detailed information about a specific dataset.",
)
async def get_dataset(dataset_id: str) -> Dataset:
    """Get dataset details by ID."""
    service = get_llm_finetuning_service()
    dataset = service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return dataset


@router.delete(
    "/datasets/{dataset_id}",
    summary="Delete dataset",
    description="Delete a fine-tuning dataset.",
)
async def delete_dataset(dataset_id: str) -> dict[str, str]:
    """Delete a dataset by ID."""
    service = get_llm_finetuning_service()
    if service.delete_dataset(dataset_id):
        return {"status": "deleted", "dataset_id": dataset_id}
    raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")


# ============================================================================
# Fine-tuning Job Endpoints
# ============================================================================


@router.post(
    "/jobs",
    response_model=FineTuneJob,
    summary="Start fine-tuning job",
    description="Start a new fine-tuning job with specified configuration.",
)
async def start_finetuning_job(request: StartFineTuneRequest) -> FineTuneJob:
    """Start a new fine-tuning job.

    Creates and starts a fine-tuning job that will train a model
    on the specified dataset using the configured hyperparameters.
    """
    try:
        service = get_llm_finetuning_service()

        config = FineTuneConfig(
            dataset_id=request.dataset_id,
            base_model=request.base_model,
            method=request.method,
            task=request.task,
            model_name=request.model_name,
            epochs=request.epochs,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate,
            warmup_steps=request.warmup_steps,
            weight_decay=request.weight_decay,
            lora_r=request.lora_r,
            lora_alpha=request.lora_alpha,
            lora_dropout=request.lora_dropout,
            eval_steps=request.eval_steps,
            save_steps=request.save_steps,
            early_stopping_patience=request.early_stopping_patience,
            seed=request.seed,
            fp16=request.fp16,
        )

        return service.start_finetuning_job(config)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-7: Log full error, return sanitized message
        logger.error(f"Failed to start fine-tuning job: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start job. Please try again.")


@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="List fine-tuning jobs",
    description="List all fine-tuning jobs, optionally filtered by status.",
)
async def list_jobs(
    status: JobStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> JobListResponse:
    """List all fine-tuning jobs."""
    service = get_llm_finetuning_service()
    jobs = service.list_jobs(status=status, limit=limit)
    return JobListResponse(jobs=jobs, total=len(jobs))


@router.get(
    "/jobs/{job_id}",
    response_model=FineTuneJob,
    summary="Get job status",
    description="Get detailed status and metrics for a fine-tuning job.",
)
async def get_job_status(job_id: str) -> FineTuneJob:
    """Get fine-tuning job status by ID."""
    service = get_llm_finetuning_service()
    job = service.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post(
    "/jobs/{job_id}/cancel",
    summary="Cancel fine-tuning job",
    description="Cancel a running or pending fine-tuning job.",
)
async def cancel_job(job_id: str) -> dict[str, str]:
    """Cancel a fine-tuning job."""
    service = get_llm_finetuning_service()
    if service.cancel_job(job_id):
        return {"status": "cancelled", "job_id": job_id}
    raise HTTPException(
        status_code=400,
        detail=f"Cannot cancel job {job_id}. Job may be completed or not found.",
    )


# ============================================================================
# Model Evaluation Endpoints
# ============================================================================


@router.post(
    "/evaluate",
    response_model=EvaluationResult,
    summary="Evaluate model",
    description="Evaluate a fine-tuned model on test data.",
)
async def evaluate_model(request: EvaluateModelRequest) -> EvaluationResult:
    """Evaluate a fine-tuned model.

    Runs evaluation on the model using either the dataset's test split
    or custom provided test examples. Returns comprehensive metrics.
    """
    try:
        service = get_llm_finetuning_service()

        test_data = None
        if request.test_examples:
            # Convert to TestData if provided
            examples = [
                TrainingExample(
                    id=f"test-{i}",
                    text=ex.get("text", ""),
                    labels=ex.get("labels"),
                    split="test",
                )
                for i, ex in enumerate(request.test_examples)
            ]
            model = service.get_model(request.model_id)
            if model:
                test_data = TestData(examples=examples, task=model.task)

        return service.evaluate_model(request.model_id, test_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-7: Log full error, return sanitized message
        logger.error(f"Evaluation failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Evaluation failed. Please try again.")


# ============================================================================
# Deployment Endpoints
# ============================================================================


@router.post(
    "/deploy",
    response_model=Deployment,
    summary="Deploy model",
    description="Deploy a fine-tuned model for inference.",
)
async def deploy_model(request: DeployModelRequest) -> Deployment:
    """Deploy a fine-tuned model.

    Creates an inference endpoint for the model with configurable
    scaling and instance settings.
    """
    try:
        service = get_llm_finetuning_service()

        endpoint_config = {
            "instance_type": request.instance_type,
            "min_replicas": request.min_replicas,
            "max_replicas": request.max_replicas,
            "auto_scale": request.auto_scale,
        }

        return service.deploy_model(request.model_id, endpoint_config)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-7: Log full error, return sanitized message
        logger.error(f"Deployment failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Deployment failed. Please try again.")


@router.get(
    "/deployments/{deployment_id}",
    response_model=Deployment,
    summary="Get deployment status",
    description="Get status and metrics for a model deployment.",
)
async def get_deployment(deployment_id: str) -> Deployment:
    """Get deployment details by ID."""
    service = get_llm_finetuning_service()
    deployment = service.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
    return deployment


@router.post(
    "/deployments/{deployment_id}/stop",
    summary="Stop deployment",
    description="Stop a running model deployment.",
)
async def stop_deployment(deployment_id: str) -> dict[str, str]:
    """Stop a deployment."""
    service = get_llm_finetuning_service()
    if service.stop_deployment(deployment_id):
        return {"status": "stopped", "deployment_id": deployment_id}
    raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")


# ============================================================================
# Inference Endpoints
# ============================================================================


@router.post(
    "/inference",
    response_model=InferenceResponse,
    summary="Run inference",
    description="Run inference on texts using a fine-tuned model.",
)
async def run_inference(request: InferenceRequest) -> InferenceResponse:
    """Run inference with a fine-tuned model.

    Processes input texts and returns predictions based on the
    model's task (NER, classification, etc.).
    """
    try:
        service = get_llm_finetuning_service()
        predictions = service.run_inference(request.model_id, request.texts)

        total_time = sum(p.inference_time_ms for p in predictions)

        return InferenceResponse(
            model_id=request.model_id,
            predictions=predictions,
            total_inference_time_ms=round(total_time, 2),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # VP-Security-7: Log full error, return sanitized message
        logger.error(f"Inference failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Inference failed. Please try again.")


# ============================================================================
# Model Management Endpoints
# ============================================================================


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="List fine-tuned models",
    description="List all fine-tuned models, optionally filtered by task or base model.",
)
async def list_models(
    task: FineTuningTask | None = Query(None, description="Filter by task"),
    base_model: BaseModelType | None = Query(None, description="Filter by base model"),
) -> ModelListResponse:
    """List all fine-tuned models."""
    service = get_llm_finetuning_service()
    models = service.list_models(task=task, base_model=base_model)
    return ModelListResponse(models=models, total=len(models))


@router.get(
    "/models/{model_id}",
    response_model=FineTunedModel,
    summary="Get model details",
    description="Get detailed information about a fine-tuned model.",
)
async def get_model(model_id: str) -> FineTunedModel:
    """Get model details by ID."""
    service = get_llm_finetuning_service()
    model = service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return model


@router.delete(
    "/models/{model_id}",
    summary="Delete model",
    description="Delete a fine-tuned model.",
)
async def delete_model(model_id: str) -> dict[str, str]:
    """Delete a fine-tuned model by ID."""
    service = get_llm_finetuning_service()
    if service.delete_model(model_id):
        return {"status": "deleted", "model_id": model_id}
    raise HTTPException(status_code=404, detail=f"Model {model_id} not found")


@router.post(
    "/models/compare",
    summary="Compare models",
    description="Compare multiple fine-tuned models.",
)
async def compare_models(request: CompareModelsRequest) -> dict[str, Any]:
    """Compare multiple models side by side."""
    service = get_llm_finetuning_service()
    return service.compare_models(request.model_ids)


# ============================================================================
# Service Info Endpoints
# ============================================================================


@router.get(
    "/stats",
    response_model=ServiceStatsResponse,
    summary="Get service statistics",
    description="Get usage statistics for the fine-tuning service.",
)
async def get_service_stats() -> ServiceStatsResponse:
    """Get fine-tuning service statistics."""
    service = get_llm_finetuning_service()
    stats = service.get_stats()
    return ServiceStatsResponse(
        total_datasets=stats.get("total_datasets", 0),
        total_models=stats.get("total_models", 0),
        total_jobs=stats.get("total_jobs", 0),
        active_jobs=stats.get("active_jobs", 0),
        total_deployments=stats.get("total_deployments", 0),
        active_deployments=stats.get("active_deployments", 0),
    )


@router.get(
    "/tasks",
    summary="List supported tasks",
    description="List all supported fine-tuning tasks.",
)
async def list_tasks() -> dict[str, list[dict[str, str]]]:
    """List supported fine-tuning tasks."""
    return {
        "tasks": [
            {"id": FineTuningTask.NER.value, "name": "Named Entity Recognition", "description": "Extract clinical entities from text"},
            {"id": FineTuningTask.TEXT_CLASSIFICATION.value, "name": "Text Classification", "description": "Classify documents by type"},
            {"id": FineTuningTask.RELATION_EXTRACTION.value, "name": "Relation Extraction", "description": "Extract relationships between entities"},
            {"id": FineTuningTask.QUESTION_ANSWERING.value, "name": "Question Answering", "description": "Answer questions about clinical text"},
            {"id": FineTuningTask.SUMMARIZATION.value, "name": "Summarization", "description": "Generate clinical summaries"},
        ]
    }


@router.get(
    "/base-models",
    summary="List supported base models",
    description="List all supported base models for fine-tuning.",
)
async def list_base_models() -> dict[str, list[dict[str, str]]]:
    """List supported base models."""
    return {
        "base_models": [
            {"id": BaseModelType.BIOBERT.value, "name": "BioBERT", "description": "Biomedical domain BERT"},
            {"id": BaseModelType.CLINICAL_BERT.value, "name": "ClinicalBERT", "description": "Clinical notes pre-trained BERT"},
            {"id": BaseModelType.PUBMED_BERT.value, "name": "PubMedBERT", "description": "PubMed abstracts pre-trained BERT"},
            {"id": BaseModelType.BERT_BASE.value, "name": "BERT Base", "description": "Standard BERT base model"},
            {"id": BaseModelType.BERT_LARGE.value, "name": "BERT Large", "description": "Standard BERT large model"},
            {"id": BaseModelType.ROBERTA_BASE.value, "name": "RoBERTa Base", "description": "RoBERTa base model"},
            {"id": BaseModelType.LLAMA_7B.value, "name": "LLaMA 7B", "description": "LLaMA 7 billion parameters"},
            {"id": BaseModelType.LLAMA_13B.value, "name": "LLaMA 13B", "description": "LLaMA 13 billion parameters"},
            {"id": BaseModelType.MISTRAL_7B.value, "name": "Mistral 7B", "description": "Mistral 7 billion parameters"},
        ]
    }


@router.get(
    "/methods",
    summary="List fine-tuning methods",
    description="List all supported fine-tuning methods.",
)
async def list_methods() -> dict[str, list[dict[str, str]]]:
    """List supported fine-tuning methods."""
    return {
        "methods": [
            {"id": FineTuningMethod.FULL.value, "name": "Full Fine-tuning", "description": "Update all model parameters"},
            {"id": FineTuningMethod.LORA.value, "name": "LoRA", "description": "Low-Rank Adaptation - efficient parameter updates"},
            {"id": FineTuningMethod.QLORA.value, "name": "QLoRA", "description": "Quantized LoRA for memory efficiency"},
            {"id": FineTuningMethod.PREFIX_TUNING.value, "name": "Prefix Tuning", "description": "Add trainable prefix tokens"},
            {"id": FineTuningMethod.ADAPTER.value, "name": "Adapter", "description": "Add adapter layers"},
        ]
    }
