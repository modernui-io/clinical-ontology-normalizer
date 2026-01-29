"""Federated Learning Service for Cross-Organization Model Training.

Implements privacy-preserving federated learning capabilities:
- Federation management (create/join federations)
- Training protocols (FedAvg, FedProx)
- Secure aggregation simulation
- Differential privacy integration
- Model types for healthcare predictions

This implementation simulates federated learning without actual network
communication, using mock multi-organization data for demonstration.
"""

import hashlib
import logging
import secrets
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class FederationRole(str, Enum):
    """Role of a participant in a federation."""

    COORDINATOR = "coordinator"
    PARTICIPANT = "participant"


class FederationStatus(str, Enum):
    """Status of a federation."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    TRAINING = "training"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RoundStatus(str, Enum):
    """Status of a training round."""

    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelType(str, Enum):
    """Types of federated models."""

    READMISSION_PREDICTION = "readmission_prediction"
    MORTALITY_RISK = "mortality_risk"
    LENGTH_OF_STAY = "length_of_stay"
    PHENOTYPING = "phenotyping"
    TREATMENT_RESPONSE = "treatment_response"


class AggregationProtocol(str, Enum):
    """Federated learning aggregation protocols."""

    FED_AVG = "fed_avg"
    FED_PROX = "fed_prox"
    SECURE_AGG = "secure_aggregation"


class PrivacyMechanism(str, Enum):
    """Differential privacy mechanisms."""

    NONE = "none"
    LOCAL_DP = "local_dp"
    CENTRAL_DP = "central_dp"
    GRADIENT_CLIPPING = "gradient_clipping"


# ============================================================================
# Pydantic Models
# ============================================================================


class Organization(BaseModel):
    """Organization participating in federated learning."""

    org_id: str = Field(..., description="Unique organization identifier")
    name: str = Field(..., description="Organization name")
    type: str = Field(
        default="hospital", description="Organization type (hospital, clinic, etc.)"
    )
    location: str | None = Field(None, description="Geographic location")
    data_size: int = Field(default=0, description="Estimated number of samples")
    contact_email: str | None = Field(None, description="Contact email")
    public_key: str | None = Field(None, description="Public key for secure comm")


class FederationConfig(BaseModel):
    """Configuration for creating a federation."""

    name: str = Field(..., description="Federation name")
    description: str | None = Field(None, description="Federation description")
    model_type: ModelType = Field(
        default=ModelType.READMISSION_PREDICTION, description="Type of model to train"
    )
    aggregation_protocol: AggregationProtocol = Field(
        default=AggregationProtocol.FED_AVG, description="Aggregation protocol"
    )
    privacy_mechanism: PrivacyMechanism = Field(
        default=PrivacyMechanism.GRADIENT_CLIPPING, description="Privacy mechanism"
    )
    min_participants: int = Field(
        default=3, ge=2, description="Minimum participants to start training"
    )
    max_participants: int = Field(
        default=100, ge=2, description="Maximum participants allowed"
    )
    min_samples_per_participant: int = Field(
        default=100, ge=10, description="Minimum samples required per participant"
    )
    rounds_total: int = Field(
        default=10, ge=1, le=100, description="Total training rounds"
    )
    local_epochs: int = Field(
        default=5, ge=1, le=50, description="Local epochs per round"
    )
    learning_rate: float = Field(
        default=0.01, gt=0, le=1.0, description="Global learning rate"
    )
    batch_size: int = Field(default=32, ge=1, le=512, description="Local batch size")
    privacy_budget_epsilon: float = Field(
        default=1.0, gt=0, description="Differential privacy epsilon"
    )
    privacy_budget_delta: float = Field(
        default=1e-5, gt=0, le=1.0, description="Differential privacy delta"
    )
    gradient_clip_norm: float = Field(
        default=1.0, gt=0, description="Gradient clipping norm"
    )
    proximal_mu: float = Field(
        default=0.01, ge=0, description="FedProx proximal term coefficient"
    )
    feature_names: list[str] = Field(
        default_factory=list, description="Feature names for the model"
    )


class Federation(BaseModel):
    """A federation of organizations for collaborative learning."""

    federation_id: str = Field(..., description="Unique federation identifier")
    name: str = Field(..., description="Federation name")
    description: str | None = Field(None)
    config: FederationConfig = Field(..., description="Federation configuration")
    status: FederationStatus = Field(default=FederationStatus.INITIALIZING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")
    coordinator_id: str | None = Field(None, description="Coordinator org ID")
    current_round: int = Field(default=0, description="Current training round")
    total_samples: int = Field(default=0, description="Total samples across all orgs")
    privacy_budget_spent: float = Field(default=0.0, description="Privacy budget used")


class Participant(BaseModel):
    """A participant in a federation."""

    participant_id: str = Field(..., description="Unique participant identifier")
    federation_id: str = Field(..., description="Federation ID")
    org: Organization = Field(..., description="Organization details")
    role: FederationRole = Field(default=FederationRole.PARTICIPANT)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="active")
    last_update_at: datetime | None = Field(None)
    rounds_participated: int = Field(default=0)
    total_samples: int = Field(default=0)
    contribution_score: float = Field(default=0.0)
    is_verified: bool = Field(default=False)


class GlobalModel(BaseModel):
    """Global model shared across federation."""

    model_id: str = Field(..., description="Model identifier")
    federation_id: str = Field(..., description="Federation ID")
    version: int = Field(default=0, description="Model version (increments each round)")
    model_type: ModelType = Field(..., description="Type of model")
    architecture: dict[str, Any] = Field(
        default_factory=dict, description="Model architecture details"
    )
    weights: dict[str, list[float]] = Field(
        default_factory=dict, description="Model weights (serialized)"
    )
    feature_names: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    training_samples: int = Field(default=0)
    performance_metrics: dict[str, float] = Field(default_factory=dict)


class ModelUpdate(BaseModel):
    """Local model update from a participant."""

    update_id: str = Field(..., description="Unique update identifier")
    participant_id: str = Field(..., description="Participant who created update")
    federation_id: str = Field(..., description="Federation ID")
    round_id: str = Field(..., description="Training round ID")
    gradient_updates: dict[str, list[float]] = Field(
        default_factory=dict, description="Gradient updates"
    )
    num_samples: int = Field(..., description="Number of samples used")
    local_loss: float = Field(..., description="Local training loss")
    local_metrics: dict[str, float] = Field(
        default_factory=dict, description="Local evaluation metrics"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    noise_added: bool = Field(default=False, description="Whether DP noise was added")
    checksum: str = Field(default="", description="Update integrity checksum")


class AggregatedUpdate(BaseModel):
    """Aggregated update from multiple participants."""

    aggregation_id: str = Field(..., description="Aggregation identifier")
    federation_id: str = Field(..., description="Federation ID")
    round_id: str = Field(..., description="Training round ID")
    aggregated_weights: dict[str, list[float]] = Field(
        default_factory=dict, description="Aggregated model weights"
    )
    participating_count: int = Field(..., description="Number of participants")
    total_samples: int = Field(..., description="Total samples used")
    weighted_loss: float = Field(..., description="Weighted average loss")
    aggregation_method: AggregationProtocol = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrainingRound(BaseModel):
    """A single training round in federated learning."""

    round_id: str = Field(..., description="Round identifier")
    federation_id: str = Field(..., description="Federation ID")
    round_number: int = Field(..., description="Round number (1-indexed)")
    status: RoundStatus = Field(default=RoundStatus.WAITING)
    started_at: datetime | None = Field(None)
    completed_at: datetime | None = Field(None)
    participating_orgs: list[str] = Field(
        default_factory=list, description="Orgs participating this round"
    )
    updates_received: int = Field(default=0)
    updates_expected: int = Field(default=0)
    global_loss: float | None = Field(None)
    global_metrics: dict[str, float] = Field(default_factory=dict)
    privacy_budget_used: float = Field(default=0.0)


class Distribution(BaseModel):
    """Model distribution to a participant."""

    distribution_id: str = Field(..., description="Distribution identifier")
    federation_id: str = Field(..., description="Federation ID")
    participant_id: str = Field(..., description="Target participant")
    model_version: int = Field(..., description="Model version distributed")
    distributed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = Field(default=False)
    acknowledged_at: datetime | None = Field(None)


class FederatedMetrics(BaseModel):
    """Metrics for a federated training session."""

    federation_id: str
    current_round: int
    total_rounds: int
    global_loss_history: list[float] = Field(default_factory=list)
    global_auc_history: list[float] = Field(default_factory=list)
    global_accuracy_history: list[float] = Field(default_factory=list)
    participants_per_round: list[int] = Field(default_factory=list)
    samples_per_round: list[int] = Field(default_factory=list)
    privacy_budget_spent: float
    convergence_rate: float | None = None
    estimated_rounds_remaining: int | None = None


# ============================================================================
# Mock Data Generation
# ============================================================================


class MockDataGenerator:
    """Generate mock data for federated learning simulation."""

    @staticmethod
    def generate_patient_features(
        num_samples: int, org_id: str, model_type: ModelType
    ) -> pd.DataFrame:
        """Generate mock patient features for a given organization.

        Each organization has slightly different data distributions
        to simulate real-world heterogeneity.
        """
        # Use org_id as seed for reproducible but varied data
        seed = int(hashlib.md5(org_id.encode()).hexdigest()[:8], 16) % 2**31
        np.random.seed(seed)

        # Base distributions with org-specific shifts
        org_shift = (seed % 10) / 10.0  # 0-1 shift factor

        if model_type == ModelType.READMISSION_PREDICTION:
            data = {
                "age": np.clip(
                    np.random.normal(65 + org_shift * 10, 15, num_samples), 18, 100
                ).astype(int),
                "length_of_stay": np.clip(
                    np.random.exponential(5 + org_shift * 2, num_samples), 1, 60
                ).astype(int),
                "comorbidity_count": np.random.poisson(2 + org_shift, num_samples),
                "prior_admissions": np.random.poisson(1 + org_shift * 0.5, num_samples),
                "ed_visits_6mo": np.random.poisson(1 + org_shift * 0.3, num_samples),
                "medication_count": np.clip(
                    np.random.poisson(8 + org_shift * 2, num_samples), 0, 30
                ),
                "hemoglobin": np.clip(
                    np.random.normal(12 - org_shift, 2, num_samples), 5, 18
                ),
                "creatinine": np.clip(
                    np.random.exponential(1 + org_shift * 0.5, num_samples), 0.3, 10
                ),
            }

            # Generate target based on features
            risk_score = (
                0.02 * data["age"]
                + 0.05 * data["length_of_stay"]
                + 0.15 * data["comorbidity_count"]
                + 0.2 * data["prior_admissions"]
                + 0.1 * data["ed_visits_6mo"]
                + 0.03 * data["medication_count"]
                - 0.05 * data["hemoglobin"]
                + 0.1 * data["creatinine"]
            )
            risk_score = (risk_score - risk_score.min()) / (
                risk_score.max() - risk_score.min() + 1e-6
            )
            data["readmitted_30d"] = (
                np.random.random(num_samples) < risk_score * 0.3 + 0.1
            ).astype(int)

        elif model_type == ModelType.MORTALITY_RISK:
            data = {
                "age": np.clip(
                    np.random.normal(70 + org_shift * 8, 12, num_samples), 18, 100
                ).astype(int),
                "charlson_score": np.random.poisson(3 + org_shift, num_samples),
                "apache_score": np.clip(
                    np.random.normal(15 + org_shift * 5, 8, num_samples), 0, 40
                ).astype(int),
                "icu_los": np.clip(
                    np.random.exponential(4 + org_shift * 2, num_samples), 0, 30
                ).astype(int),
                "mechanical_vent": (np.random.random(num_samples) < 0.3 + org_shift * 0.1).astype(int),
                "vasopressors": (np.random.random(num_samples) < 0.25 + org_shift * 0.1).astype(int),
                "creatinine": np.clip(
                    np.random.exponential(1.5 + org_shift, num_samples), 0.3, 15
                ),
                "lactate": np.clip(
                    np.random.exponential(2 + org_shift, num_samples), 0.5, 20
                ),
            }

            # Generate mortality target
            risk_score = (
                0.01 * data["age"]
                + 0.12 * data["charlson_score"]
                + 0.03 * data["apache_score"]
                + 0.08 * data["icu_los"]
                + 0.25 * data["mechanical_vent"]
                + 0.2 * data["vasopressors"]
                + 0.05 * data["creatinine"]
                + 0.1 * data["lactate"]
            )
            risk_score = (risk_score - risk_score.min()) / (
                risk_score.max() - risk_score.min() + 1e-6
            )
            data["mortality"] = (
                np.random.random(num_samples) < risk_score * 0.25 + 0.05
            ).astype(int)

        else:  # Default phenotyping
            data = {
                "age": np.clip(
                    np.random.normal(55 + org_shift * 15, 18, num_samples), 18, 100
                ).astype(int),
                "bmi": np.clip(
                    np.random.normal(28 + org_shift * 3, 6, num_samples), 15, 50
                ),
                "systolic_bp": np.clip(
                    np.random.normal(130 + org_shift * 10, 20, num_samples), 80, 200
                ).astype(int),
                "diastolic_bp": np.clip(
                    np.random.normal(80 + org_shift * 5, 12, num_samples), 50, 120
                ).astype(int),
                "fasting_glucose": np.clip(
                    np.random.normal(100 + org_shift * 20, 30, num_samples), 60, 300
                ),
                "hba1c": np.clip(
                    np.random.normal(6 + org_shift * 1.5, 1.5, num_samples), 4, 14
                ),
                "total_cholesterol": np.clip(
                    np.random.normal(200 + org_shift * 30, 40, num_samples), 100, 350
                ),
                "smoking_status": (np.random.random(num_samples) < 0.2 + org_shift * 0.1).astype(int),
            }

            # Generate phenotype (diabetes risk)
            risk_score = (
                0.01 * data["age"]
                + 0.05 * data["bmi"]
                + 0.02 * data["systolic_bp"]
                + 0.03 * data["fasting_glucose"]
                + 0.3 * data["hba1c"]
                + 0.01 * data["total_cholesterol"]
                + 0.1 * data["smoking_status"]
            )
            risk_score = (risk_score - risk_score.min()) / (
                risk_score.max() - risk_score.min() + 1e-6
            )
            data["diabetes_phenotype"] = (
                np.random.random(num_samples) < risk_score * 0.4 + 0.1
            ).astype(int)

        return pd.DataFrame(data)

    @staticmethod
    def generate_mock_organizations(count: int = 5) -> list[Organization]:
        """Generate mock organizations for testing."""
        hospital_names = [
            "Metro General Hospital",
            "University Medical Center",
            "Regional Health System",
            "Community Hospital Network",
            "Academic Medical Center",
            "Veterans Health Administration",
            "Children's Hospital",
            "County General Hospital",
            "Sacred Heart Medical Center",
            "Providence Health System",
        ]

        locations = [
            "Northeast",
            "Southeast",
            "Midwest",
            "Southwest",
            "West Coast",
            "Pacific Northwest",
            "Mountain Region",
            "Great Plains",
            "Gulf Coast",
            "Mid-Atlantic",
        ]

        orgs = []
        for i in range(min(count, len(hospital_names))):
            org_id = f"org-{str(uuid4())[:8]}"
            orgs.append(
                Organization(
                    org_id=org_id,
                    name=hospital_names[i],
                    type="hospital",
                    location=locations[i % len(locations)],
                    data_size=np.random.randint(5000, 50000),
                    contact_email=f"admin@{hospital_names[i].lower().replace(' ', '')}.org",
                    public_key=secrets.token_hex(32),
                )
            )
        return orgs


# ============================================================================
# Privacy Mechanisms
# ============================================================================


class PrivacyEngine:
    """Implements differential privacy mechanisms."""

    def __init__(
        self,
        mechanism: PrivacyMechanism,
        epsilon: float = 1.0,
        delta: float = 1e-5,
        clip_norm: float = 1.0,
    ):
        """Initialize privacy engine.

        Args:
            mechanism: Type of privacy mechanism.
            epsilon: Privacy budget epsilon.
            delta: Privacy budget delta.
            clip_norm: Gradient clipping norm.
        """
        self.mechanism = mechanism
        self.epsilon = epsilon
        self.delta = delta
        self.clip_norm = clip_norm

    def clip_gradients(self, gradients: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Clip gradients to bounded norm."""
        if self.mechanism == PrivacyMechanism.NONE:
            return gradients

        clipped = {}
        for layer, grad in gradients.items():
            grad_array = np.array(grad)
            norm = np.linalg.norm(grad_array)
            if norm > self.clip_norm:
                grad_array = grad_array * (self.clip_norm / norm)
            clipped[layer] = grad_array
        return clipped

    def add_noise(
        self, gradients: dict[str, np.ndarray], num_samples: int
    ) -> dict[str, np.ndarray]:
        """Add calibrated Gaussian noise for differential privacy."""
        if self.mechanism in [PrivacyMechanism.NONE, PrivacyMechanism.GRADIENT_CLIPPING]:
            return gradients

        # Compute noise scale using Gaussian mechanism
        sensitivity = self.clip_norm / num_samples
        noise_scale = sensitivity * np.sqrt(2 * np.log(1.25 / self.delta)) / self.epsilon

        noisy = {}
        for layer, grad in gradients.items():
            grad_array = np.array(grad)
            noise = np.random.normal(0, noise_scale, grad_array.shape)
            noisy[layer] = grad_array + noise
        return noisy

    def compute_privacy_spent(self, num_queries: int) -> float:
        """Compute privacy budget spent using composition theorem."""
        if self.mechanism == PrivacyMechanism.NONE:
            return 0.0

        # Simple composition (advanced composition would be tighter)
        return self.epsilon * np.sqrt(2 * num_queries * np.log(1 / self.delta))


# ============================================================================
# Aggregation Protocols
# ============================================================================


class AggregationEngine:
    """Implements federated aggregation protocols."""

    def __init__(self, protocol: AggregationProtocol, proximal_mu: float = 0.01):
        """Initialize aggregation engine.

        Args:
            protocol: Aggregation protocol to use.
            proximal_mu: FedProx proximal term coefficient.
        """
        self.protocol = protocol
        self.proximal_mu = proximal_mu

    def aggregate(
        self,
        updates: list[ModelUpdate],
        global_weights: dict[str, list[float]] | None = None,
    ) -> dict[str, np.ndarray]:
        """Aggregate model updates from participants.

        Args:
            updates: List of model updates from participants.
            global_weights: Current global model weights (for FedProx).

        Returns:
            Aggregated model weights.
        """
        if not updates:
            return {}

        if self.protocol == AggregationProtocol.FED_AVG:
            return self._fed_avg(updates)
        elif self.protocol == AggregationProtocol.FED_PROX:
            return self._fed_prox(updates, global_weights)
        elif self.protocol == AggregationProtocol.SECURE_AGG:
            return self._secure_aggregation(updates)
        else:
            return self._fed_avg(updates)

    def _fed_avg(self, updates: list[ModelUpdate]) -> dict[str, np.ndarray]:
        """Federated Averaging (FedAvg).

        Weighted average of gradients by number of samples.
        """
        total_samples = sum(u.num_samples for u in updates)
        if total_samples == 0:
            return {}

        aggregated = {}
        for update in updates:
            weight = update.num_samples / total_samples
            for layer, grads in update.gradient_updates.items():
                grad_array = np.array(grads)
                if layer in aggregated:
                    aggregated[layer] += weight * grad_array
                else:
                    aggregated[layer] = weight * grad_array

        return aggregated

    def _fed_prox(
        self,
        updates: list[ModelUpdate],
        global_weights: dict[str, list[float]] | None,
    ) -> dict[str, np.ndarray]:
        """FedProx with proximal term.

        Adds regularization towards global model to handle heterogeneity.
        """
        # Start with FedAvg
        aggregated = self._fed_avg(updates)

        # Add proximal regularization if global weights available
        if global_weights:
            for layer in aggregated:
                if layer in global_weights:
                    global_w = np.array(global_weights[layer])
                    aggregated[layer] += self.proximal_mu * (
                        global_w - aggregated[layer]
                    )

        return aggregated

    def _secure_aggregation(self, updates: list[ModelUpdate]) -> dict[str, np.ndarray]:
        """Simulated secure aggregation.

        In production, this would use cryptographic protocols.
        For simulation, we add extra random masking that cancels out.
        """
        # Simulate secure aggregation by adding/removing masks
        num_participants = len(updates)

        # Generate pairwise masks (would be negotiated in real protocol)
        masks = []
        for i in range(num_participants):
            mask = {}
            for layer in updates[0].gradient_updates:
                grad_shape = np.array(updates[0].gradient_updates[layer]).shape
                mask[layer] = np.random.randn(*grad_shape)
            masks.append(mask)

        # Apply masks (in real protocol, pairs would exchange masked values)
        masked_updates = []
        for i, update in enumerate(updates):
            masked = {}
            for layer, grads in update.gradient_updates.items():
                masked[layer] = np.array(grads) + masks[i][layer]
                # Subtract masks from other participants (simulated)
                for j in range(num_participants):
                    if j != i:
                        masked[layer] -= masks[j][layer] / (num_participants - 1)
            masked_updates.append(
                ModelUpdate(
                    update_id=update.update_id,
                    participant_id=update.participant_id,
                    federation_id=update.federation_id,
                    round_id=update.round_id,
                    gradient_updates={k: v.tolist() for k, v in masked.items()},
                    num_samples=update.num_samples,
                    local_loss=update.local_loss,
                    local_metrics=update.local_metrics,
                )
            )

        # Aggregate (masks should cancel out)
        return self._fed_avg(masked_updates)


# ============================================================================
# Local Training Simulator
# ============================================================================


class LocalTrainer:
    """Simulates local model training at a participant site."""

    def __init__(
        self,
        model_type: ModelType,
        learning_rate: float = 0.01,
        batch_size: int = 32,
        local_epochs: int = 5,
    ):
        """Initialize local trainer.

        Args:
            model_type: Type of model being trained.
            learning_rate: Learning rate for local optimization.
            batch_size: Batch size for local training.
            local_epochs: Number of local epochs per round.
        """
        self.model_type = model_type
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.local_epochs = local_epochs

        # Initialize mock model weights
        self._init_model_weights()

    def _init_model_weights(self) -> None:
        """Initialize model weights based on model type."""
        if self.model_type == ModelType.READMISSION_PREDICTION:
            self.weights = {
                "layer1": np.random.randn(8, 16).tolist(),
                "layer2": np.random.randn(16, 8).tolist(),
                "output": np.random.randn(8, 1).tolist(),
            }
            self.feature_names = [
                "age",
                "length_of_stay",
                "comorbidity_count",
                "prior_admissions",
                "ed_visits_6mo",
                "medication_count",
                "hemoglobin",
                "creatinine",
            ]
        elif self.model_type == ModelType.MORTALITY_RISK:
            self.weights = {
                "layer1": np.random.randn(8, 16).tolist(),
                "layer2": np.random.randn(16, 8).tolist(),
                "output": np.random.randn(8, 1).tolist(),
            }
            self.feature_names = [
                "age",
                "charlson_score",
                "apache_score",
                "icu_los",
                "mechanical_vent",
                "vasopressors",
                "creatinine",
                "lactate",
            ]
        else:
            self.weights = {
                "layer1": np.random.randn(8, 16).tolist(),
                "layer2": np.random.randn(16, 8).tolist(),
                "output": np.random.randn(8, 1).tolist(),
            }
            self.feature_names = [
                "age",
                "bmi",
                "systolic_bp",
                "diastolic_bp",
                "fasting_glucose",
                "hba1c",
                "total_cholesterol",
                "smoking_status",
            ]

    def train_local(
        self,
        data: pd.DataFrame,
        global_weights: dict[str, list[float]] | None = None,
    ) -> tuple[dict[str, list[float]], float, dict[str, float]]:
        """Perform local training on participant data.

        Args:
            data: Local training data.
            global_weights: Current global model weights.

        Returns:
            Tuple of (gradient_updates, loss, metrics).
        """
        # Update local weights from global if provided
        if global_weights:
            self.weights = global_weights.copy()

        num_samples = len(data)
        num_batches = max(1, num_samples // self.batch_size)

        # Simulate training loop
        total_loss = 0.0
        for epoch in range(self.local_epochs):
            epoch_loss = 0.0
            for batch_idx in range(num_batches):
                # Simulate forward/backward pass
                batch_loss = np.random.exponential(0.5) * np.exp(-epoch * 0.1)
                epoch_loss += batch_loss

                # Simulate gradient computation
                for layer in self.weights:
                    weights_array = np.array(self.weights[layer])
                    gradient = np.random.randn(*weights_array.shape) * 0.01
                    weights_array -= self.learning_rate * gradient
                    self.weights[layer] = weights_array.tolist()

            total_loss += epoch_loss / num_batches

        avg_loss = total_loss / self.local_epochs

        # Compute gradient updates (difference from global)
        gradient_updates = {}
        if global_weights:
            for layer in self.weights:
                local_w = np.array(self.weights[layer])
                global_w = np.array(global_weights[layer])
                gradient_updates[layer] = (local_w - global_w).tolist()
        else:
            gradient_updates = self.weights.copy()

        # Compute local metrics
        metrics = {
            "accuracy": 0.65 + np.random.random() * 0.2,
            "auc": 0.70 + np.random.random() * 0.15,
            "precision": 0.60 + np.random.random() * 0.2,
            "recall": 0.55 + np.random.random() * 0.25,
        }

        return gradient_updates, avg_loss, metrics


# ============================================================================
# Federated Learning Service
# ============================================================================


class FederatedLearningService:
    """Main service for federated learning operations."""

    def __init__(self):
        """Initialize the federated learning service."""
        self._federations: dict[str, Federation] = {}
        self._participants: dict[str, dict[str, Participant]] = {}
        self._global_models: dict[str, GlobalModel] = {}
        self._training_rounds: dict[str, dict[str, TrainingRound]] = {}
        self._model_updates: dict[str, list[ModelUpdate]] = {}
        self._distributions: dict[str, list[Distribution]] = {}

        # Initialize demo data
        self._load_demo_federations()

    def _load_demo_federations(self) -> None:
        """Load demonstration federations for testing."""
        # Create demo federation
        demo_config = FederationConfig(
            name="Multi-Hospital Readmission Study",
            description="Collaborative study to predict 30-day readmission risk across multiple healthcare systems",
            model_type=ModelType.READMISSION_PREDICTION,
            aggregation_protocol=AggregationProtocol.FED_AVG,
            privacy_mechanism=PrivacyMechanism.GRADIENT_CLIPPING,
            min_participants=3,
            rounds_total=10,
            local_epochs=5,
            learning_rate=0.01,
            privacy_budget_epsilon=1.0,
            gradient_clip_norm=1.0,
            feature_names=[
                "age",
                "length_of_stay",
                "comorbidity_count",
                "prior_admissions",
                "ed_visits_6mo",
                "medication_count",
                "hemoglobin",
                "creatinine",
            ],
        )

        federation = self.create_federation(demo_config)

        # Add demo participants
        demo_orgs = MockDataGenerator.generate_mock_organizations(5)
        for i, org in enumerate(demo_orgs):
            org.data_size = np.random.randint(5000, 20000)
            participant = self.register_participant(federation.federation_id, org)
            if i == 0:
                # First org is coordinator
                participant.role = FederationRole.COORDINATOR
                federation.coordinator_id = org.org_id

        # Initialize global model
        self.initialize_global_model(
            federation.federation_id,
            {
                "architecture": "feedforward_nn",
                "layers": [8, 16, 8, 1],
                "activation": "relu",
            },
        )

        # Simulate some training rounds
        federation.status = FederationStatus.ACTIVE
        federation.current_round = 3
        federation.total_samples = sum(p.total_samples for p in self._participants.get(federation.federation_id, {}).values())

        # Create training history
        for round_num in range(1, 4):
            round_id = f"round-{round_num}-{federation.federation_id[:8]}"
            training_round = TrainingRound(
                round_id=round_id,
                federation_id=federation.federation_id,
                round_number=round_num,
                status=RoundStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                participating_orgs=[p.org.org_id for p in self._participants.get(federation.federation_id, {}).values()],
                updates_received=5,
                updates_expected=5,
                global_loss=0.5 - round_num * 0.05 + np.random.random() * 0.05,
                global_metrics={
                    "auc": 0.72 + round_num * 0.02 + np.random.random() * 0.02,
                    "accuracy": 0.70 + round_num * 0.015 + np.random.random() * 0.02,
                },
            )
            if federation.federation_id not in self._training_rounds:
                self._training_rounds[federation.federation_id] = {}
            self._training_rounds[federation.federation_id][round_id] = training_round

        # Update global model with simulated performance
        if federation.federation_id in self._global_models:
            self._global_models[federation.federation_id].version = 3
            self._global_models[federation.federation_id].performance_metrics = {
                "auc": 0.78,
                "accuracy": 0.74,
                "precision": 0.71,
                "recall": 0.68,
                "f1": 0.695,
            }

        self._federations[federation.federation_id] = federation
        logger.info(f"Loaded demo federation: {federation.name}")

    def create_federation(self, config: FederationConfig) -> Federation:
        """Create a new federation of participating organizations.

        Args:
            config: Federation configuration.

        Returns:
            Created Federation object.
        """
        federation_id = f"fed-{str(uuid4())[:12]}"

        federation = Federation(
            federation_id=federation_id,
            name=config.name,
            description=config.description,
            config=config,
            status=FederationStatus.INITIALIZING,
        )

        self._federations[federation_id] = federation
        self._participants[federation_id] = {}
        self._training_rounds[federation_id] = {}
        self._model_updates[federation_id] = []
        self._distributions[federation_id] = []

        logger.info(f"Created federation: {config.name} ({federation_id})")
        return federation

    def register_participant(
        self, federation_id: str, org: Organization
    ) -> Participant:
        """Register organization as federation participant.

        Args:
            federation_id: Federation to join.
            org: Organization details.

        Returns:
            Participant object.

        Raises:
            KeyError: If federation not found.
            ValueError: If federation is full or org doesn't meet requirements.
        """
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")

        federation = self._federations[federation_id]

        # Check if federation is accepting participants
        if federation.status not in [
            FederationStatus.INITIALIZING,
            FederationStatus.ACTIVE,
        ]:
            raise ValueError(f"Federation is not accepting new participants (status: {federation.status})")

        # Check participant limits
        current_count = len(self._participants.get(federation_id, {}))
        if current_count >= federation.config.max_participants:
            raise ValueError("Federation has reached maximum participants")

        # Check minimum samples
        if org.data_size < federation.config.min_samples_per_participant:
            raise ValueError(
                f"Organization has insufficient data ({org.data_size} < {federation.config.min_samples_per_participant})"
            )

        participant_id = f"part-{str(uuid4())[:8]}"

        # Determine role
        role = FederationRole.PARTICIPANT
        if current_count == 0:
            role = FederationRole.COORDINATOR
            federation.coordinator_id = org.org_id

        participant = Participant(
            participant_id=participant_id,
            federation_id=federation_id,
            org=org,
            role=role,
            total_samples=org.data_size,
            is_verified=True,
        )

        self._participants[federation_id][participant_id] = participant

        # Update federation total samples
        federation.total_samples += org.data_size
        federation.updated_at = datetime.now(timezone.utc)

        # Check if we have enough participants to start
        if len(self._participants[federation_id]) >= federation.config.min_participants:
            if federation.status == FederationStatus.INITIALIZING:
                federation.status = FederationStatus.ACTIVE

        logger.info(
            f"Registered participant {org.name} ({participant_id}) to federation {federation_id}"
        )
        return participant

    def initialize_global_model(
        self, federation_id: str, model_config: dict
    ) -> GlobalModel:
        """Initialize global model for federation.

        Args:
            federation_id: Federation ID.
            model_config: Model architecture configuration.

        Returns:
            Initialized GlobalModel.

        Raises:
            KeyError: If federation not found.
        """
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")

        federation = self._federations[federation_id]
        model_id = f"model-{str(uuid4())[:8]}"

        # Initialize trainer to get initial weights
        trainer = LocalTrainer(
            model_type=federation.config.model_type,
            learning_rate=federation.config.learning_rate,
            batch_size=federation.config.batch_size,
            local_epochs=federation.config.local_epochs,
        )

        global_model = GlobalModel(
            model_id=model_id,
            federation_id=federation_id,
            version=0,
            model_type=federation.config.model_type,
            architecture=model_config,
            weights=trainer.weights,
            feature_names=trainer.feature_names,
            training_samples=0,
            performance_metrics={},
        )

        self._global_models[federation_id] = global_model

        logger.info(f"Initialized global model for federation {federation_id}")
        return global_model

    def start_training_round(self, federation_id: str) -> TrainingRound:
        """Start a new training round.

        Args:
            federation_id: Federation ID.

        Returns:
            Created TrainingRound.

        Raises:
            KeyError: If federation not found.
            ValueError: If conditions not met for training.
        """
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")

        federation = self._federations[federation_id]

        # Check if federation can train
        if federation.status not in [FederationStatus.ACTIVE, FederationStatus.TRAINING]:
            raise ValueError(f"Federation cannot start training (status: {federation.status})")

        participants = self._participants.get(federation_id, {})
        if len(participants) < federation.config.min_participants:
            raise ValueError(f"Insufficient participants ({len(participants)} < {federation.config.min_participants})")

        # Check if there's an active round
        active_rounds = [
            r for r in self._training_rounds.get(federation_id, {}).values()
            if r.status in [RoundStatus.WAITING, RoundStatus.IN_PROGRESS, RoundStatus.AGGREGATING]
        ]
        if active_rounds:
            raise ValueError("There is already an active training round")

        # Create new round
        round_number = federation.current_round + 1
        round_id = f"round-{round_number}-{str(uuid4())[:8]}"

        training_round = TrainingRound(
            round_id=round_id,
            federation_id=federation_id,
            round_number=round_number,
            status=RoundStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
            participating_orgs=[p.org.org_id for p in participants.values()],
            updates_expected=len(participants),
        )

        self._training_rounds[federation_id][round_id] = training_round
        self._model_updates[round_id] = []

        # Update federation status
        federation.status = FederationStatus.TRAINING
        federation.updated_at = datetime.now(timezone.utc)

        logger.info(f"Started training round {round_number} for federation {federation_id}")
        return training_round

    def compute_local_update(
        self, participant_id: str, federation_id: str, round_id: str
    ) -> ModelUpdate:
        """Compute local model update (simulates running at participant site).

        Args:
            participant_id: Participant ID.
            federation_id: Federation ID.
            round_id: Training round ID.

        Returns:
            ModelUpdate with gradient updates.

        Raises:
            KeyError: If participant, federation, or round not found.
        """
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")
        if federation_id not in self._participants or participant_id not in self._participants[federation_id]:
            raise KeyError(f"Participant {participant_id} not found in federation")
        if round_id not in self._training_rounds.get(federation_id, {}):
            raise KeyError(f"Training round {round_id} not found")

        federation = self._federations[federation_id]
        participant = self._participants[federation_id][participant_id]
        global_model = self._global_models.get(federation_id)

        # Generate mock local data
        local_data = MockDataGenerator.generate_patient_features(
            num_samples=participant.total_samples,
            org_id=participant.org.org_id,
            model_type=federation.config.model_type,
        )

        # Create local trainer
        trainer = LocalTrainer(
            model_type=federation.config.model_type,
            learning_rate=federation.config.learning_rate,
            batch_size=federation.config.batch_size,
            local_epochs=federation.config.local_epochs,
        )

        # Perform local training
        gradient_updates, local_loss, local_metrics = trainer.train_local(
            data=local_data,
            global_weights=global_model.weights if global_model else None,
        )

        # Apply privacy mechanisms
        privacy_engine = PrivacyEngine(
            mechanism=federation.config.privacy_mechanism,
            epsilon=federation.config.privacy_budget_epsilon,
            delta=federation.config.privacy_budget_delta,
            clip_norm=federation.config.gradient_clip_norm,
        )

        # Clip gradients
        clipped = privacy_engine.clip_gradients(
            {k: np.array(v) for k, v in gradient_updates.items()}
        )

        # Add noise if using DP
        noisy = privacy_engine.add_noise(clipped, len(local_data))
        noise_added = federation.config.privacy_mechanism in [
            PrivacyMechanism.LOCAL_DP,
            PrivacyMechanism.CENTRAL_DP,
        ]

        # Create update
        update_id = f"update-{str(uuid4())[:8]}"
        checksum = hashlib.sha256(
            str(gradient_updates).encode()
        ).hexdigest()[:16]

        model_update = ModelUpdate(
            update_id=update_id,
            participant_id=participant_id,
            federation_id=federation_id,
            round_id=round_id,
            gradient_updates={k: v.tolist() for k, v in noisy.items()},
            num_samples=len(local_data),
            local_loss=local_loss,
            local_metrics=local_metrics,
            noise_added=noise_added,
            checksum=checksum,
        )

        # Update participant stats
        participant.last_update_at = datetime.now(timezone.utc)
        participant.rounds_participated += 1

        logger.info(
            f"Computed local update for participant {participant_id} in round {round_id}"
        )
        return model_update

    def upload_local_update(
        self, federation_id: str, round_id: str, update: ModelUpdate
    ) -> bool:
        """Upload local update from participant.

        Args:
            federation_id: Federation ID.
            round_id: Training round ID.
            update: Model update to upload.

        Returns:
            True if upload successful.

        Raises:
            KeyError: If federation or round not found.
        """
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")
        if round_id not in self._training_rounds.get(federation_id, {}):
            raise KeyError(f"Training round {round_id} not found")

        training_round = self._training_rounds[federation_id][round_id]

        if training_round.status != RoundStatus.IN_PROGRESS:
            raise ValueError(f"Round is not accepting updates (status: {training_round.status})")

        # Store update
        if round_id not in self._model_updates:
            self._model_updates[round_id] = []
        self._model_updates[round_id].append(update)

        # Update round stats
        training_round.updates_received += 1

        logger.info(
            f"Uploaded update from participant {update.participant_id} "
            f"({training_round.updates_received}/{training_round.updates_expected})"
        )
        return True

    def aggregate_updates(self, federation_id: str, round_id: str) -> GlobalModel:
        """Aggregate local model updates using configured protocol.

        Args:
            federation_id: Federation ID.
            round_id: Training round ID.

        Returns:
            Updated GlobalModel.

        Raises:
            KeyError: If federation or round not found.
            ValueError: If not enough updates received.
        """
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")
        if round_id not in self._training_rounds.get(federation_id, {}):
            raise KeyError(f"Training round {round_id} not found")

        federation = self._federations[federation_id]
        training_round = self._training_rounds[federation_id][round_id]
        global_model = self._global_models.get(federation_id)

        updates = self._model_updates.get(round_id, [])
        if not updates:
            raise ValueError("No updates received for aggregation")

        # Update round status
        training_round.status = RoundStatus.AGGREGATING

        # Create aggregation engine
        aggregation_engine = AggregationEngine(
            protocol=federation.config.aggregation_protocol,
            proximal_mu=federation.config.proximal_mu,
        )

        # Perform aggregation
        aggregated_weights = aggregation_engine.aggregate(
            updates=updates,
            global_weights=global_model.weights if global_model else None,
        )

        # Update global model
        if global_model:
            # Convert aggregated weights to lists for storage
            new_weights = {}
            for layer, weights in aggregated_weights.items():
                if isinstance(weights, np.ndarray):
                    new_weights[layer] = weights.tolist()
                else:
                    new_weights[layer] = weights

            # Apply aggregated gradients to global model
            for layer in global_model.weights:
                if layer in new_weights:
                    global_w = np.array(global_model.weights[layer])
                    update_w = np.array(new_weights[layer])
                    global_model.weights[layer] = (
                        global_w + federation.config.learning_rate * update_w
                    ).tolist()

            global_model.version += 1
            global_model.updated_at = datetime.now(timezone.utc)
            global_model.training_samples = sum(u.num_samples for u in updates)

            # Update performance metrics (simulated improvement)
            base_auc = global_model.performance_metrics.get("auc", 0.7)
            base_acc = global_model.performance_metrics.get("accuracy", 0.65)
            global_model.performance_metrics = {
                "auc": min(0.95, base_auc + np.random.random() * 0.02),
                "accuracy": min(0.92, base_acc + np.random.random() * 0.015),
                "precision": 0.7 + np.random.random() * 0.15,
                "recall": 0.65 + np.random.random() * 0.2,
                "f1": 0.68 + np.random.random() * 0.15,
            }

        # Compute round metrics
        total_samples = sum(u.num_samples for u in updates)
        weighted_loss = sum(u.local_loss * u.num_samples for u in updates) / max(total_samples, 1)

        training_round.global_loss = weighted_loss
        training_round.global_metrics = {
            "auc": np.mean([u.local_metrics.get("auc", 0.7) for u in updates]),
            "accuracy": np.mean([u.local_metrics.get("accuracy", 0.65) for u in updates]),
        }
        training_round.status = RoundStatus.COMPLETED
        training_round.completed_at = datetime.now(timezone.utc)

        # Update federation
        federation.current_round = training_round.round_number
        federation.status = FederationStatus.ACTIVE
        federation.updated_at = datetime.now(timezone.utc)

        # Track privacy budget
        privacy_engine = PrivacyEngine(
            mechanism=federation.config.privacy_mechanism,
            epsilon=federation.config.privacy_budget_epsilon,
            delta=federation.config.privacy_budget_delta,
        )
        training_round.privacy_budget_used = privacy_engine.compute_privacy_spent(1)
        federation.privacy_budget_spent += training_round.privacy_budget_used

        logger.info(
            f"Aggregated {len(updates)} updates for round {round_id}, "
            f"global model version: {global_model.version if global_model else 'N/A'}"
        )

        return global_model

    def distribute_global_model(self, federation_id: str) -> list[Distribution]:
        """Send global model to all participants.

        Args:
            federation_id: Federation ID.

        Returns:
            List of Distribution records.

        Raises:
            KeyError: If federation not found.
        """
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")

        global_model = self._global_models.get(federation_id)
        if not global_model:
            raise ValueError("No global model initialized")

        participants = self._participants.get(federation_id, {})
        distributions = []

        for participant_id, participant in participants.items():
            distribution = Distribution(
                distribution_id=f"dist-{str(uuid4())[:8]}",
                federation_id=federation_id,
                participant_id=participant_id,
                model_version=global_model.version,
                acknowledged=True,  # Simulated acknowledgment
                acknowledged_at=datetime.now(timezone.utc),
            )
            distributions.append(distribution)
            self._distributions[federation_id].append(distribution)

        logger.info(
            f"Distributed global model v{global_model.version} to {len(distributions)} participants"
        )
        return distributions

    def apply_secure_aggregation(
        self, updates: list[ModelUpdate]
    ) -> AggregatedUpdate:
        """Apply secure aggregation protocol.

        Args:
            updates: List of model updates.

        Returns:
            AggregatedUpdate with securely aggregated weights.
        """
        if not updates:
            raise ValueError("No updates provided for aggregation")

        aggregation_engine = AggregationEngine(
            protocol=AggregationProtocol.SECURE_AGG
        )

        aggregated_weights = aggregation_engine.aggregate(updates)

        return AggregatedUpdate(
            aggregation_id=f"agg-{str(uuid4())[:8]}",
            federation_id=updates[0].federation_id,
            round_id=updates[0].round_id,
            aggregated_weights={k: v.tolist() for k, v in aggregated_weights.items()},
            participating_count=len(updates),
            total_samples=sum(u.num_samples for u in updates),
            weighted_loss=sum(u.local_loss * u.num_samples for u in updates) / sum(u.num_samples for u in updates),
            aggregation_method=AggregationProtocol.SECURE_AGG,
        )

    def run_full_round(self, federation_id: str) -> TrainingRound:
        """Run a complete training round (for simulation).

        This method orchestrates:
        1. Start round
        2. Compute local updates for all participants
        3. Aggregate updates
        4. Distribute new global model

        Args:
            federation_id: Federation ID.

        Returns:
            Completed TrainingRound.
        """
        # Start round
        training_round = self.start_training_round(federation_id)

        # Compute and upload updates for each participant
        participants = self._participants.get(federation_id, {})
        for participant_id in participants:
            update = self.compute_local_update(
                participant_id=participant_id,
                federation_id=federation_id,
                round_id=training_round.round_id,
            )
            self.upload_local_update(federation_id, training_round.round_id, update)

        # Aggregate
        self.aggregate_updates(federation_id, training_round.round_id)

        # Distribute new model
        self.distribute_global_model(federation_id)

        return self._training_rounds[federation_id][training_round.round_id]

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_federation(self, federation_id: str) -> Federation | None:
        """Get federation by ID."""
        return self._federations.get(federation_id)

    def list_federations(self) -> list[Federation]:
        """List all federations."""
        return list(self._federations.values())

    def get_participants(self, federation_id: str) -> list[Participant]:
        """Get all participants in a federation."""
        return list(self._participants.get(federation_id, {}).values())

    def get_global_model(self, federation_id: str) -> GlobalModel | None:
        """Get current global model for a federation."""
        return self._global_models.get(federation_id)

    def get_training_round(
        self, federation_id: str, round_id: str
    ) -> TrainingRound | None:
        """Get a specific training round."""
        return self._training_rounds.get(federation_id, {}).get(round_id)

    def get_training_rounds(self, federation_id: str) -> list[TrainingRound]:
        """Get all training rounds for a federation."""
        return list(self._training_rounds.get(federation_id, {}).values())

    def get_training_metrics(self, federation_id: str) -> FederatedMetrics:
        """Get comprehensive training metrics for a federation."""
        if federation_id not in self._federations:
            raise KeyError(f"Federation {federation_id} not found")

        federation = self._federations[federation_id]
        rounds = sorted(
            self._training_rounds.get(federation_id, {}).values(),
            key=lambda r: r.round_number,
        )

        loss_history = [r.global_loss for r in rounds if r.global_loss is not None]
        auc_history = [r.global_metrics.get("auc", 0) for r in rounds if r.global_metrics]
        accuracy_history = [r.global_metrics.get("accuracy", 0) for r in rounds if r.global_metrics]

        # Compute convergence rate (change in loss)
        convergence_rate = None
        if len(loss_history) >= 2:
            convergence_rate = (loss_history[-1] - loss_history[0]) / len(loss_history)

        # Estimate remaining rounds
        estimated_remaining = None
        if convergence_rate and convergence_rate < 0 and loss_history[-1] > 0.1:
            # Estimate rounds to reach loss of 0.1
            estimated_remaining = int((loss_history[-1] - 0.1) / abs(convergence_rate))
            estimated_remaining = min(estimated_remaining, federation.config.rounds_total - federation.current_round)

        return FederatedMetrics(
            federation_id=federation_id,
            current_round=federation.current_round,
            total_rounds=federation.config.rounds_total,
            global_loss_history=loss_history,
            global_auc_history=auc_history,
            global_accuracy_history=accuracy_history,
            participants_per_round=[r.updates_received for r in rounds],
            samples_per_round=[sum(p.total_samples for p in self._participants.get(federation_id, {}).values())] * len(rounds),
            privacy_budget_spent=federation.privacy_budget_spent,
            convergence_rate=convergence_rate,
            estimated_rounds_remaining=estimated_remaining,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_federations": len(self._federations),
            "active_federations": len([f for f in self._federations.values() if f.status in [FederationStatus.ACTIVE, FederationStatus.TRAINING]]),
            "total_participants": sum(len(p) for p in self._participants.values()),
            "total_training_rounds": sum(len(r) for r in self._training_rounds.values()),
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_federated_learning_service: FederatedLearningService | None = None
_federated_lock = threading.Lock()


def get_federated_learning_service() -> FederatedLearningService:
    """Get the singleton federated learning service instance."""
    global _federated_learning_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _federated_learning_service is None:
        with _federated_lock:
            if _federated_learning_service is None:
                _federated_learning_service = FederatedLearningService()
    return _federated_learning_service
