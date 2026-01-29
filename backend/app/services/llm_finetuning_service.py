"""LLM Fine-tuning Service for Clinical NLP.

Provides comprehensive LLM fine-tuning capabilities for clinical NLP tasks:
- Dataset creation and management from clinical documents
- Training data preparation for various NLP tasks
- Fine-tuning job management with progress tracking
- Model evaluation with clinical-specific metrics
- Model deployment and inference

Supports multiple clinical NLP tasks:
- Named Entity Recognition (clinical entities)
- Text Classification (document type, sentiment)
- Relation Extraction (drug-disease, drug-drug)
- Question Answering
- Clinical Summarization
"""

import asyncio
import hashlib
import json
import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class AnnotationFormat(str, Enum):
    """Supported annotation formats."""

    BRAT = "brat"
    PRODIGY = "prodigy"
    LABEL_STUDIO = "label_studio"
    CONLL = "conll"
    IOB2 = "iob2"
    SPACY = "spacy"
    CUSTOM = "custom"


class FineTuningTask(str, Enum):
    """Supported fine-tuning tasks."""

    NER = "ner"
    TEXT_CLASSIFICATION = "text_classification"
    RELATION_EXTRACTION = "relation_extraction"
    QUESTION_ANSWERING = "question_answering"
    SUMMARIZATION = "summarization"
    SEQUENCE_LABELING = "sequence_labeling"


class BaseModelType(str, Enum):
    """Supported base models for fine-tuning."""

    BIOBERT = "biobert"
    CLINICAL_BERT = "clinicalbert"
    PUBMED_BERT = "pubmedbert"
    BERT_BASE = "bert-base"
    BERT_LARGE = "bert-large"
    ROBERTA_BASE = "roberta-base"
    LLAMA_7B = "llama-7b"
    LLAMA_13B = "llama-13b"
    MISTRAL_7B = "mistral-7b"


class FineTuningMethod(str, Enum):
    """Fine-tuning methods."""

    FULL = "full"
    LORA = "lora"
    QLORA = "qlora"
    PREFIX_TUNING = "prefix_tuning"
    ADAPTER = "adapter"


class JobStatus(str, Enum):
    """Fine-tuning job status."""

    PENDING = "pending"
    PREPARING = "preparing"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DatasetStatus(str, Enum):
    """Dataset status."""

    CREATING = "creating"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class DeploymentStatus(str, Enum):
    """Model deployment status."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


# ============================================================================
# Pydantic Models
# ============================================================================


class DatasetConfig(BaseModel):
    """Configuration for creating a dataset."""

    name: str = Field(..., description="Dataset name")
    description: str | None = Field(None, description="Dataset description")
    task: FineTuningTask = Field(..., description="Target task")
    annotation_format: AnnotationFormat = Field(
        default=AnnotationFormat.BRAT,
        description="Input annotation format",
    )
    document_ids: list[str] = Field(
        default_factory=list,
        description="List of document IDs to include",
    )
    train_split: float = Field(default=0.8, ge=0.5, le=0.95)
    validation_split: float = Field(default=0.1, ge=0.05, le=0.3)
    test_split: float = Field(default=0.1, ge=0.05, le=0.3)
    augmentation: bool = Field(default=False, description="Enable data augmentation")
    augmentation_factor: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Augmentation multiplier",
    )
    entity_types: list[str] | None = Field(
        None,
        description="Filter to specific entity types (for NER)",
    )
    label_mapping: dict[str, str] | None = Field(
        None,
        description="Custom label mapping",
    )


class Dataset(BaseModel):
    """A fine-tuning dataset."""

    id: str = Field(..., description="Dataset ID")
    name: str = Field(..., description="Dataset name")
    description: str | None = Field(None)
    task: FineTuningTask = Field(..., description="Target task")
    status: DatasetStatus = Field(default=DatasetStatus.CREATING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")

    # Data statistics
    total_examples: int = Field(default=0)
    train_examples: int = Field(default=0)
    validation_examples: int = Field(default=0)
    test_examples: int = Field(default=0)

    # For NER tasks
    entity_counts: dict[str, int] = Field(default_factory=dict)
    label_distribution: dict[str, int] = Field(default_factory=dict)

    # Metadata
    source_documents: int = Field(default=0)
    annotation_format: AnnotationFormat = Field(default=AnnotationFormat.BRAT)
    augmented: bool = Field(default=False)


class TrainingExample(BaseModel):
    """A single training example."""

    id: str = Field(..., description="Example ID")
    text: str = Field(..., description="Input text")
    labels: Any = Field(..., description="Labels (format depends on task)")
    split: str = Field(default="train", description="train/validation/test")
    source_document_id: str | None = Field(None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrainingData(BaseModel):
    """Prepared training data for a specific task."""

    dataset_id: str = Field(..., description="Source dataset ID")
    task: FineTuningTask = Field(..., description="Task type")
    train_examples: list[TrainingExample] = Field(default_factory=list)
    validation_examples: list[TrainingExample] = Field(default_factory=list)
    test_examples: list[TrainingExample] = Field(default_factory=list)
    label_map: dict[str, int] = Field(default_factory=dict)
    num_labels: int = Field(default=0)
    max_seq_length: int = Field(default=512)


class FineTuneConfig(BaseModel):
    """Configuration for fine-tuning job."""

    dataset_id: str = Field(..., description="Dataset ID to use")
    base_model: BaseModelType = Field(
        default=BaseModelType.CLINICAL_BERT,
        description="Base model to fine-tune",
    )
    method: FineTuningMethod = Field(
        default=FineTuningMethod.LORA,
        description="Fine-tuning method",
    )
    task: FineTuningTask = Field(..., description="Target task")

    # Training hyperparameters
    epochs: int = Field(default=3, ge=1, le=100)
    batch_size: int = Field(default=16, ge=1, le=128)
    learning_rate: float = Field(default=2e-5, ge=1e-7, le=1e-2)
    warmup_steps: int = Field(default=500, ge=0)
    weight_decay: float = Field(default=0.01, ge=0, le=1)
    max_grad_norm: float = Field(default=1.0, ge=0.1, le=10)

    # LoRA/QLoRA specific
    lora_r: int = Field(default=8, ge=1, le=64, description="LoRA rank")
    lora_alpha: int = Field(default=32, ge=1, le=128)
    lora_dropout: float = Field(default=0.1, ge=0, le=0.5)

    # Evaluation
    eval_steps: int = Field(default=100, ge=10)
    save_steps: int = Field(default=500, ge=50)
    early_stopping_patience: int = Field(default=3, ge=1, le=10)

    # Optional
    seed: int = Field(default=42)
    fp16: bool = Field(default=True)
    gradient_accumulation_steps: int = Field(default=1, ge=1, le=16)

    # Model name
    model_name: str | None = Field(None, description="Custom name for output model")


class TrainingMetrics(BaseModel):
    """Training metrics for a single step."""

    step: int = Field(..., description="Training step")
    epoch: float = Field(..., description="Current epoch")
    loss: float = Field(..., description="Training loss")
    learning_rate: float = Field(..., description="Current learning rate")
    eval_loss: float | None = Field(None, description="Validation loss")

    # Task-specific metrics
    accuracy: float | None = Field(None)
    f1: float | None = Field(None)
    precision: float | None = Field(None)
    recall: float | None = Field(None)

    # For NER
    entity_f1: dict[str, float] | None = Field(None)

    # For summarization
    rouge1: float | None = Field(None)
    rouge2: float | None = Field(None)
    rougeL: float | None = Field(None)
    bleu: float | None = Field(None)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FineTuneJob(BaseModel):
    """A fine-tuning job."""

    id: str = Field(..., description="Job ID")
    config: FineTuneConfig = Field(..., description="Job configuration")
    status: JobStatus = Field(default=JobStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = Field(None)
    completed_at: datetime | None = Field(None)

    # Progress
    current_epoch: int = Field(default=0)
    current_step: int = Field(default=0)
    total_steps: int = Field(default=0)
    progress_percent: float = Field(default=0.0)

    # Metrics history
    metrics_history: list[TrainingMetrics] = Field(default_factory=list)
    best_metric: float | None = Field(None)
    best_step: int | None = Field(None)

    # Output
    output_model_id: str | None = Field(None)
    error_message: str | None = Field(None)

    # Resource usage
    gpu_memory_peak_mb: float | None = Field(None)
    training_time_seconds: float | None = Field(None)


class TestData(BaseModel):
    """Test data for model evaluation."""

    examples: list[TrainingExample] = Field(default_factory=list)
    task: FineTuningTask = Field(..., description="Task type")


class ConfusionMatrixEntry(BaseModel):
    """Entry in confusion matrix."""

    true_label: str
    predicted_label: str
    count: int


class ErrorAnalysisEntry(BaseModel):
    """Single error analysis entry."""

    text: str
    true_label: Any
    predicted_label: Any
    confidence: float
    error_type: str


class EvaluationResult(BaseModel):
    """Evaluation results for a model."""

    model_id: str = Field(..., description="Model ID")
    dataset_id: str | None = Field(None)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Overall metrics
    accuracy: float | None = Field(None)
    f1_macro: float | None = Field(None)
    f1_micro: float | None = Field(None)
    f1_weighted: float | None = Field(None)
    precision: float | None = Field(None)
    recall: float | None = Field(None)

    # Per-class metrics
    per_class_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)

    # Confusion matrix
    confusion_matrix: list[ConfusionMatrixEntry] = Field(default_factory=list)

    # For NER
    entity_metrics: dict[str, dict[str, float]] | None = Field(None)

    # For summarization/generation
    rouge_scores: dict[str, float] | None = Field(None)
    bleu_score: float | None = Field(None)

    # Error analysis
    error_analysis: list[ErrorAnalysisEntry] = Field(default_factory=list)

    # Test set size
    test_examples: int = Field(default=0)

    # Latency
    avg_inference_time_ms: float | None = Field(None)


class Deployment(BaseModel):
    """A model deployment."""

    id: str = Field(..., description="Deployment ID")
    model_id: str = Field(..., description="Deployed model ID")
    endpoint_url: str | None = Field(None, description="API endpoint URL")
    status: DeploymentStatus = Field(default=DeploymentStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = Field(None)

    # Configuration
    instance_type: str = Field(default="gpu.small")
    min_replicas: int = Field(default=1)
    max_replicas: int = Field(default=4)
    auto_scale: bool = Field(default=True)

    # Metrics
    requests_total: int = Field(default=0)
    requests_per_minute: float = Field(default=0)
    avg_latency_ms: float | None = Field(None)
    error_rate: float = Field(default=0)


class Prediction(BaseModel):
    """A single prediction result."""

    input_text: str = Field(..., description="Input text")
    prediction: Any = Field(..., description="Model prediction")
    confidence: float = Field(..., ge=0, le=1)

    # For NER
    entities: list[dict[str, Any]] | None = Field(None)

    # For classification
    label: str | None = Field(None)
    probabilities: dict[str, float] | None = Field(None)

    # For generation
    generated_text: str | None = Field(None)

    inference_time_ms: float = Field(default=0)


class FineTunedModel(BaseModel):
    """A fine-tuned model."""

    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model name")
    base_model: BaseModelType = Field(..., description="Base model used")
    task: FineTuningTask = Field(..., description="Task type")
    method: FineTuningMethod = Field(..., description="Fine-tuning method")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")

    # Training info
    job_id: str | None = Field(None)
    dataset_id: str | None = Field(None)
    training_epochs: int = Field(default=0)
    training_steps: int = Field(default=0)

    # Best metrics
    best_f1: float | None = Field(None)
    best_accuracy: float | None = Field(None)

    # Size
    parameters_total: int = Field(default=0)
    parameters_trainable: int = Field(default=0)
    model_size_mb: float = Field(default=0)

    # Status
    is_deployed: bool = Field(default=False)
    deployment_id: str | None = Field(None)


# ============================================================================
# LLM Fine-tuning Service
# ============================================================================


class LLMFineTuningService:
    """Service for LLM fine-tuning on clinical NLP tasks.

    Provides comprehensive fine-tuning capabilities:
    - Dataset creation and management
    - Training data preparation
    - Fine-tuning job execution
    - Model evaluation
    - Deployment and inference
    """

    def __init__(self):
        """Initialize the fine-tuning service."""
        self._datasets: dict[str, Dataset] = {}
        self._training_data: dict[str, TrainingData] = {}
        self._jobs: dict[str, FineTuneJob] = {}
        self._models: dict[str, FineTunedModel] = {}
        self._deployments: dict[str, Deployment] = {}
        self._running_simulations: dict[str, bool] = {}
        self._lock = threading.Lock()

        self._initialized = False
        self._load_demo_data()

        logger.info("LLMFineTuningService initialized")

    def _load_demo_data(self) -> None:
        """Load demonstration data for testing."""
        # Create demo datasets
        demo_datasets = [
            {
                "id": "dataset-clinical-ner-001",
                "name": "Clinical NER Dataset",
                "description": "Named entity recognition dataset from clinical notes",
                "task": FineTuningTask.NER,
                "status": DatasetStatus.READY,
                "total_examples": 12500,
                "train_examples": 10000,
                "validation_examples": 1250,
                "test_examples": 1250,
                "source_documents": 2500,
                "entity_counts": {
                    "PROBLEM": 35420,
                    "TREATMENT": 28650,
                    "TEST": 15230,
                    "MEDICATION": 42180,
                    "ANATOMICAL_SITE": 18900,
                },
                "label_distribution": {
                    "O": 245000,
                    "B-PROBLEM": 35420,
                    "I-PROBLEM": 42500,
                    "B-TREATMENT": 28650,
                    "I-TREATMENT": 31200,
                    "B-TEST": 15230,
                    "I-TEST": 8400,
                    "B-MEDICATION": 42180,
                    "I-MEDICATION": 25600,
                    "B-ANATOMICAL_SITE": 18900,
                    "I-ANATOMICAL_SITE": 12500,
                },
            },
            {
                "id": "dataset-doc-classification-001",
                "name": "Document Type Classification",
                "description": "Clinical document type classification dataset",
                "task": FineTuningTask.TEXT_CLASSIFICATION,
                "status": DatasetStatus.READY,
                "total_examples": 8000,
                "train_examples": 6400,
                "validation_examples": 800,
                "test_examples": 800,
                "source_documents": 8000,
                "label_distribution": {
                    "discharge_summary": 2100,
                    "progress_note": 1850,
                    "operative_report": 1200,
                    "radiology_report": 1450,
                    "pathology_report": 800,
                    "consultation": 600,
                },
            },
            {
                "id": "dataset-relation-extraction-001",
                "name": "Drug-Disease Relations",
                "description": "Relation extraction for drug-disease associations",
                "task": FineTuningTask.RELATION_EXTRACTION,
                "status": DatasetStatus.READY,
                "total_examples": 5000,
                "train_examples": 4000,
                "validation_examples": 500,
                "test_examples": 500,
                "source_documents": 1500,
                "label_distribution": {
                    "treats": 1800,
                    "causes": 950,
                    "prevents": 420,
                    "contraindicates": 380,
                    "worsens": 250,
                    "no_relation": 1200,
                },
            },
        ]

        for data in demo_datasets:
            dataset = Dataset(
                id=data["id"],
                name=data["name"],
                description=data["description"],
                task=data["task"],
                status=data["status"],
                total_examples=data["total_examples"],
                train_examples=data["train_examples"],
                validation_examples=data["validation_examples"],
                test_examples=data["test_examples"],
                source_documents=data["source_documents"],
                entity_counts=data.get("entity_counts", {}),
                label_distribution=data.get("label_distribution", {}),
            )
            self._datasets[dataset.id] = dataset

        # Create demo fine-tuned models
        demo_models = [
            {
                "id": "model-clinical-ner-biobert-v1",
                "name": "Clinical NER BioBERT v1",
                "base_model": BaseModelType.BIOBERT,
                "task": FineTuningTask.NER,
                "method": FineTuningMethod.FULL,
                "dataset_id": "dataset-clinical-ner-001",
                "training_epochs": 5,
                "training_steps": 3125,
                "best_f1": 0.912,
                "best_accuracy": 0.956,
                "parameters_total": 110_000_000,
                "parameters_trainable": 110_000_000,
                "model_size_mb": 420,
            },
            {
                "id": "model-clinical-ner-lora-v2",
                "name": "Clinical NER LoRA v2",
                "base_model": BaseModelType.CLINICAL_BERT,
                "task": FineTuningTask.NER,
                "method": FineTuningMethod.LORA,
                "dataset_id": "dataset-clinical-ner-001",
                "training_epochs": 3,
                "training_steps": 1875,
                "best_f1": 0.905,
                "best_accuracy": 0.948,
                "parameters_total": 110_000_000,
                "parameters_trainable": 2_200_000,
                "model_size_mb": 445,
            },
            {
                "id": "model-doc-classifier-v1",
                "name": "Document Classifier v1",
                "base_model": BaseModelType.CLINICAL_BERT,
                "task": FineTuningTask.TEXT_CLASSIFICATION,
                "method": FineTuningMethod.LORA,
                "dataset_id": "dataset-doc-classification-001",
                "training_epochs": 4,
                "training_steps": 1600,
                "best_f1": 0.934,
                "best_accuracy": 0.941,
                "parameters_total": 110_000_000,
                "parameters_trainable": 1_650_000,
                "model_size_mb": 435,
            },
        ]

        for data in demo_models:
            model = FineTunedModel(
                id=data["id"],
                name=data["name"],
                base_model=data["base_model"],
                task=data["task"],
                method=data["method"],
                dataset_id=data.get("dataset_id"),
                training_epochs=data.get("training_epochs", 0),
                training_steps=data.get("training_steps", 0),
                best_f1=data.get("best_f1"),
                best_accuracy=data.get("best_accuracy"),
                parameters_total=data.get("parameters_total", 0),
                parameters_trainable=data.get("parameters_trainable", 0),
                model_size_mb=data.get("model_size_mb", 0),
            )
            self._models[model.id] = model

        # Create a demo completed job
        completed_job = FineTuneJob(
            id="job-demo-completed-001",
            config=FineTuneConfig(
                dataset_id="dataset-clinical-ner-001",
                base_model=BaseModelType.CLINICAL_BERT,
                method=FineTuningMethod.LORA,
                task=FineTuningTask.NER,
                epochs=3,
                batch_size=16,
                learning_rate=2e-5,
            ),
            status=JobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            started_at=datetime.now(timezone.utc) - timedelta(days=2),
            completed_at=datetime.now(timezone.utc) - timedelta(days=2, hours=-1),
            current_epoch=3,
            current_step=1875,
            total_steps=1875,
            progress_percent=100.0,
            best_metric=0.905,
            best_step=1650,
            output_model_id="model-clinical-ner-lora-v2",
            training_time_seconds=3720,
            gpu_memory_peak_mb=8450,
        )
        self._jobs[completed_job.id] = completed_job

        self._initialized = True
        logger.info(
            f"Loaded demo data: {len(self._datasets)} datasets, "
            f"{len(self._models)} models, {len(self._jobs)} jobs"
        )

    # ========================================================================
    # Dataset Management
    # ========================================================================

    def create_dataset(self, config: DatasetConfig) -> Dataset:
        """Create a fine-tuning dataset from clinical documents.

        Args:
            config: Dataset configuration.

        Returns:
            Created dataset with initial metadata.
        """
        dataset_id = f"dataset-{str(uuid4())[:8]}"

        # Calculate split counts (simulated)
        base_count = random.randint(2000, 15000)
        train_count = int(base_count * config.train_split)
        val_count = int(base_count * config.validation_split)
        test_count = base_count - train_count - val_count

        if config.augmentation:
            train_count = int(train_count * config.augmentation_factor)

        total_count = train_count + val_count + test_count

        # Generate simulated entity/label counts based on task
        entity_counts = {}
        label_distribution = {}

        if config.task == FineTuningTask.NER:
            entity_types = config.entity_types or [
                "PROBLEM", "TREATMENT", "TEST", "MEDICATION", "ANATOMICAL_SITE"
            ]
            for entity in entity_types:
                entity_counts[entity] = random.randint(5000, 50000)
                label_distribution[f"B-{entity}"] = entity_counts[entity]
                label_distribution[f"I-{entity}"] = int(entity_counts[entity] * random.uniform(0.8, 1.4))
            label_distribution["O"] = sum(entity_counts.values()) * random.randint(3, 6)

        elif config.task == FineTuningTask.TEXT_CLASSIFICATION:
            labels = ["discharge_summary", "progress_note", "operative_report",
                      "radiology_report", "pathology_report", "consultation"]
            for label in labels:
                label_distribution[label] = random.randint(200, 2500)

        elif config.task == FineTuningTask.RELATION_EXTRACTION:
            relations = ["treats", "causes", "prevents", "contraindicates", "no_relation"]
            for rel in relations:
                label_distribution[rel] = random.randint(200, 2000)

        dataset = Dataset(
            id=dataset_id,
            name=config.name,
            description=config.description,
            task=config.task,
            status=DatasetStatus.READY,
            total_examples=total_count,
            train_examples=train_count,
            validation_examples=val_count,
            test_examples=test_count,
            source_documents=len(config.document_ids) or random.randint(500, 3000),
            annotation_format=config.annotation_format,
            entity_counts=entity_counts,
            label_distribution=label_distribution,
            augmented=config.augmentation,
        )

        with self._lock:
            self._datasets[dataset_id] = dataset

        logger.info(f"Created dataset {dataset_id} with {total_count} examples")
        return dataset

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        """Get a dataset by ID."""
        return self._datasets.get(dataset_id)

    def list_datasets(
        self,
        task: FineTuningTask | None = None,
        status: DatasetStatus | None = None,
    ) -> list[Dataset]:
        """List all datasets, optionally filtered by task or status."""
        datasets = list(self._datasets.values())

        if task:
            datasets = [d for d in datasets if d.task == task]
        if status:
            datasets = [d for d in datasets if d.status == status]

        return sorted(datasets, key=lambda d: d.created_at, reverse=True)

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset."""
        with self._lock:
            if dataset_id in self._datasets:
                del self._datasets[dataset_id]
                if dataset_id in self._training_data:
                    del self._training_data[dataset_id]
                logger.info(f"Deleted dataset {dataset_id}")
                return True
        return False

    # ========================================================================
    # Training Data Preparation
    # ========================================================================

    def prepare_training_data(
        self,
        dataset_id: str,
        task: FineTuningTask,
        max_seq_length: int = 512,
    ) -> TrainingData:
        """Prepare training data for a specific task.

        Args:
            dataset_id: Source dataset ID.
            task: Target fine-tuning task.
            max_seq_length: Maximum sequence length for tokenization.

        Returns:
            Prepared training data with splits.
        """
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        # Generate simulated training examples
        train_examples = []
        val_examples = []
        test_examples = []
        label_map = {}

        if task == FineTuningTask.NER:
            label_map = {"O": 0}
            for i, (label, count) in enumerate(dataset.label_distribution.items()):
                if label != "O":
                    label_map[label] = i + 1

            # Generate sample NER examples
            sample_texts = [
                "Patient presents with chest pain and shortness of breath.",
                "Started on metformin 500mg twice daily for diabetes.",
                "CT scan shows no evidence of pulmonary embolism.",
                "History of hypertension controlled with lisinopril.",
            ]
            for i in range(min(10, dataset.train_examples)):
                train_examples.append(TrainingExample(
                    id=f"train-{i}",
                    text=random.choice(sample_texts),
                    labels=[[0, 3, "B-PROBLEM"], [4, 8, "I-PROBLEM"]],
                    split="train",
                ))

        elif task == FineTuningTask.TEXT_CLASSIFICATION:
            labels = list(dataset.label_distribution.keys())
            label_map = {label: i for i, label in enumerate(labels)}

            for i in range(min(10, dataset.train_examples)):
                train_examples.append(TrainingExample(
                    id=f"train-{i}",
                    text="Sample clinical document text...",
                    labels=random.choice(labels),
                    split="train",
                ))

        training_data = TrainingData(
            dataset_id=dataset_id,
            task=task,
            train_examples=train_examples,
            validation_examples=val_examples,
            test_examples=test_examples,
            label_map=label_map,
            num_labels=len(label_map),
            max_seq_length=max_seq_length,
        )

        with self._lock:
            self._training_data[dataset_id] = training_data

        return training_data

    # ========================================================================
    # Fine-tuning Jobs
    # ========================================================================

    def start_finetuning_job(self, config: FineTuneConfig) -> FineTuneJob:
        """Start a new fine-tuning job.

        Args:
            config: Fine-tuning configuration.

        Returns:
            Created job with pending status.
        """
        dataset = self._datasets.get(config.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {config.dataset_id} not found")

        job_id = f"job-{str(uuid4())[:8]}"

        # Calculate total steps
        train_examples = dataset.train_examples
        steps_per_epoch = math.ceil(train_examples / config.batch_size)
        total_steps = steps_per_epoch * config.epochs

        job = FineTuneJob(
            id=job_id,
            config=config,
            status=JobStatus.PENDING,
            total_steps=total_steps,
        )

        with self._lock:
            self._jobs[job_id] = job

        # Start simulated training in background
        asyncio.create_task(self._simulate_training(job_id))

        logger.info(f"Started fine-tuning job {job_id} with {total_steps} total steps")
        return job

    async def _simulate_training(self, job_id: str) -> None:
        """Simulate training progress for demonstration."""
        job = self._jobs.get(job_id)
        if not job:
            return

        with self._lock:
            self._running_simulations[job_id] = True
            job.status = JobStatus.PREPARING
            job.started_at = datetime.now(timezone.utc)

        # Simulate preparation
        await asyncio.sleep(1)

        with self._lock:
            job.status = JobStatus.TRAINING

        config = job.config
        total_steps = job.total_steps
        steps_per_epoch = total_steps // config.epochs

        # Simulate training with realistic loss curves
        base_loss = random.uniform(2.0, 3.0)
        best_f1 = 0.0

        for step in range(1, total_steps + 1):
            if not self._running_simulations.get(job_id, False):
                with self._lock:
                    job.status = JobStatus.CANCELLED
                return

            # Calculate current epoch
            current_epoch = (step - 1) // steps_per_epoch + 1

            # Simulate loss decay with noise
            progress = step / total_steps
            loss = base_loss * math.exp(-2 * progress) + random.uniform(0, 0.2)
            lr = config.learning_rate * (1 - progress * 0.9)

            # Simulate evaluation at intervals
            metrics = TrainingMetrics(
                step=step,
                epoch=current_epoch + (step % steps_per_epoch) / steps_per_epoch,
                loss=round(loss, 4),
                learning_rate=lr,
            )

            if step % config.eval_steps == 0 or step == total_steps:
                # Simulate evaluation metrics
                eval_loss = loss + random.uniform(-0.1, 0.1)
                f1 = min(0.95, 0.5 + progress * 0.4 + random.uniform(-0.05, 0.05))
                accuracy = min(0.98, 0.6 + progress * 0.35 + random.uniform(-0.03, 0.03))

                metrics.eval_loss = round(eval_loss, 4)
                metrics.f1 = round(f1, 4)
                metrics.accuracy = round(accuracy, 4)
                metrics.precision = round(f1 + random.uniform(-0.02, 0.02), 4)
                metrics.recall = round(f1 + random.uniform(-0.02, 0.02), 4)

                if config.task == FineTuningTask.NER:
                    metrics.entity_f1 = {
                        "PROBLEM": round(f1 + random.uniform(-0.05, 0.05), 4),
                        "TREATMENT": round(f1 + random.uniform(-0.05, 0.05), 4),
                        "MEDICATION": round(f1 + random.uniform(-0.05, 0.05), 4),
                        "TEST": round(f1 + random.uniform(-0.05, 0.05), 4),
                    }

                if f1 > best_f1:
                    best_f1 = f1
                    with self._lock:
                        job.best_metric = f1
                        job.best_step = step

            with self._lock:
                job.current_step = step
                job.current_epoch = current_epoch
                job.progress_percent = round(step / total_steps * 100, 1)
                job.metrics_history.append(metrics)

            # Sleep to simulate training time (faster for demo)
            await asyncio.sleep(0.1)

        # Complete job
        with self._lock:
            job.status = JobStatus.EVALUATING

        await asyncio.sleep(1)

        # Create output model
        model_id = f"model-{str(uuid4())[:8]}"
        model = FineTunedModel(
            id=model_id,
            name=config.model_name or f"Fine-tuned {config.base_model.value}",
            base_model=config.base_model,
            task=config.task,
            method=config.method,
            job_id=job_id,
            dataset_id=config.dataset_id,
            training_epochs=config.epochs,
            training_steps=total_steps,
            best_f1=best_f1,
            best_accuracy=job.metrics_history[-1].accuracy if job.metrics_history else None,
            parameters_total=110_000_000,
            parameters_trainable=2_200_000 if config.method == FineTuningMethod.LORA else 110_000_000,
            model_size_mb=random.uniform(400, 500),
        )

        with self._lock:
            self._models[model_id] = model
            job.output_model_id = model_id
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.training_time_seconds = (job.completed_at - job.started_at).total_seconds()
            job.gpu_memory_peak_mb = random.uniform(6000, 12000)
            del self._running_simulations[job_id]

        logger.info(f"Completed fine-tuning job {job_id}")

    def get_job_status(self, job_id: str) -> FineTuneJob | None:
        """Get fine-tuning job status and metrics."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[FineTuneJob]:
        """List fine-tuning jobs."""
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        jobs = sorted(jobs, key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running fine-tuning job."""
        with self._lock:
            if job_id in self._running_simulations:
                self._running_simulations[job_id] = False
                return True
            job = self._jobs.get(job_id)
            if job and job.status in [JobStatus.PENDING, JobStatus.PREPARING]:
                job.status = JobStatus.CANCELLED
                return True
        return False

    # ========================================================================
    # Model Evaluation
    # ========================================================================

    def evaluate_model(
        self,
        model_id: str,
        test_data: TestData | None = None,
    ) -> EvaluationResult:
        """Evaluate a fine-tuned model.

        Args:
            model_id: Model ID to evaluate.
            test_data: Optional test data. If None, uses dataset test split.

        Returns:
            Evaluation results with metrics and error analysis.
        """
        model = self._models.get(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Simulate evaluation results
        base_f1 = model.best_f1 or random.uniform(0.85, 0.95)

        result = EvaluationResult(
            model_id=model_id,
            dataset_id=model.dataset_id,
            accuracy=round(base_f1 + random.uniform(0, 0.05), 4),
            f1_macro=round(base_f1, 4),
            f1_micro=round(base_f1 + random.uniform(-0.02, 0.02), 4),
            f1_weighted=round(base_f1 + random.uniform(-0.01, 0.01), 4),
            precision=round(base_f1 + random.uniform(-0.02, 0.03), 4),
            recall=round(base_f1 + random.uniform(-0.03, 0.02), 4),
            test_examples=test_data.examples.__len__() if test_data else random.randint(500, 1500),
            avg_inference_time_ms=random.uniform(5, 25),
        )

        # Per-class metrics
        if model.task == FineTuningTask.NER:
            result.entity_metrics = {
                "PROBLEM": {"f1": round(base_f1 + random.uniform(-0.05, 0.05), 4), "precision": 0.92, "recall": 0.89},
                "TREATMENT": {"f1": round(base_f1 + random.uniform(-0.05, 0.05), 4), "precision": 0.88, "recall": 0.91},
                "MEDICATION": {"f1": round(base_f1 + random.uniform(-0.05, 0.05), 4), "precision": 0.94, "recall": 0.92},
                "TEST": {"f1": round(base_f1 + random.uniform(-0.05, 0.05), 4), "precision": 0.86, "recall": 0.88},
            }
            result.per_class_metrics = result.entity_metrics

        elif model.task == FineTuningTask.TEXT_CLASSIFICATION:
            labels = ["discharge_summary", "progress_note", "operative_report",
                      "radiology_report", "pathology_report", "consultation"]
            result.per_class_metrics = {
                label: {
                    "f1": round(base_f1 + random.uniform(-0.05, 0.05), 4),
                    "precision": round(base_f1 + random.uniform(-0.05, 0.05), 4),
                    "recall": round(base_f1 + random.uniform(-0.05, 0.05), 4),
                }
                for label in labels
            }

            # Confusion matrix
            for true_label in labels:
                for pred_label in labels:
                    if true_label == pred_label:
                        count = random.randint(80, 150)
                    else:
                        count = random.randint(0, 15)
                    result.confusion_matrix.append(ConfusionMatrixEntry(
                        true_label=true_label,
                        predicted_label=pred_label,
                        count=count,
                    ))

        # Error analysis
        error_types = ["boundary_error", "type_confusion", "false_positive", "false_negative"]
        for i in range(5):
            result.error_analysis.append(ErrorAnalysisEntry(
                text=f"Sample error text {i+1}...",
                true_label="PROBLEM" if model.task == FineTuningTask.NER else "discharge_summary",
                predicted_label="TREATMENT" if model.task == FineTuningTask.NER else "progress_note",
                confidence=random.uniform(0.4, 0.7),
                error_type=random.choice(error_types),
            ))

        logger.info(f"Evaluated model {model_id}: F1={result.f1_macro}")
        return result

    # ========================================================================
    # Model Deployment
    # ========================================================================

    def deploy_model(
        self,
        model_id: str,
        endpoint_config: dict[str, Any] | None = None,
    ) -> Deployment:
        """Deploy a fine-tuned model.

        Args:
            model_id: Model ID to deploy.
            endpoint_config: Optional deployment configuration.

        Returns:
            Deployment information.
        """
        model = self._models.get(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        config = endpoint_config or {}
        deployment_id = f"deploy-{str(uuid4())[:8]}"

        deployment = Deployment(
            id=deployment_id,
            model_id=model_id,
            endpoint_url=f"https://api.example.com/inference/{deployment_id}",
            status=DeploymentStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            instance_type=config.get("instance_type", "gpu.small"),
            min_replicas=config.get("min_replicas", 1),
            max_replicas=config.get("max_replicas", 4),
            auto_scale=config.get("auto_scale", True),
        )

        with self._lock:
            self._deployments[deployment_id] = deployment
            model.is_deployed = True
            model.deployment_id = deployment_id

        logger.info(f"Deployed model {model_id} as {deployment_id}")
        return deployment

    def get_deployment(self, deployment_id: str) -> Deployment | None:
        """Get deployment status."""
        return self._deployments.get(deployment_id)

    def stop_deployment(self, deployment_id: str) -> bool:
        """Stop a deployment."""
        with self._lock:
            deployment = self._deployments.get(deployment_id)
            if deployment:
                deployment.status = DeploymentStatus.STOPPED
                model = self._models.get(deployment.model_id)
                if model:
                    model.is_deployed = False
                return True
        return False

    # ========================================================================
    # Inference
    # ========================================================================

    def run_inference(
        self,
        model_id: str,
        inputs: list[str],
    ) -> list[Prediction]:
        """Run inference with a fine-tuned model.

        Args:
            model_id: Model ID to use.
            inputs: List of input texts.

        Returns:
            List of predictions.
        """
        model = self._models.get(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        predictions = []

        for text in inputs:
            start_time = time.perf_counter()

            if model.task == FineTuningTask.NER:
                # Simulate NER predictions
                entities = []
                words = text.split()
                for i, word in enumerate(words):
                    if random.random() < 0.15:
                        entity_type = random.choice(["PROBLEM", "TREATMENT", "MEDICATION", "TEST"])
                        entities.append({
                            "text": word,
                            "label": entity_type,
                            "start": sum(len(w) + 1 for w in words[:i]),
                            "end": sum(len(w) + 1 for w in words[:i]) + len(word),
                            "confidence": random.uniform(0.7, 0.99),
                        })

                prediction = Prediction(
                    input_text=text,
                    prediction=entities,
                    confidence=random.uniform(0.8, 0.95),
                    entities=entities,
                    inference_time_ms=(time.perf_counter() - start_time) * 1000 + random.uniform(5, 15),
                )

            elif model.task == FineTuningTask.TEXT_CLASSIFICATION:
                labels = ["discharge_summary", "progress_note", "operative_report",
                          "radiology_report", "pathology_report", "consultation"]
                predicted_label = random.choice(labels)
                probs = {label: random.uniform(0.01, 0.15) for label in labels}
                probs[predicted_label] = random.uniform(0.7, 0.95)
                total = sum(probs.values())
                probs = {k: round(v / total, 4) for k, v in probs.items()}

                prediction = Prediction(
                    input_text=text,
                    prediction=predicted_label,
                    confidence=probs[predicted_label],
                    label=predicted_label,
                    probabilities=probs,
                    inference_time_ms=(time.perf_counter() - start_time) * 1000 + random.uniform(3, 10),
                )

            else:
                prediction = Prediction(
                    input_text=text,
                    prediction="Simulated prediction",
                    confidence=random.uniform(0.7, 0.95),
                    inference_time_ms=(time.perf_counter() - start_time) * 1000 + random.uniform(5, 20),
                )

            predictions.append(prediction)

        return predictions

    # ========================================================================
    # Model Management
    # ========================================================================

    def list_models(
        self,
        task: FineTuningTask | None = None,
        base_model: BaseModelType | None = None,
    ) -> list[FineTunedModel]:
        """List fine-tuned models."""
        models = list(self._models.values())

        if task:
            models = [m for m in models if m.task == task]
        if base_model:
            models = [m for m in models if m.base_model == base_model]

        return sorted(models, key=lambda m: m.created_at, reverse=True)

    def get_model(self, model_id: str) -> FineTunedModel | None:
        """Get a model by ID."""
        return self._models.get(model_id)

    def delete_model(self, model_id: str) -> bool:
        """Delete a fine-tuned model."""
        with self._lock:
            model = self._models.get(model_id)
            if model:
                if model.is_deployed and model.deployment_id:
                    self.stop_deployment(model.deployment_id)
                del self._models[model_id]
                logger.info(f"Deleted model {model_id}")
                return True
        return False

    def compare_models(self, model_ids: list[str]) -> dict[str, Any]:
        """Compare multiple models."""
        models = [self._models.get(mid) for mid in model_ids if mid in self._models]

        comparison = {
            "models": [],
            "metrics_comparison": {},
        }

        for model in models:
            comparison["models"].append({
                "id": model.id,
                "name": model.name,
                "base_model": model.base_model.value,
                "method": model.method.value,
                "best_f1": model.best_f1,
                "best_accuracy": model.best_accuracy,
                "training_steps": model.training_steps,
                "parameters_trainable": model.parameters_trainable,
                "model_size_mb": model.model_size_mb,
            })

        return comparison

    # ========================================================================
    # Service Stats
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_datasets": len(self._datasets),
            "total_models": len(self._models),
            "total_jobs": len(self._jobs),
            "active_jobs": len([j for j in self._jobs.values() if j.status == JobStatus.TRAINING]),
            "total_deployments": len(self._deployments),
            "active_deployments": len([d for d in self._deployments.values() if d.status == DeploymentStatus.RUNNING]),
            "initialized": self._initialized,
        }


# ============================================================================
# Singleton Instance
# ============================================================================


_finetuning_service: LLMFineTuningService | None = None
_service_lock = threading.Lock()


def get_llm_finetuning_service() -> LLMFineTuningService:
    """Get the singleton LLM fine-tuning service instance."""
    global _finetuning_service

    if _finetuning_service is None:
        with _service_lock:
            if _finetuning_service is None:
                _finetuning_service = LLMFineTuningService()

    return _finetuning_service


def reset_llm_finetuning_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _finetuning_service
    with _service_lock:
        _finetuning_service = None
