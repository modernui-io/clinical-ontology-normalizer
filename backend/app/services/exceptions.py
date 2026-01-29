"""Service-specific exception classes for Clinical Ontology Normalizer.

This module provides typed exceptions for each service domain that automatically
map to the correct HTTP status codes and error codes. These should be used
instead of generic ValueError, ConnectionError, or Exception catches.

Usage:
    from app.services.exceptions import DataSourceConnectionError, ETLJobError

    try:
        await connector.extract()
    except TimeoutError as e:
        raise DataSourceConnectionError(
            message=f"Connection timeout for {source.name}",
            source_id=source.id,
            cause=e
        )

CTO Stability Initiative - Replaces 613 generic Exception catches
"""

from __future__ import annotations

from typing import Any

from app.api.errors import (
    APIError,
    ConflictError,
    ErrorCode,
    ErrorDetail,
    InternalError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)


# ============================================================================
# Base Service Exception
# ============================================================================


class ServiceError(InternalError):
    """Base class for all service-layer exceptions.

    Provides common functionality for service errors including:
    - Automatic error code mapping
    - Cause chaining (original exception)
    - Contextual metadata
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: list[ErrorDetail] | None = None,
        cause: Exception | None = None,
        **metadata: Any,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            details=details or [],
        )
        self.cause = cause
        self.metadata = metadata

    def __str__(self) -> str:
        base = super().__str__()
        if self.cause:
            return f"{base} (caused by: {type(self.cause).__name__}: {self.cause})"
        return base


# ============================================================================
# Data Source Exceptions
# ============================================================================


class DataSourceError(ServiceError):
    """Base exception for data source operations."""

    def __init__(
        self,
        message: str,
        source_id: str | None = None,
        source_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, source_id=source_id, source_name=source_name, **kwargs)


class DataSourceConnectionError(ServiceUnavailableError):
    """Failed to connect to a data source."""

    def __init__(
        self,
        message: str,
        source_id: str | None = None,
        source_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
        )
        self.source_id = source_id
        self.source_name = source_name
        self.cause = cause


class DataSourceNotFoundError(NotFoundError):
    """Data source not found."""

    def __init__(self, source_id: str) -> None:
        super().__init__(
            message=f"Data source '{source_id}' not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
            details=[ErrorDetail(field="source_id", message="Data source does not exist")],
        )


# ============================================================================
# ETL Exceptions
# ============================================================================


class ETLError(ServiceError):
    """Base exception for ETL operations."""

    def __init__(
        self,
        message: str,
        job_id: str | None = None,
        pipeline_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, job_id=job_id, pipeline_id=pipeline_id, **kwargs)


class ETLJobNotFoundError(NotFoundError):
    """ETL job not found."""

    def __init__(self, job_id: str) -> None:
        super().__init__(
            message=f"ETL job '{job_id}' not found",
            error_code=ErrorCode.NOT_FOUND_JOB,
            details=[ErrorDetail(field="job_id", message="Job does not exist")],
        )


class ETLJobStateError(ConflictError):
    """ETL job is in invalid state for requested operation."""

    def __init__(self, job_id: str, current_state: str, required_state: str) -> None:
        super().__init__(
            message=f"Job '{job_id}' is in '{current_state}' state, required: '{required_state}'",
            error_code=ErrorCode.CONFLICT_JOB_ALREADY_PROCESSING,
            details=[
                ErrorDetail(
                    field="job_id",
                    message=f"Job must be in '{required_state}' state",
                    value=current_state,
                )
            ],
        )


class ETLPipelineError(ServiceError):
    """ETL pipeline execution failed."""

    def __init__(
        self,
        message: str,
        pipeline_id: str | None = None,
        step: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_PROCESSING_ERROR,
            pipeline_id=pipeline_id,
            step=step,
            cause=cause,
        )


# ============================================================================
# Vocabulary/Terminology Exceptions
# ============================================================================


class VocabularyError(ServiceError):
    """Base exception for vocabulary/terminology operations."""

    pass


class VocabularyNotFoundError(NotFoundError):
    """Vocabulary or concept not found."""

    def __init__(self, vocabulary: str, code: str | None = None) -> None:
        msg = f"Vocabulary '{vocabulary}' not found"
        if code:
            msg = f"Code '{code}' not found in vocabulary '{vocabulary}'"
        super().__init__(
            message=msg,
            error_code=ErrorCode.NOT_FOUND_CONCEPT,
            details=[ErrorDetail(field="code", message=msg, value=code)],
        )


class VocabularyMappingError(ServiceError):
    """Failed to map between vocabularies."""

    def __init__(
        self,
        source_vocabulary: str,
        target_vocabulary: str,
        code: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"Failed to map '{code}' from {source_vocabulary} to {target_vocabulary}",
            error_code=ErrorCode.INTERNAL_MAPPING_ERROR,
            source_vocabulary=source_vocabulary,
            target_vocabulary=target_vocabulary,
            code=code,
            cause=cause,
        )


# ============================================================================
# Clinical Calculator Exceptions
# ============================================================================


class ClinicalCalculatorError(ServiceError):
    """Base exception for clinical calculator operations."""

    pass


class CalculatorNotFoundError(NotFoundError):
    """Calculator not found."""

    def __init__(self, calculator_id: str) -> None:
        super().__init__(
            message=f"Calculator '{calculator_id}' not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
        )


class CalculatorInputError(ValidationError):
    """Invalid input for calculator."""

    def __init__(self, calculator_id: str, field: str, message: str, value: Any = None) -> None:
        super().__init__(
            message=f"Invalid input for calculator '{calculator_id}': {message}",
            error_code=ErrorCode.VALIDATION_INVALID_VALUE,
            details=[ErrorDetail(field=field, message=message, value=str(value) if value else None)],
        )


class CalculatorComputationError(ServiceError):
    """Calculator computation failed."""

    def __init__(
        self,
        calculator_id: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"Computation failed for '{calculator_id}': {message}",
            error_code=ErrorCode.INTERNAL_PROCESSING_ERROR,
            calculator_id=calculator_id,
            cause=cause,
        )


# ============================================================================
# AI/ML Service Exceptions
# ============================================================================


class AIServiceError(ServiceError):
    """Base exception for AI/ML service operations."""

    pass


class ModelNotFoundError(NotFoundError):
    """ML model not found."""

    def __init__(self, model_id: str) -> None:
        super().__init__(
            message=f"Model '{model_id}' not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
        )


class ModelInferenceError(ServiceError):
    """Model inference failed."""

    def __init__(
        self,
        model_id: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"Inference failed for model '{model_id}': {message}",
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
            model_id=model_id,
            cause=cause,
        )


class CodingServiceError(ServiceError):
    """Medical coding service error."""

    def __init__(
        self,
        message: str,
        coding_system: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_PROCESSING_ERROR,
            coding_system=coding_system,
            cause=cause,
        )


# ============================================================================
# CDS Hooks Exceptions
# ============================================================================


class CDSHooksError(ServiceError):
    """Base exception for CDS Hooks operations."""

    pass


class CDSServiceNotFoundError(NotFoundError):
    """CDS service not found."""

    def __init__(self, service_id: str) -> None:
        super().__init__(
            message=f"CDS service '{service_id}' not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
        )


class CDSHookExecutionError(ServiceError):
    """CDS hook execution failed."""

    def __init__(
        self,
        hook_id: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"Hook '{hook_id}' execution failed: {message}",
            error_code=ErrorCode.INTERNAL_PROCESSING_ERROR,
            hook_id=hook_id,
            cause=cause,
        )


# ============================================================================
# FHIR Exceptions
# ============================================================================


class FHIRError(ServiceError):
    """Base exception for FHIR operations."""

    pass


class FHIRValidationError(ValidationError):
    """FHIR resource validation failed."""

    def __init__(self, resource_type: str, errors: list[str]) -> None:
        super().__init__(
            message=f"FHIR {resource_type} validation failed",
            error_code=ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="resource", message=err) for err in errors],
        )


class FHIRServerError(ServiceUnavailableError):
    """FHIR server communication error."""

    def __init__(
        self,
        server_url: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"FHIR server error ({server_url}): {message}",
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
        )
        self.server_url = server_url
        self.cause = cause


# ============================================================================
# Knowledge Graph Exceptions
# ============================================================================


class KnowledgeGraphError(ServiceError):
    """Base exception for Knowledge Graph operations."""

    pass


class KGNodeNotFoundError(NotFoundError):
    """Knowledge graph node not found."""

    def __init__(self, node_id: str) -> None:
        super().__init__(
            message=f"KG node '{node_id}' not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
        )


class KGQueryError(ServiceError):
    """Knowledge graph query failed."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"KG query failed: {message}",
            error_code=ErrorCode.INTERNAL_DATABASE_ERROR,
            query=query,
            cause=cause,
        )


# ============================================================================
# NLP Exceptions
# ============================================================================


class NLPError(ServiceError):
    """Base exception for NLP operations."""

    def __init__(
        self,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
            cause=cause,
        )


class NLPModelLoadError(ServiceUnavailableError):
    """NLP model failed to load."""

    def __init__(self, model_name: str, cause: Exception | None = None) -> None:
        super().__init__(
            message=f"Failed to load NLP model '{model_name}'",
            error_code=ErrorCode.SERVICE_NLP_UNAVAILABLE,
        )
        self.model_name = model_name
        self.cause = cause


class NLPProcessingError(ServiceError):
    """NLP processing failed."""

    def __init__(
        self,
        message: str,
        document_id: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_NLP_ERROR,
            document_id=document_id,
            cause=cause,
        )


# ============================================================================
# Cohort/Analytics Exceptions
# ============================================================================


class CohortError(ServiceError):
    """Base exception for cohort operations."""

    pass


class CohortNotFoundError(NotFoundError):
    """Cohort not found."""

    def __init__(self, cohort_id: str) -> None:
        super().__init__(
            message=f"Cohort '{cohort_id}' not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
        )


class CohortQueryError(ServiceError):
    """Cohort query failed."""

    def __init__(
        self,
        message: str,
        cohort_id: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_PROCESSING_ERROR,
            cohort_id=cohort_id,
            cause=cause,
        )


# ============================================================================
# RBAC Exceptions
# ============================================================================


class RBACError(ServiceError):
    """Base exception for RBAC operations."""

    pass


class RoleNotFoundError(NotFoundError):
    """Role not found."""

    def __init__(self, role_name: str) -> None:
        super().__init__(
            message=f"Role '{role_name}' not found",
            error_code=ErrorCode.NOT_FOUND_RESOURCE,
        )


class RoleExistsError(ConflictError):
    """Role already exists."""

    def __init__(self, role_name: str) -> None:
        super().__init__(
            message=f"Role '{role_name}' already exists",
            error_code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
        )


class PermissionDeniedError(APIError):
    """Permission denied for operation."""

    def __init__(self, operation: str, resource: str | None = None) -> None:
        msg = f"Permission denied for operation '{operation}'"
        if resource:
            msg += f" on resource '{resource}'"
        super().__init__(
            message=msg,
            error_code=ErrorCode.FORBIDDEN_INSUFFICIENT_PERMISSIONS,
            status_code=403,
        )
