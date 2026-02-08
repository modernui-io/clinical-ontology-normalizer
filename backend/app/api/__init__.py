"""API routers for Clinical Ontology Normalizer."""

from __future__ import annotations

from app.api.agent import router as agent_router
from app.api.agent_chat import router as agent_chat_router
from app.api.ai_audit import router as ai_audit_router
from app.api.ai_coding import router as ai_coding_router
from app.api.assistant import router as assistant_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.auth_sessions import router as auth_sessions_router
from app.api.batch import router as batch_router
from app.api.calculators import router as calculators_router
from app.api.calculators import clinical_router as clinical_calculators_router
from app.api.calculators import data_driven_router as data_driven_calculators_router
from app.api.cdisc import router as cdisc_router
from app.api.cds_hooks import router as cds_hooks_router
from app.api.coding import router as coding_router
from app.api.cohorts import router as cohorts_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router  # Now imports from documents package
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
from app.api.middleware.security_headers import SecurityHeadersMiddleware
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
from app.api.valuesets import clinical_router as clinical_valuesets_router
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
from app.api.guidelines import router as guidelines_router
from app.api.policy import router as policy_router
from app.api.vocabulary import router as vocabulary_router
from app.api.smart_server import router as smart_server_router
from app.api.data_sources import router as data_sources_router
from app.api.phenotypes import router as phenotypes_router
from app.api.pipeline_version import router as pipeline_version_router
from app.api.pipelines import router as pipelines_router
from app.api.feedback import router as feedback_router
from app.api.lineage import router as lineage_router
from app.api.trials import router as trials_router
from app.api.bulk_screening import router as bulk_screening_router
from app.api.mapping_quality import router as mapping_quality_router
from app.api.model_evaluation import router as model_evaluation_router
from app.api.metriport_api import router as metriport_api_router
from app.api.metriport_webhook import router as metriport_webhook_router
from app.api.incidents import router as incidents_router
from app.api.screening_results import router as screening_results_router
from app.api.sites import router as sites_router
from app.api.backup_status import router as backup_status_router
from app.api.roi_dashboard import router as roi_dashboard_router
from app.api.terminology_governance import router as terminology_governance_router
from app.api.cohort_phenotypes import router as cohort_phenotypes_router
from app.api.consent import router as consent_router
from app.api.data_quality_dqd import router as data_quality_dqd_router
from app.api.screen_failure_analytics import router as screen_failure_analytics_router
from app.api.diversity_analytics import router as diversity_analytics_router
from app.api.criteria_fidelity import router as criteria_fidelity_router
from app.api.etl_validation import router as etl_validation_router
from app.api.fhir_validation import router as fhir_validation_router
from app.api.validation_study import router as validation_study_router
from app.api.experiments import router as experiments_router
from app.api.gold_standard import router as gold_standard_router
from app.api.observability import router as observability_router
from app.api.secret_rotation import router as secret_rotation_router
from app.api.data_governance import router as data_governance_router
from app.api.drift_detection import router as drift_detection_router
from app.api.fairness_audit import router as fairness_audit_router
from app.api.quality_management import router as quality_management_router
from app.api.infrastructure import router as infrastructure_router
from app.api.soc2_compliance import router as soc2_compliance_router
from app.api.scalability_audit import router as scalability_audit_router

__all__ = [
    # Routers
    "agent_router",
    "agent_chat_router",
    "ai_audit_router",
    "ai_coding_router",
    "assistant_router",
    "audit_router",
    "auth_router",
    "auth_sessions_router",
    "batch_router",
    "calculators_router",
    "clinical_calculators_router",
    "data_driven_calculators_router",
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
    "clinical_valuesets_router",
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
    "model_evaluation_router",
    "model_registry_router",
    "clinical_agent_router",
    "guidelines_router",
    "policy_router",
    "vocabulary_router",
    "smart_server_router",
    "data_sources_router",
    "phenotypes_router",
    "pipeline_version_router",
    "pipelines_router",
    "feedback_router",
    "trials_router",
    "bulk_screening_router",
    "mapping_quality_router",
    "metriport_api_router",
    "metriport_webhook_router",
    "lineage_router",
    "incidents_router",
    "screening_results_router",
    "sites_router",
    "backup_status_router",
    "roi_dashboard_router",
    "terminology_governance_router",
    "cohort_phenotypes_router",
    "consent_router",
    "data_quality_dqd_router",
    "screen_failure_analytics_router",
    "diversity_analytics_router",
    "criteria_fidelity_router",
    "etl_validation_router",
    "fhir_validation_router",
    "validation_study_router",
    "experiments_router",
    "gold_standard_router",
    "observability_router",
    "secret_rotation_router",
    "data_governance_router",
    "drift_detection_router",
    "fairness_audit_router",
    "quality_management_router",
    "infrastructure_router",
    "soc2_compliance_router",
    "scalability_audit_router",
    # Middleware
    "AuditMiddleware",
    "AsyncAuditMiddleware",
    "ErrorHandlerMiddleware",
    "MetricsMiddleware",
    "MetricsTimer",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "RequestIdMiddleware",
    "SecurityHeadersMiddleware",
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
