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
from app.models.vocabulary import Concept, ConceptSynonym

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
]
