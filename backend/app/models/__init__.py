"""SQLAlchemy ORM models for Clinical Ontology Normalizer.

All models inherit from Base which provides:
- id: UUID primary key
- created_at: Timestamp

Models:
- Document, StructuredResource (task 2.3)
- Mention, MentionConceptCandidate (task 2.4)
- ClinicalFact, FactEvidence (task 2.5)
- KGNode, KGEdge (task 2.6)
- Concept, ConceptSynonym (task 2.7)
- ClinicalValue (P3-1 value extraction)
- AuditLog, AuditExport (HIPAA audit trail)
- CustomCalculator, CalculatorResult (custom clinical calculators)
- User, Role, Permission, UserRole, RolePermission, RefreshToken (RBAC)
"""

from __future__ import annotations

from app.core.database import Base
from app.models.audit import (
    AuditAction,
    AuditExport,
    AuditExportFormat,
    AuditExportStatus,
    AuditLog,
    AuditResourceType,
)
from app.models.calculator import (
    CalculatorResult,
    CustomCalculator,
    InputType,
    OutputType,
)
from app.models.clinical_fact import ClinicalFact, FactEvidence
from app.models.clinical_value import ClinicalValue, ValueType
from app.models.document import Document, StructuredResource
from app.models.knowledge_graph import KGEdge, KGNode
from app.models.mention import Mention, MentionConceptCandidate
from app.models.rbac import (
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.smart_app import (
    SMARTApp,
    SMARTAuthorizationCode,
)
from app.models.data_source import (
    AuthMethod,
    DataSource,
    DataSourceType,
    HealthStatus,
    Pipeline,
    PipelineRun,
    PipelineRunStatus,
    PipelineStage,
    PipelineStatus,
    ScheduleType,
)
from app.models.policy import (
    Policy,
    PolicyAlertRule,
    PolicySection,
    PolicyStatus,
)
from app.models.policy_kg import (
    EvidenceGrade,
    PolicyEdgeType,
    PolicyKGEdge,
    PolicyKGNode,
    PolicyNodeType,
    PolicyRule,
    RecommendationStrength,
)
from app.models.provenance import (
    ConfidenceLevelDB,
    ExtractionMethodDB,
    ProvenanceRecord,
    ReasoningStepType,
    ReasoningTrace,
)
from app.models.trial import (
    EnrollmentStatus,
    Trial,
    TrialEnrollment,
    TrialPhase,
    TrialStatus,
)
from app.models.vocabulary import Concept, ConceptRelationship, ConceptStatus, ConceptSynonym

__all__ = [
    "Base",
    "Document",
    "StructuredResource",
    "Mention",
    "MentionConceptCandidate",
    "ClinicalFact",
    "FactEvidence",
    "KGNode",
    "KGEdge",
    "Concept",
    "ConceptSynonym",
    "ConceptRelationship",
    "ConceptStatus",
    "ClinicalValue",
    "ValueType",
    "AuditLog",
    "AuditExport",
    "AuditAction",
    "AuditResourceType",
    "AuditExportStatus",
    "AuditExportFormat",
    "CustomCalculator",
    "CalculatorResult",
    "InputType",
    "OutputType",
    # RBAC Models
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "RefreshToken",
    # SMART on FHIR Models
    "SMARTApp",
    "SMARTAuthorizationCode",
    # Data Pipeline Models
    "DataSource",
    "DataSourceType",
    "HealthStatus",
    "AuthMethod",
    "Pipeline",
    "PipelineStatus",
    "ScheduleType",
    "PipelineRun",
    "PipelineRunStatus",
    "PipelineStage",
    # Policy Models
    "Policy",
    "PolicySection",
    "PolicyAlertRule",
    "PolicyStatus",
    # Policy Knowledge Graph Models
    "PolicyKGNode",
    "PolicyKGEdge",
    "PolicyRule",
    "PolicyNodeType",
    "PolicyEdgeType",
    "EvidenceGrade",
    "RecommendationStrength",
    # Provenance Models
    "ProvenanceRecord",
    "ReasoningTrace",
    "ExtractionMethodDB",
    "ConfidenceLevelDB",
    "ReasoningStepType",
    # Trial Models
    "Trial",
    "TrialEnrollment",
    "TrialPhase",
    "TrialStatus",
    "EnrollmentStatus",
]
