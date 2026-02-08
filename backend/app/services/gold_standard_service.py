"""Gold Standard Dataset Management Service.

Provides an in-memory store for creating, versioning, and evaluating
gold standard datasets used to benchmark NLP extraction, OMOP mapping,
trial screening, and assertion detection accuracy.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.gold_standard import (
    Annotation,
    EvaluationResult,
    GoldStandardDataset,
    GoldStandardDomain,
    InterAnnotatorAgreement,
    PerClassMetric,
    Prediction,
)

logger = logging.getLogger(__name__)

# Path to pre-built fixture datasets
FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "gold_standard"


class GoldStandardService:
    """In-memory gold standard dataset management service."""

    def __init__(self) -> None:
        # dataset_id -> GoldStandardDataset
        self._datasets: dict[str, GoldStandardDataset] = {}
        # dataset_id -> list[Annotation]
        self._annotations: dict[str, list[Annotation]] = {}
        # (name, version) -> dataset_id  for lookup
        self._name_version_index: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Dataset management
    # ------------------------------------------------------------------

    def create_dataset(
        self,
        name: str,
        domain: GoldStandardDomain,
        description: str = "",
        version: str = "1.0.0",
    ) -> GoldStandardDataset:
        """Create a new gold standard dataset.

        If a dataset with the same (name, version) already exists,
        the existing dataset is returned.
        """
        with self._lock:
            key = (name, version)
            if key in self._name_version_index:
                existing_id = self._name_version_index[key]
                logger.info(f"Dataset {name} v{version} already exists")
                return self._datasets[existing_id]

            dataset_id = str(uuid4())
            dataset = GoldStandardDataset(
                id=dataset_id,
                name=name,
                domain=domain,
                description=description,
                version=version,
            )
            self._datasets[dataset_id] = dataset
            self._annotations[dataset_id] = []
            self._name_version_index[key] = dataset_id
            logger.info(f"Created gold standard dataset {name} v{version} ({domain.value})")
            return dataset

    def get_dataset(
        self,
        name: str,
        version: str | None = None,
    ) -> GoldStandardDataset | None:
        """Retrieve a dataset by name and optional version.

        If version is None, returns the latest version by creation time.
        """
        if version is not None:
            key = (name, version)
            dataset_id = self._name_version_index.get(key)
            if dataset_id is None:
                return None
            return self._datasets[dataset_id]

        # Find latest version for this name
        candidates = [
            self._datasets[did]
            for (n, _v), did in self._name_version_index.items()
            if n == name
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda d: d.created_at)

    def list_datasets(
        self,
        domain: GoldStandardDomain | None = None,
    ) -> list[GoldStandardDataset]:
        """List all datasets, optionally filtered by domain."""
        datasets = list(self._datasets.values())
        if domain is not None:
            datasets = [d for d in datasets if d.domain == domain]
        return datasets

    def get_annotations(self, dataset_id: str) -> list[Annotation]:
        """Return all annotations for a dataset."""
        return self._annotations.get(dataset_id, [])

    # ------------------------------------------------------------------
    # Annotation management
    # ------------------------------------------------------------------

    def add_annotation(
        self,
        dataset_id: str,
        input_data: dict[str, Any],
        expected_output: dict[str, Any],
        annotator_id: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> Annotation:
        """Add an annotation to a dataset.

        Raises:
            ValueError: If the dataset_id does not exist.
        """
        with self._lock:
            if dataset_id not in self._datasets:
                raise ValueError(f"Dataset {dataset_id} not found")

            annotation = Annotation(
                id=str(uuid4()),
                dataset_id=dataset_id,
                input_data=input_data,
                expected_output=expected_output,
                annotator_id=annotator_id,
                metadata=metadata or {},
            )
            self._annotations[dataset_id].append(annotation)

            # Update annotation count on the dataset
            ds = self._datasets[dataset_id]
            self._datasets[dataset_id] = ds.model_copy(
                update={"annotation_count": len(self._annotations[dataset_id])}
            )

            return annotation

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_against(
        self,
        dataset_id: str,
        predictions: list[Prediction],
    ) -> EvaluationResult:
        """Compare predictions against gold standard annotations.

        Each prediction references an annotation by ID. The comparison
        checks whether ``predicted_output`` matches ``expected_output``.

        For structured outputs with a ``label`` key, per-class metrics
        are also computed.

        Raises:
            ValueError: If the dataset_id does not exist.
        """
        if dataset_id not in self._datasets:
            raise ValueError(f"Dataset {dataset_id} not found")

        annotations_by_id = {a.id: a for a in self._annotations.get(dataset_id, [])}

        correct = 0
        incorrect = 0
        total = len(predictions)

        # For per-class metrics: track TP, FP, FN per class
        class_tp: dict[str, int] = defaultdict(int)
        class_fp: dict[str, int] = defaultdict(int)
        class_fn: dict[str, int] = defaultdict(int)
        class_support: dict[str, int] = defaultdict(int)

        # Confusion data: {actual_label: {predicted_label: count}}
        confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for pred in predictions:
            ann = annotations_by_id.get(pred.annotation_id)
            if ann is None:
                incorrect += 1
                continue

            expected = ann.expected_output
            predicted = pred.predicted_output

            # Exact match check
            if predicted == expected:
                correct += 1
            else:
                incorrect += 1

            # Extract labels for per-class tracking
            expected_label = expected.get("label")
            predicted_label = predicted.get("label")

            if expected_label is not None:
                class_support[expected_label] += 1

                if predicted_label is not None:
                    confusion[expected_label][predicted_label] += 1

                    if predicted_label == expected_label:
                        class_tp[expected_label] += 1
                    else:
                        class_fn[expected_label] += 1
                        class_fp[predicted_label] += 1
                else:
                    class_fn[expected_label] += 1

        # Compute per-class precision / recall / F1
        all_classes = sorted(
            set(class_support.keys()) | set(class_fp.keys())
        )
        per_class_metrics: list[PerClassMetric] = []
        for cls in all_classes:
            tp = class_tp[cls]
            fp = class_fp[cls]
            fn = class_fn[cls]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            per_class_metrics.append(
                PerClassMetric(
                    class_name=cls,
                    precision=round(precision, 4),
                    recall=round(recall, 4),
                    f1=round(f1, 4),
                    support=class_support.get(cls, 0),
                )
            )

        accuracy = correct / total if total > 0 else 0.0

        return EvaluationResult(
            dataset_id=dataset_id,
            total=total,
            correct=correct,
            incorrect=incorrect,
            accuracy=round(accuracy, 4),
            per_class_metrics=per_class_metrics,
            confusion_data={
                actual: dict(preds) for actual, preds in confusion.items()
            },
        )

    # ------------------------------------------------------------------
    # Inter-annotator agreement
    # ------------------------------------------------------------------

    def get_inter_annotator_agreement(
        self,
        dataset_id: str,
    ) -> InterAnnotatorAgreement:
        """Compute inter-annotator agreement metrics for a dataset.

        Groups annotations by input_data and compares expected_output
        across annotators. Returns pairwise agreement and Cohen's kappa.

        Raises:
            ValueError: If the dataset_id does not exist or has < 2 annotators.
        """
        if dataset_id not in self._datasets:
            raise ValueError(f"Dataset {dataset_id} not found")

        annotations = self._annotations.get(dataset_id, [])
        annotators = list({a.annotator_id for a in annotations})

        if len(annotators) < 2:
            raise ValueError(
                f"Need at least 2 annotators for IAA; found {len(annotators)}"
            )

        # Group annotations by input_data key (serialized)
        by_input: dict[str, list[Annotation]] = defaultdict(list)
        for ann in annotations:
            key = json.dumps(ann.input_data, sort_keys=True)
            by_input[key].append(ann)

        # Compute pairwise agreement
        agree_count = 0
        total_pairs = 0

        for _input_key, anns in by_input.items():
            if len(anns) < 2:
                continue
            for i in range(len(anns)):
                for j in range(i + 1, len(anns)):
                    total_pairs += 1
                    if anns[i].expected_output == anns[j].expected_output:
                        agree_count += 1

        pairwise_agreement = agree_count / total_pairs if total_pairs > 0 else 0.0

        # Simplified Cohen's kappa: kappa = (po - pe) / (1 - pe)
        # where po = observed agreement, pe = expected agreement by chance
        po = pairwise_agreement

        # Estimate pe from label distribution
        label_counts: dict[str, int] = defaultdict(int)
        total_labels = 0
        for anns in by_input.values():
            for ann in anns:
                label = json.dumps(ann.expected_output, sort_keys=True)
                label_counts[label] += 1
                total_labels += 1

        if total_labels > 0:
            pe = sum(
                (count / total_labels) ** 2 for count in label_counts.values()
            )
        else:
            pe = 0.0

        kappa = (po - pe) / (1 - pe) if (1 - pe) > 0 else 1.0

        return InterAnnotatorAgreement(
            dataset_id=dataset_id,
            annotator_count=len(annotators),
            annotators=sorted(annotators),
            pairwise_agreement=round(pairwise_agreement, 4),
            cohens_kappa=round(kappa, 4),
        )

    # ------------------------------------------------------------------
    # Fixture loading
    # ------------------------------------------------------------------

    def load_fixture(self, filename: str) -> GoldStandardDataset:
        """Load a pre-built fixture dataset from the fixtures directory.

        The JSON file must contain:
        - metadata: {name, domain, description, version}
        - annotations: [{input_data, expected_output, annotator_id?, metadata?}]

        Returns the created dataset with all annotations loaded.

        Raises:
            FileNotFoundError: If the fixture file does not exist.
            ValueError: If the fixture format is invalid.
        """
        filepath = FIXTURES_DIR / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Fixture file not found: {filepath}")

        with open(filepath) as f:
            data = json.load(f)

        meta = data.get("metadata", {})
        name = meta.get("name", filepath.stem)
        domain_str = meta.get("domain", "nlp_extraction")
        description = meta.get("description", "")
        version = meta.get("version", "1.0.0")

        domain = GoldStandardDomain(domain_str)
        dataset = self.create_dataset(
            name=name,
            domain=domain,
            description=description,
            version=version,
        )

        for ann_data in data.get("annotations", []):
            self.add_annotation(
                dataset_id=dataset.id,
                input_data=ann_data["input_data"],
                expected_output=ann_data["expected_output"],
                annotator_id=ann_data.get("annotator_id", "system"),
                metadata=ann_data.get("metadata", {}),
            )

        # Refresh dataset to get updated annotation_count
        dataset = self._datasets[dataset.id]
        logger.info(
            f"Loaded fixture {filename}: {dataset.annotation_count} annotations"
        )
        return dataset


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_service: GoldStandardService | None = None
_service_lock = threading.Lock()


def get_gold_standard_service() -> GoldStandardService:
    """Return the singleton GoldStandardService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = GoldStandardService()
    return _service


def reset_gold_standard_service() -> None:
    """Reset the singleton (useful for test isolation)."""
    global _service
    with _service_lock:
        _service = None
