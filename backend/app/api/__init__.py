"""API routers for Clinical Ontology Normalizer."""

from app.api.agent import router as agent_router
from app.api.ai_audit import router as ai_audit_router
from app.api.ai_coding import router as ai_coding_router
from app.api.assistant import router as assistant_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.auth_sessions import router as auth_sessions_router
from app.api.batch import router as batch_router
from app.api.calculators import router as calculators_router
from app.api.calculators import clinical_router as clinical_calculators_router
from app.api.cdisc import router as cdisc_router
from app.api.cds_hooks import router as cds_hooks_router
from app.api.coding import router as coding_router
from app.api.cohorts import router as cohorts_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router
from app.api.etl import router as etl_router
from app.api.graph import router as graph_router
from app.api.graph import reasoning_router as graph_reasoning_router
from app.api.graph_rag import router as graph_rag_router
from app.api.health import router as health_router
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
    create_field_error,
    create_not_found_error,
    create_validation_error,
    create_validation_errors_from_pydantic,
    get_field_suggestion,
)
from app.api.export import router as export_router
from app.api.federated import router as federated_router
from app.api.fhir import router as fhir_router
from app.api.jobs import router as jobs_router
from app.api.job_queue import router as job_queue_router
from app.api.llm import router as llm_router
from app.api.llm_finetuning import router as llm_finetuning_router
from app.api.metrics import router as metrics_router
from app.api.nlp import router as nlp_router
from app.api.notifications import router as notifications_router
from app.api.middleware import (
    AuditMiddleware,
    AsyncAuditMiddleware,
    CurrentUser,
    ErrorHandlerMiddleware,
    MetricsMiddleware,
    MetricsTimer,
    PermissionChecker,
    RateLimitConfig,
    RateLimitMiddleware,
    RequestIdMiddleware,
    RoleChecker,
    get_current_active_user,
    get_current_user,
    get_current_user_optional,
    get_rate_limiter_store,
    get_request_id,
    rate_limit,
    require_admin,
    require_any_permission,
    require_any_role,
    require_documents_read,
    require_documents_write,
    require_patients_read,
    require_permission,
    require_role,
    track_time,
)
from app.api.patients import router as patients_router
from app.api.search import router as search_router
from app.api.semantic_search import router as semantic_search_router
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
from app.api.risk import router as risk_router
from app.api.notes import router as notes_router
from app.api.predictions import router as predictions_router
from app.api.quality import router as quality_router
from app.api.quality_measures import router as quality_measures_router
from app.api.terminology import router as terminology_router
from app.api.timeline import router as timeline_router
from app.api.valuesets import router as valuesets_router
from app.api.visualizations import router as visualizations_router
from app.api.streaming import router as streaming_router
from app.api.synthetic import router as synthetic_router
from app.api.tefca import router as tefca_router
from app.api.knowledge_graph_fhir import router as knowledge_graph_fhir_router
from app.api.kg_benchmark import router as kg_benchmark_router
from app.api.kg_health import router as kg_health_router
from app.api.kg_orchestration import router as kg_orchestration_router
from app.api.drug_safety import router as drug_safety_router
from app.api.differential_diagnosis import router as differential_diagnosis_router
from app.api.icd10_suggestions import router as icd10_suggestions_router
from app.api.cpt_suggestions import router as cpt_suggestions_router
from app.api.hcc_analysis import router as hcc_analysis_router
from app.api.voice import router as voice_router
from app.api.coding_assistant import router as coding_assistant_router
from app.api.lab_reference import router as lab_reference_router
from app.api.alert_rules import router as alert_rules_router
from app.api.risk_thresholds import router as risk_thresholds_router
from app.api.prediction_audit import router as prediction_audit_router
from app.api.pipeline_scheduling import router as pipeline_scheduling_router
from app.api.data_completeness import router as data_completeness_router
from app.api.data_consistency import router as data_consistency_router
from app.api.model_registry import router as model_registry_router
from app.api.clinical_agent import router as clinical_agent_router
from app.api.policy import router as policy_router
from app.api.vocabulary import router as vocabulary_router

__all__ = [
    # Routers
    "agent_router",
    "ai_audit_router",
    "ai_coding_router",
    "assistant_router",
    "audit_router",
    "auth_router",
    "auth_sessions_router",
    "batch_router",
    "calculators_router",
    "clinical_calculators_router",
    "cdisc_router",
    "cds_hooks_router",
    "coding_router",
    "cohorts_router",
    "dashboard_router",
    "documents_router",
    "etl_router",
    "graph_router",
    "graph_reasoning_router",
    "graph_rag_router",
    "export_router",
    "federated_router",
    "fhir_router",
    "health_router",
    "jobs_router",
    "job_queue_router",
    "llm_router",
    "llm_finetuning_router",
    "metrics_router",
    "nlp_router",
    "notifications_router",
    "notes_router",
    "patients_router",
    "predictions_router",
    "quality_router",
    "quality_measures_router",
    "reconciliation_router",
    "risk_router",
    "search_router",
    "semantic_search_router",
    "smart_router",
    "sse_router",
    "terminology_router",
    "timeline_router",
    "users_router",
    "valuesets_router",
    "visualizations_router",
    "vocabulary_mapping_router",
    "websocket_router",
    "streaming_router",
    "synthetic_router",
    "tefca_router",
    "knowledge_graph_fhir_router",
    "kg_benchmark_router",
    "kg_health_router",
    "kg_orchestration_router",
    "drug_safety_router",
    "differential_diagnosis_router",
    "icd10_suggestions_router",
    "cpt_suggestions_router",
    "hcc_analysis_router",
    "voice_router",
    "coding_assistant_router",
    "lab_reference_router",
    "alert_rules_router",
    "risk_thresholds_router",
    "prediction_audit_router",
    "pipeline_scheduling_router",
    "data_completeness_router",
    "data_consistency_router",
    "model_registry_router",
    "clinical_agent_router",
    "policy_router",
    "vocabulary_router",
    # Middleware
    "AuditMiddleware",
    "AsyncAuditMiddleware",
    "ErrorHandlerMiddleware",
    "MetricsMiddleware",
    "MetricsTimer",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "RequestIdMiddleware",
    "get_rate_limiter_store",
    "get_request_id",
    "rate_limit",
    "track_time",
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
    "create_field_error",
    "create_not_found_error",
    "create_validation_error",
    "create_validation_errors_from_pydantic",
    "get_field_suggestion",
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
