"""Federated Learning API Endpoints.

Provides endpoints for federated learning operations:
- POST /api/v1/federated/federations - Create federation
- GET /api/v1/federated/federations - List federations
- GET /api/v1/federated/federations/{id} - Get federation details
- POST /api/v1/federated/federations/{id}/join - Join federation
- POST /api/v1/federated/federations/{id}/rounds - Start training round
- GET /api/v1/federated/federations/{id}/rounds - List training rounds
- GET /api/v1/federated/federations/{id}/rounds/{round_id} - Get round status
- POST /api/v1/federated/federations/{id}/upload - Upload local update
- GET /api/v1/federated/federations/{id}/model - Get current global model
- GET /api/v1/federated/federations/{id}/metrics - Get training metrics
- POST /api/v1/federated/federations/{id}/simulate - Simulate training round
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError, NotFoundError, ValidationError

router = APIRouter(prefix="/federated", tags=["Federated Learning"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateFederationRequest(BaseModel):
    """Request to create a new federation."""

    name: str = Field(..., min_length=3, max_length=100, description="Federation name")
    description: str | None = Field(None, max_length=500)
    model_type: str = Field(
        default="readmission_prediction",
        description="Model type: readmission_prediction, mortality_risk, phenotyping, etc.",
    )
    aggregation_protocol: str = Field(
        default="fed_avg", description="Aggregation protocol: fed_avg, fed_prox, secure_aggregation"
    )
    privacy_mechanism: str = Field(
        default="gradient_clipping",
        description="Privacy: none, local_dp, central_dp, gradient_clipping",
    )
    min_participants: int = Field(default=3, ge=2, le=50)
    max_participants: int = Field(default=100, ge=2, le=1000)
    min_samples_per_participant: int = Field(default=100, ge=10)
    rounds_total: int = Field(default=10, ge=1, le=100)
    local_epochs: int = Field(default=5, ge=1, le=50)
    learning_rate: float = Field(default=0.01, gt=0, le=1.0)
    batch_size: int = Field(default=32, ge=1, le=512)
    privacy_budget_epsilon: float = Field(default=1.0, gt=0)
    privacy_budget_delta: float = Field(default=1e-5, gt=0, le=1.0)
    gradient_clip_norm: float = Field(default=1.0, gt=0)
    proximal_mu: float = Field(default=0.01, ge=0)
    feature_names: list[str] = Field(default_factory=list)


class JoinFederationRequest(BaseModel):
    """Request to join a federation."""

    org_id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    type: str = Field(default="hospital")
    location: str | None = Field(None)
    data_size: int = Field(..., ge=0, description="Estimated number of samples")
    contact_email: str | None = Field(None)


class UploadUpdateRequest(BaseModel):
    """Request to upload a local model update."""

    participant_id: str = Field(..., description="Participant ID")
    round_id: str = Field(..., description="Training round ID")
    gradient_updates: dict[str, list[float]] = Field(
        default_factory=dict, description="Gradient updates"
    )
    num_samples: int = Field(..., ge=1, description="Number of samples used")
    local_loss: float = Field(..., ge=0, description="Local training loss")
    local_metrics: dict[str, float] = Field(
        default_factory=dict, description="Local evaluation metrics"
    )


class FederationResponse(BaseModel):
    """Response with federation details."""

    federation_id: str
    name: str
    description: str | None
    status: str
    model_type: str
    aggregation_protocol: str
    privacy_mechanism: str
    min_participants: int
    max_participants: int
    current_participants: int
    current_round: int
    total_rounds: int
    total_samples: int
    privacy_budget_epsilon: float
    privacy_budget_spent: float
    created_at: datetime
    updated_at: datetime
    coordinator_id: str | None


class FederationListResponse(BaseModel):
    """Response with list of federations."""

    total: int
    federations: list[FederationResponse]


class ParticipantResponse(BaseModel):
    """Response with participant details."""

    participant_id: str
    federation_id: str
    org_id: str
    org_name: str
    org_type: str
    location: str | None
    role: str
    status: str
    joined_at: datetime
    last_update_at: datetime | None
    rounds_participated: int
    total_samples: int
    contribution_score: float


class ParticipantListResponse(BaseModel):
    """Response with list of participants."""

    federation_id: str
    total: int
    participants: list[ParticipantResponse]


class TrainingRoundResponse(BaseModel):
    """Response with training round details."""

    round_id: str
    federation_id: str
    round_number: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    participating_orgs: list[str]
    updates_received: int
    updates_expected: int
    global_loss: float | None
    global_metrics: dict[str, float]
    privacy_budget_used: float


class TrainingRoundListResponse(BaseModel):
    """Response with list of training rounds."""

    federation_id: str
    total: int
    rounds: list[TrainingRoundResponse]


class GlobalModelResponse(BaseModel):
    """Response with global model details."""

    model_id: str
    federation_id: str
    version: int
    model_type: str
    architecture: dict[str, Any]
    feature_names: list[str]
    training_samples: int
    performance_metrics: dict[str, float]
    created_at: datetime
    updated_at: datetime


class TrainingMetricsResponse(BaseModel):
    """Response with training metrics."""

    federation_id: str
    current_round: int
    total_rounds: int
    global_loss_history: list[float]
    global_auc_history: list[float]
    global_accuracy_history: list[float]
    participants_per_round: list[int]
    samples_per_round: list[int]
    privacy_budget_spent: float
    privacy_budget_total: float
    convergence_rate: float | None
    estimated_rounds_remaining: int | None


class SimulateRoundResponse(BaseModel):
    """Response from simulating a training round."""

    federation_id: str
    round_id: str
    round_number: int
    status: str
    participating_count: int
    total_samples: int
    global_loss: float | None
    global_metrics: dict[str, float]
    model_version: int
    processing_time_ms: float


# ============================================================================
# Create Federation
# ============================================================================


@router.post(
    "/federations",
    response_model=FederationResponse,
    summary="Create a new federation",
    description="Create a new federated learning federation for cross-organization model training.",
)
async def create_federation(request: CreateFederationRequest) -> FederationResponse:
    """Create a new federation.

    Args:
        request: Federation configuration.

    Returns:
        Created federation details.
    """
    try:
        from app.services.federated_learning_service import (
            AggregationProtocol,
            FederationConfig,
            ModelType,
            PrivacyMechanism,
            get_federated_learning_service,
        )

        service = get_federated_learning_service()

        # Map string enums to proper types
        model_type_map = {
            "readmission_prediction": ModelType.READMISSION_PREDICTION,
            "mortality_risk": ModelType.MORTALITY_RISK,
            "length_of_stay": ModelType.LENGTH_OF_STAY,
            "phenotyping": ModelType.PHENOTYPING,
            "treatment_response": ModelType.TREATMENT_RESPONSE,
        }
        model_type = model_type_map.get(request.model_type, ModelType.READMISSION_PREDICTION)

        aggregation_map = {
            "fed_avg": AggregationProtocol.FED_AVG,
            "fed_prox": AggregationProtocol.FED_PROX,
            "secure_aggregation": AggregationProtocol.SECURE_AGG,
        }
        aggregation = aggregation_map.get(request.aggregation_protocol, AggregationProtocol.FED_AVG)

        privacy_map = {
            "none": PrivacyMechanism.NONE,
            "local_dp": PrivacyMechanism.LOCAL_DP,
            "central_dp": PrivacyMechanism.CENTRAL_DP,
            "gradient_clipping": PrivacyMechanism.GRADIENT_CLIPPING,
        }
        privacy = privacy_map.get(request.privacy_mechanism, PrivacyMechanism.GRADIENT_CLIPPING)

        config = FederationConfig(
            name=request.name,
            description=request.description,
            model_type=model_type,
            aggregation_protocol=aggregation,
            privacy_mechanism=privacy,
            min_participants=request.min_participants,
            max_participants=request.max_participants,
            min_samples_per_participant=request.min_samples_per_participant,
            rounds_total=request.rounds_total,
            local_epochs=request.local_epochs,
            learning_rate=request.learning_rate,
            batch_size=request.batch_size,
            privacy_budget_epsilon=request.privacy_budget_epsilon,
            privacy_budget_delta=request.privacy_budget_delta,
            gradient_clip_norm=request.gradient_clip_norm,
            proximal_mu=request.proximal_mu,
            feature_names=request.feature_names,
        )

        federation = service.create_federation(config)

        # Initialize global model
        service.initialize_global_model(
            federation.federation_id,
            {"architecture": "feedforward_nn", "layers": [8, 16, 8, 1]},
        )

        participants = service.get_participants(federation.federation_id)

        return FederationResponse(
            federation_id=federation.federation_id,
            name=federation.name,
            description=federation.description,
            status=federation.status.value,
            model_type=federation.config.model_type.value,
            aggregation_protocol=federation.config.aggregation_protocol.value,
            privacy_mechanism=federation.config.privacy_mechanism.value,
            min_participants=federation.config.min_participants,
            max_participants=federation.config.max_participants,
            current_participants=len(participants),
            current_round=federation.current_round,
            total_rounds=federation.config.rounds_total,
            total_samples=federation.total_samples,
            privacy_budget_epsilon=federation.config.privacy_budget_epsilon,
            privacy_budget_spent=federation.privacy_budget_spent,
            created_at=federation.created_at,
            updated_at=federation.updated_at,
            coordinator_id=federation.coordinator_id,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to create federation: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# List Federations
# ============================================================================


@router.get(
    "/federations",
    response_model=FederationListResponse,
    summary="List all federations",
    description="Get a list of all federated learning federations.",
)
async def list_federations(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> FederationListResponse:
    """List all federations.

    Args:
        status: Optional status filter.
        limit: Maximum number to return.
        offset: Pagination offset.

    Returns:
        List of federations.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()
        federations = service.list_federations()

        # Filter by status if provided
        if status:
            federations = [f for f in federations if f.status.value == status]

        # Apply pagination
        total = len(federations)
        federations = federations[offset : offset + limit]

        responses = []
        for fed in federations:
            participants = service.get_participants(fed.federation_id)
            responses.append(
                FederationResponse(
                    federation_id=fed.federation_id,
                    name=fed.name,
                    description=fed.description,
                    status=fed.status.value,
                    model_type=fed.config.model_type.value,
                    aggregation_protocol=fed.config.aggregation_protocol.value,
                    privacy_mechanism=fed.config.privacy_mechanism.value,
                    min_participants=fed.config.min_participants,
                    max_participants=fed.config.max_participants,
                    current_participants=len(participants),
                    current_round=fed.current_round,
                    total_rounds=fed.config.rounds_total,
                    total_samples=fed.total_samples,
                    privacy_budget_epsilon=fed.config.privacy_budget_epsilon,
                    privacy_budget_spent=fed.privacy_budget_spent,
                    created_at=fed.created_at,
                    updated_at=fed.updated_at,
                    coordinator_id=fed.coordinator_id,
                )
            )

        return FederationListResponse(total=total, federations=responses)

    except Exception as e:
        raise InternalError(
            message=f"Failed to list federations: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Get Federation
# ============================================================================


@router.get(
    "/federations/{federation_id}",
    response_model=FederationResponse,
    summary="Get federation details",
    description="Get details of a specific federation.",
)
async def get_federation(federation_id: str) -> FederationResponse:
    """Get federation by ID.

    Args:
        federation_id: Federation identifier.

    Returns:
        Federation details.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()
        federation = service.get_federation(federation_id)

        if not federation:
            raise NotFoundError(
                message=f"Federation {federation_id} not found",
                error_code=ErrorCode.NOT_FOUND,
            )

        participants = service.get_participants(federation_id)

        return FederationResponse(
            federation_id=federation.federation_id,
            name=federation.name,
            description=federation.description,
            status=federation.status.value,
            model_type=federation.config.model_type.value,
            aggregation_protocol=federation.config.aggregation_protocol.value,
            privacy_mechanism=federation.config.privacy_mechanism.value,
            min_participants=federation.config.min_participants,
            max_participants=federation.config.max_participants,
            current_participants=len(participants),
            current_round=federation.current_round,
            total_rounds=federation.config.rounds_total,
            total_samples=federation.total_samples,
            privacy_budget_epsilon=federation.config.privacy_budget_epsilon,
            privacy_budget_spent=federation.privacy_budget_spent,
            created_at=federation.created_at,
            updated_at=federation.updated_at,
            coordinator_id=federation.coordinator_id,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to get federation: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Join Federation
# ============================================================================


@router.post(
    "/federations/{federation_id}/join",
    response_model=ParticipantResponse,
    summary="Join a federation",
    description="Register an organization as a participant in a federation.",
)
async def join_federation(
    federation_id: str, request: JoinFederationRequest
) -> ParticipantResponse:
    """Join a federation.

    Args:
        federation_id: Federation to join.
        request: Organization details.

    Returns:
        Participant registration details.
    """
    try:
        from app.services.federated_learning_service import (
            Organization,
            get_federated_learning_service,
        )

        service = get_federated_learning_service()

        org = Organization(
            org_id=request.org_id,
            name=request.name,
            type=request.type,
            location=request.location,
            data_size=request.data_size,
            contact_email=request.contact_email,
        )

        participant = service.register_participant(federation_id, org)

        return ParticipantResponse(
            participant_id=participant.participant_id,
            federation_id=participant.federation_id,
            org_id=participant.org.org_id,
            org_name=participant.org.name,
            org_type=participant.org.type,
            location=participant.org.location,
            role=participant.role.value,
            status=participant.status,
            joined_at=participant.joined_at,
            last_update_at=participant.last_update_at,
            rounds_participated=participant.rounds_participated,
            total_samples=participant.total_samples,
            contribution_score=participant.contribution_score,
        )

    except KeyError as e:
        raise NotFoundError(
            message=str(e),
            error_code=ErrorCode.NOT_FOUND,
        )
    except ValueError as e:
        raise ValidationError(
            message=str(e),
            error_code=ErrorCode.VALIDATION_ERROR,
        )
    except Exception as e:
        raise InternalError(
            message=f"Failed to join federation: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Get Participants
# ============================================================================


@router.get(
    "/federations/{federation_id}/participants",
    response_model=ParticipantListResponse,
    summary="List federation participants",
    description="Get all participants in a federation.",
)
async def get_participants(federation_id: str) -> ParticipantListResponse:
    """Get all participants in a federation.

    Args:
        federation_id: Federation identifier.

    Returns:
        List of participants.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()

        if not service.get_federation(federation_id):
            raise NotFoundError(
                message=f"Federation {federation_id} not found",
                error_code=ErrorCode.NOT_FOUND,
            )

        participants = service.get_participants(federation_id)

        responses = [
            ParticipantResponse(
                participant_id=p.participant_id,
                federation_id=p.federation_id,
                org_id=p.org.org_id,
                org_name=p.org.name,
                org_type=p.org.type,
                location=p.org.location,
                role=p.role.value,
                status=p.status,
                joined_at=p.joined_at,
                last_update_at=p.last_update_at,
                rounds_participated=p.rounds_participated,
                total_samples=p.total_samples,
                contribution_score=p.contribution_score,
            )
            for p in participants
        ]

        return ParticipantListResponse(
            federation_id=federation_id,
            total=len(responses),
            participants=responses,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to get participants: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Start Training Round
# ============================================================================


@router.post(
    "/federations/{federation_id}/rounds",
    response_model=TrainingRoundResponse,
    summary="Start a training round",
    description="Start a new federated training round.",
)
async def start_training_round(federation_id: str) -> TrainingRoundResponse:
    """Start a new training round.

    Args:
        federation_id: Federation identifier.

    Returns:
        Training round details.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()
        training_round = service.start_training_round(federation_id)

        return TrainingRoundResponse(
            round_id=training_round.round_id,
            federation_id=training_round.federation_id,
            round_number=training_round.round_number,
            status=training_round.status.value,
            started_at=training_round.started_at,
            completed_at=training_round.completed_at,
            participating_orgs=training_round.participating_orgs,
            updates_received=training_round.updates_received,
            updates_expected=training_round.updates_expected,
            global_loss=training_round.global_loss,
            global_metrics=training_round.global_metrics,
            privacy_budget_used=training_round.privacy_budget_used,
        )

    except KeyError as e:
        raise NotFoundError(
            message=str(e),
            error_code=ErrorCode.NOT_FOUND,
        )
    except ValueError as e:
        raise ValidationError(
            message=str(e),
            error_code=ErrorCode.VALIDATION_ERROR,
        )
    except Exception as e:
        raise InternalError(
            message=f"Failed to start training round: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Get Training Rounds
# ============================================================================


@router.get(
    "/federations/{federation_id}/rounds",
    response_model=TrainingRoundListResponse,
    summary="List training rounds",
    description="Get all training rounds for a federation.",
)
async def get_training_rounds(federation_id: str) -> TrainingRoundListResponse:
    """Get all training rounds for a federation.

    Args:
        federation_id: Federation identifier.

    Returns:
        List of training rounds.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()

        if not service.get_federation(federation_id):
            raise NotFoundError(
                message=f"Federation {federation_id} not found",
                error_code=ErrorCode.NOT_FOUND,
            )

        rounds = service.get_training_rounds(federation_id)

        responses = [
            TrainingRoundResponse(
                round_id=r.round_id,
                federation_id=r.federation_id,
                round_number=r.round_number,
                status=r.status.value,
                started_at=r.started_at,
                completed_at=r.completed_at,
                participating_orgs=r.participating_orgs,
                updates_received=r.updates_received,
                updates_expected=r.updates_expected,
                global_loss=r.global_loss,
                global_metrics=r.global_metrics,
                privacy_budget_used=r.privacy_budget_used,
            )
            for r in sorted(rounds, key=lambda x: x.round_number)
        ]

        return TrainingRoundListResponse(
            federation_id=federation_id,
            total=len(responses),
            rounds=responses,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to get training rounds: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Get Training Round Status
# ============================================================================


@router.get(
    "/federations/{federation_id}/rounds/{round_id}",
    response_model=TrainingRoundResponse,
    summary="Get training round status",
    description="Get the status of a specific training round.",
)
async def get_training_round(federation_id: str, round_id: str) -> TrainingRoundResponse:
    """Get training round by ID.

    Args:
        federation_id: Federation identifier.
        round_id: Training round identifier.

    Returns:
        Training round details.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()
        training_round = service.get_training_round(federation_id, round_id)

        if not training_round:
            raise NotFoundError(
                message=f"Training round {round_id} not found",
                error_code=ErrorCode.NOT_FOUND,
            )

        return TrainingRoundResponse(
            round_id=training_round.round_id,
            federation_id=training_round.federation_id,
            round_number=training_round.round_number,
            status=training_round.status.value,
            started_at=training_round.started_at,
            completed_at=training_round.completed_at,
            participating_orgs=training_round.participating_orgs,
            updates_received=training_round.updates_received,
            updates_expected=training_round.updates_expected,
            global_loss=training_round.global_loss,
            global_metrics=training_round.global_metrics,
            privacy_budget_used=training_round.privacy_budget_used,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to get training round: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Upload Local Update
# ============================================================================


@router.post(
    "/federations/{federation_id}/upload",
    summary="Upload local model update",
    description="Upload a local model update from a participant.",
)
async def upload_local_update(
    federation_id: str, request: UploadUpdateRequest
) -> dict[str, Any]:
    """Upload local model update.

    Args:
        federation_id: Federation identifier.
        request: Model update data.

    Returns:
        Upload confirmation.
    """
    try:
        from app.services.federated_learning_service import (
            ModelUpdate,
            get_federated_learning_service,
        )

        service = get_federated_learning_service()

        update = ModelUpdate(
            update_id=f"update-{str(uuid4())[:8]}",
            participant_id=request.participant_id,
            federation_id=federation_id,
            round_id=request.round_id,
            gradient_updates=request.gradient_updates,
            num_samples=request.num_samples,
            local_loss=request.local_loss,
            local_metrics=request.local_metrics,
        )

        success = service.upload_local_update(federation_id, request.round_id, update)

        return {
            "success": success,
            "update_id": update.update_id,
            "message": "Update uploaded successfully",
        }

    except KeyError as e:
        raise NotFoundError(
            message=str(e),
            error_code=ErrorCode.NOT_FOUND,
        )
    except ValueError as e:
        raise ValidationError(
            message=str(e),
            error_code=ErrorCode.VALIDATION_ERROR,
        )
    except Exception as e:
        raise InternalError(
            message=f"Failed to upload update: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Get Global Model
# ============================================================================


@router.get(
    "/federations/{federation_id}/model",
    response_model=GlobalModelResponse,
    summary="Get current global model",
    description="Get the current global model for a federation.",
)
async def get_global_model(federation_id: str) -> GlobalModelResponse:
    """Get current global model.

    Args:
        federation_id: Federation identifier.

    Returns:
        Global model details.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()
        global_model = service.get_global_model(federation_id)

        if not global_model:
            raise NotFoundError(
                message=f"No global model found for federation {federation_id}",
                error_code=ErrorCode.NOT_FOUND,
            )

        return GlobalModelResponse(
            model_id=global_model.model_id,
            federation_id=global_model.federation_id,
            version=global_model.version,
            model_type=global_model.model_type.value,
            architecture=global_model.architecture,
            feature_names=global_model.feature_names,
            training_samples=global_model.training_samples,
            performance_metrics=global_model.performance_metrics,
            created_at=global_model.created_at,
            updated_at=global_model.updated_at,
        )

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to get global model: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Get Training Metrics
# ============================================================================


@router.get(
    "/federations/{federation_id}/metrics",
    response_model=TrainingMetricsResponse,
    summary="Get training metrics",
    description="Get comprehensive training metrics for a federation.",
)
async def get_training_metrics(federation_id: str) -> TrainingMetricsResponse:
    """Get training metrics.

    Args:
        federation_id: Federation identifier.

    Returns:
        Training metrics.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()
        federation = service.get_federation(federation_id)

        if not federation:
            raise NotFoundError(
                message=f"Federation {federation_id} not found",
                error_code=ErrorCode.NOT_FOUND,
            )

        metrics = service.get_training_metrics(federation_id)

        return TrainingMetricsResponse(
            federation_id=metrics.federation_id,
            current_round=metrics.current_round,
            total_rounds=metrics.total_rounds,
            global_loss_history=metrics.global_loss_history,
            global_auc_history=metrics.global_auc_history,
            global_accuracy_history=metrics.global_accuracy_history,
            participants_per_round=metrics.participants_per_round,
            samples_per_round=metrics.samples_per_round,
            privacy_budget_spent=metrics.privacy_budget_spent,
            privacy_budget_total=federation.config.privacy_budget_epsilon,
            convergence_rate=metrics.convergence_rate,
            estimated_rounds_remaining=metrics.estimated_rounds_remaining,
        )

    except NotFoundError:
        raise
    except KeyError as e:
        raise NotFoundError(
            message=str(e),
            error_code=ErrorCode.NOT_FOUND,
        )
    except Exception as e:
        raise InternalError(
            message=f"Failed to get training metrics: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Simulate Training Round
# ============================================================================


@router.post(
    "/federations/{federation_id}/simulate",
    response_model=SimulateRoundResponse,
    summary="Simulate a training round",
    description="Simulate a complete federated training round (for demonstration).",
)
async def simulate_training_round(federation_id: str) -> SimulateRoundResponse:
    """Simulate a complete training round.

    This endpoint orchestrates a full training round including:
    - Starting the round
    - Computing local updates for all participants
    - Aggregating updates
    - Distributing the new global model

    Args:
        federation_id: Federation identifier.

    Returns:
        Training round results.
    """
    start_time = time.perf_counter()

    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()

        # Run full round
        training_round = service.run_full_round(federation_id)
        global_model = service.get_global_model(federation_id)

        processing_time = (time.perf_counter() - start_time) * 1000

        return SimulateRoundResponse(
            federation_id=federation_id,
            round_id=training_round.round_id,
            round_number=training_round.round_number,
            status=training_round.status.value,
            participating_count=training_round.updates_received,
            total_samples=sum(
                p.total_samples for p in service.get_participants(federation_id)
            ),
            global_loss=training_round.global_loss,
            global_metrics=training_round.global_metrics,
            model_version=global_model.version if global_model else 0,
            processing_time_ms=round(processing_time, 2),
        )

    except KeyError as e:
        raise NotFoundError(
            message=str(e),
            error_code=ErrorCode.NOT_FOUND,
        )
    except ValueError as e:
        raise ValidationError(
            message=str(e),
            error_code=ErrorCode.VALIDATION_ERROR,
        )
    except Exception as e:
        raise InternalError(
            message=f"Failed to simulate training round: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )


# ============================================================================
# Download Model
# ============================================================================


@router.get(
    "/federations/{federation_id}/model/download",
    summary="Download global model weights",
    description="Download the current global model weights for deployment.",
)
async def download_model(federation_id: str) -> dict[str, Any]:
    """Download global model weights.

    Args:
        federation_id: Federation identifier.

    Returns:
        Model weights and metadata for download.
    """
    try:
        from app.services.federated_learning_service import get_federated_learning_service

        service = get_federated_learning_service()
        global_model = service.get_global_model(federation_id)

        if not global_model:
            raise NotFoundError(
                message=f"No global model found for federation {federation_id}",
                error_code=ErrorCode.NOT_FOUND,
            )

        return {
            "model_id": global_model.model_id,
            "federation_id": global_model.federation_id,
            "version": global_model.version,
            "model_type": global_model.model_type.value,
            "architecture": global_model.architecture,
            "feature_names": global_model.feature_names,
            "weights": global_model.weights,
            "performance_metrics": global_model.performance_metrics,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "json",
            "framework_compatible": ["sklearn", "pytorch", "tensorflow"],
        }

    except NotFoundError:
        raise
    except Exception as e:
        raise InternalError(
            message=f"Failed to download model: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVICE_ERROR,
        )
