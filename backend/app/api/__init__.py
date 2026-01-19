"""API routers for Clinical Ontology Normalizer."""

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.calculators import router as calculators_router
from app.api.coding import router as coding_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router
from app.api.etl import router as etl_router
from app.api.errors import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    InternalError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
    create_not_found_error,
    create_validation_error,
)
from app.api.export import router as export_router
from app.api.fhir import router as fhir_router
from app.api.jobs import router as jobs_router
from app.api.llm import router as llm_router
from app.api.middleware import (
    AuditMiddleware,
    AsyncAuditMiddleware,
    CurrentUser,
    ErrorHandlerMiddleware,
    PermissionChecker,
    RequestIdMiddleware,
    RoleChecker,
    get_current_active_user,
    get_current_user,
    get_current_user_optional,
    get_request_id,
    require_admin,
    require_any_permission,
    require_any_role,
    require_documents_read,
    require_documents_write,
    require_patients_read,
    require_permission,
    require_role,
)
from app.api.patients import router as patients_router
from app.api.search import router as search_router
from app.api.smart import router as smart_router
from app.api.sse import router as sse_router
from app.api.users import router as users_router
from app.api.validators import (
    BillingCode,
    CPTCode,
    ClinicalText,
    HCPCSCode,
    ICD10CMCode,
    ICD10Code,
    ICD10PCSCode,
    PatientID,
    SNOMEDCode,
    validate_cpt_code,
    validate_date_range,
    validate_icd10_code,
    validate_patient_id,
    validate_snomed_code,
)
from app.api.vocabulary_mapping import router as vocabulary_mapping_router
from app.api.websocket import router as websocket_router
from app.api.reconciliation import router as reconciliation_router
from app.api.notes import router as notes_router
from app.api.quality import router as quality_router
from app.api.terminology import router as terminology_router
from app.api.timeline import router as timeline_router

__all__ = [
    # Routers
    "audit_router",
    "auth_router",
    "calculators_router",
    "coding_router",
    "dashboard_router",
    "documents_router",
    "etl_router",
    "export_router",
    "fhir_router",
    "jobs_router",
    "llm_router",
    "notes_router",
    "patients_router",
    "quality_router",
    "reconciliation_router",
    "search_router",
    "smart_router",
    "sse_router",
    "terminology_router",
    "timeline_router",
    "users_router",
    "vocabulary_mapping_router",
    "websocket_router",
    # Middleware
    "AuditMiddleware",
    "AsyncAuditMiddleware",
    "ErrorHandlerMiddleware",
    "RequestIdMiddleware",
    "get_request_id",
    # Auth Middleware
    "CurrentUser",
    "PermissionChecker",
    "RoleChecker",
    "get_current_active_user",
    "get_current_user",
    "get_current_user_optional",
    "require_admin",
    "require_any_permission",
    "require_any_role",
    "require_documents_read",
    "require_documents_write",
    "require_patients_read",
    "require_permission",
    "require_role",
    # Errors
    "APIError",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "ErrorCode",
    "ErrorDetail",
    "ErrorResponse",
    "InternalError",
    "NotFoundError",
    "RateLimitError",
    "ServiceUnavailableError",
    "ValidationError",
    "create_not_found_error",
    "create_validation_error",
    # Validators
    "BillingCode",
    "CPTCode",
    "ClinicalText",
    "HCPCSCode",
    "ICD10CMCode",
    "ICD10Code",
    "ICD10PCSCode",
    "PatientID",
    "SNOMEDCode",
    "validate_cpt_code",
    "validate_date_range",
    "validate_icd10_code",
    "validate_patient_id",
    "validate_snomed_code",
]
