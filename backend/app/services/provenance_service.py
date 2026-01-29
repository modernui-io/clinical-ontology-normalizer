"""
Provenance Tracking Service for Clinical Knowledge Graph.

Tracks the origin, derivation, and confidence of all facts and inferences:
- Source document tracking (which clinical notes)
- Extraction method (NLP, rule-based, LLM)
- Confidence scores with calibration
- Audit trails for regulatory compliance
- Reasoning chain provenance for multi-hop inferences

Based on:
- W3C PROV-O ontology for provenance
- HL7 FHIR Provenance resource patterns
- Clinical decision support audit requirements
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExtractionMethod(str, Enum):
    """Methods used to extract clinical facts."""

    MANUAL = "manual"  # Human-entered
    NLP_RULE = "nlp_rule"  # Rule-based NLP extraction
    NLP_ML = "nlp_ml"  # ML-based NLP (NER, classification)
    NLP_LLM = "nlp_llm"  # LLM extraction (GPT, Claude, etc.)
    FHIR_IMPORT = "fhir_import"  # Imported from FHIR resource
    HL7_IMPORT = "hl7_import"  # Imported from HL7 message
    ONTOLOGY = "ontology"  # Derived from ontology (IS-A relations)
    INFERENCE = "inference"  # Inferred via reasoning
    AGGREGATION = "aggregation"  # Aggregated from multiple sources


class ConfidenceLevel(str, Enum):
    """Calibrated confidence levels."""

    VERIFIED = "verified"  # Human-verified, >99% accurate
    HIGH = "high"  # High confidence, 90-99% accurate
    MEDIUM = "medium"  # Medium confidence, 70-90% accurate
    LOW = "low"  # Low confidence, 50-70% accurate
    UNCERTAIN = "uncertain"  # Uncertain, <50% accurate


@dataclass
class SourceDocument:
    """Reference to a source document."""

    document_id: str
    document_type: str  # progress_note, discharge_summary, lab_report, etc.
    document_date: datetime | None = None
    section: str | None = None  # Section within document
    text_span: tuple[int, int] | None = None  # Character positions
    author: str | None = None
    institution: str | None = None


@dataclass
class ExtractionInfo:
    """Information about how a fact was extracted."""

    method: ExtractionMethod
    model_name: str | None = None  # e.g., "en_core_sci_lg", "gpt-4"
    model_version: str | None = None
    extraction_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_confidence: float = 1.0  # Model's raw confidence score
    calibrated_confidence: float = 1.0  # Calibrated confidence
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH


@dataclass
class ProvenanceRecord:
    """Complete provenance record for a clinical fact or inference."""

    provenance_id: str = field(default_factory=lambda: str(uuid4()))
    fact_id: str = ""  # ID of the fact/inference this tracks
    fact_type: str = ""  # condition, drug, measurement, inference, etc.

    # Source tracking
    source_documents: list[SourceDocument] = field(default_factory=list)
    primary_source: SourceDocument | None = None

    # Extraction info
    extraction: ExtractionInfo | None = None

    # For derived/inferred facts
    derived_from: list[str] = field(default_factory=list)  # IDs of source facts
    reasoning_chain: list[str] = field(default_factory=list)  # Steps in reasoning

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    verified_at: datetime | None = None
    verified_by: str | None = None

    # Audit
    version: int = 1
    previous_version_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "provenance_id": self.provenance_id,
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "source_documents": [
                {
                    "document_id": doc.document_id,
                    "document_type": doc.document_type,
                    "document_date": doc.document_date.isoformat() if doc.document_date else None,
                    "section": doc.section,
                    "author": doc.author,
                }
                for doc in self.source_documents
            ],
            "extraction_method": self.extraction.method.value if self.extraction else None,
            "confidence": self.extraction.calibrated_confidence if self.extraction else 1.0,
            "confidence_level": self.extraction.confidence_level.value if self.extraction else "high",
            "derived_from": self.derived_from,
            "reasoning_chain": self.reasoning_chain,
            "created_at": self.created_at.isoformat(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verified_by": self.verified_by,
            "version": self.version,
        }


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""

    step_number: int
    description: str
    source_facts: list[str]  # Fact IDs used
    relation_used: str | None = None  # e.g., "IS_A", "TREATS", "CAUSES"
    confidence: float = 1.0
    evidence_type: str = "direct"  # direct, inferred, assumed


@dataclass
class ReasoningProvenance:
    """Provenance for a multi-hop reasoning chain."""

    reasoning_id: str = field(default_factory=lambda: str(uuid4()))
    query: str = ""  # Original question
    conclusion: str = ""  # Final answer/inference

    steps: list[ReasoningStep] = field(default_factory=list)

    # Overall confidence (product of step confidences with decay)
    aggregate_confidence: float = 1.0

    # Path metrics
    total_hops: int = 0
    semantic_coherence: float = 1.0  # Measure of semantic consistency

    # Evidence summary
    supporting_facts: list[str] = field(default_factory=list)
    contradicting_facts: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ProvenanceService:
    """Service for tracking and querying provenance information.

    Features:
    - Create provenance records for extracted facts
    - Track reasoning chains for inferred facts
    - Query provenance for audit trails
    - Calculate aggregate confidence with calibration
    """

    # Confidence calibration based on extraction method
    METHOD_CALIBRATION = {
        ExtractionMethod.MANUAL: 1.0,
        ExtractionMethod.FHIR_IMPORT: 0.95,
        ExtractionMethod.HL7_IMPORT: 0.95,
        ExtractionMethod.NLP_RULE: 0.85,
        ExtractionMethod.NLP_ML: 0.80,
        ExtractionMethod.NLP_LLM: 0.75,
        ExtractionMethod.ONTOLOGY: 0.99,
        ExtractionMethod.INFERENCE: 0.70,
        ExtractionMethod.AGGREGATION: 0.85,
    }

    # Confidence decay per hop in reasoning chains
    HOP_DECAY = 0.9

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self._driver = None

        # In-memory cache for recent provenance (for fast lookup)
        self._provenance_cache: dict[str, ProvenanceRecord] = {}
        self._reasoning_cache: dict[str, ReasoningProvenance] = {}

    def create_provenance(
        self,
        fact_id: str,
        fact_type: str,
        source_document: SourceDocument | None = None,
        extraction_method: ExtractionMethod = ExtractionMethod.NLP_ML,
        raw_confidence: float = 1.0,
        model_name: str | None = None,
    ) -> ProvenanceRecord:
        """Create a provenance record for an extracted fact.

        Args:
            fact_id: ID of the fact being tracked
            fact_type: Type of fact (condition, drug, etc.)
            source_document: Source document reference
            extraction_method: How the fact was extracted
            raw_confidence: Model's confidence score
            model_name: Name of extraction model

        Returns:
            ProvenanceRecord with calibrated confidence
        """
        # Calibrate confidence based on method
        calibration_factor = self.METHOD_CALIBRATION.get(extraction_method, 0.7)
        calibrated = raw_confidence * calibration_factor

        # Determine confidence level
        if calibrated >= 0.95:
            level = ConfidenceLevel.HIGH
        elif calibrated >= 0.75:
            level = ConfidenceLevel.MEDIUM
        elif calibrated >= 0.50:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.UNCERTAIN

        extraction = ExtractionInfo(
            method=extraction_method,
            model_name=model_name,
            raw_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            confidence_level=level,
        )

        record = ProvenanceRecord(
            fact_id=fact_id,
            fact_type=fact_type,
            source_documents=[source_document] if source_document else [],
            primary_source=source_document,
            extraction=extraction,
        )

        # Cache for fast lookup
        self._provenance_cache[fact_id] = record

        return record

    def create_inference_provenance(
        self,
        fact_id: str,
        derived_from: list[str],
        reasoning_steps: list[ReasoningStep],
        conclusion: str,
    ) -> ProvenanceRecord:
        """Create provenance for an inferred fact from reasoning.

        Args:
            fact_id: ID of the inferred fact
            derived_from: IDs of source facts
            reasoning_steps: Steps in the reasoning chain
            conclusion: The inference conclusion

        Returns:
            ProvenanceRecord with aggregate confidence
        """
        # Calculate aggregate confidence with hop decay
        aggregate_confidence = 1.0
        for i, step in enumerate(reasoning_steps):
            hop_factor = self.HOP_DECAY ** i
            aggregate_confidence *= step.confidence * hop_factor

        # Determine level based on aggregate
        if aggregate_confidence >= 0.80:
            level = ConfidenceLevel.HIGH
        elif aggregate_confidence >= 0.60:
            level = ConfidenceLevel.MEDIUM
        elif aggregate_confidence >= 0.40:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.UNCERTAIN

        extraction = ExtractionInfo(
            method=ExtractionMethod.INFERENCE,
            raw_confidence=aggregate_confidence,
            calibrated_confidence=aggregate_confidence,
            confidence_level=level,
        )

        record = ProvenanceRecord(
            fact_id=fact_id,
            fact_type="inference",
            extraction=extraction,
            derived_from=derived_from,
            reasoning_chain=[step.description for step in reasoning_steps],
        )

        self._provenance_cache[fact_id] = record
        return record

    def create_reasoning_provenance(
        self,
        query: str,
        steps: list[ReasoningStep],
        conclusion: str,
        supporting_facts: list[str],
        contradicting_facts: list[str] | None = None,
    ) -> ReasoningProvenance:
        """Create detailed provenance for a reasoning chain.

        Args:
            query: Original question
            steps: Reasoning steps
            conclusion: Final answer
            supporting_facts: Facts supporting the conclusion
            contradicting_facts: Facts contradicting (if any)

        Returns:
            ReasoningProvenance with full chain
        """
        # Calculate aggregate confidence with decay
        aggregate = 1.0
        for i, step in enumerate(steps):
            decay = self.HOP_DECAY ** i
            aggregate *= step.confidence * decay

        # Adjust for contradicting evidence
        if contradicting_facts:
            contradiction_penalty = 0.9 ** len(contradicting_facts)
            aggregate *= contradiction_penalty

        provenance = ReasoningProvenance(
            query=query,
            conclusion=conclusion,
            steps=steps,
            aggregate_confidence=aggregate,
            total_hops=len(steps),
            supporting_facts=supporting_facts,
            contradicting_facts=contradicting_facts or [],
        )

        self._reasoning_cache[provenance.reasoning_id] = provenance
        return provenance

    def get_provenance(self, fact_id: str) -> ProvenanceRecord | None:
        """Get provenance record for a fact.

        Args:
            fact_id: ID of the fact

        Returns:
            ProvenanceRecord or None if not found
        """
        return self._provenance_cache.get(fact_id)

    def get_reasoning_provenance(self, reasoning_id: str) -> ReasoningProvenance | None:
        """Get reasoning provenance by ID.

        Args:
            reasoning_id: ID of the reasoning chain

        Returns:
            ReasoningProvenance or None if not found
        """
        return self._reasoning_cache.get(reasoning_id)

    def get_fact_lineage(self, fact_id: str) -> list[ProvenanceRecord]:
        """Get the full lineage of a fact (all derived-from chain).

        Args:
            fact_id: ID of the fact

        Returns:
            List of provenance records in derivation order
        """
        lineage = []
        visited = set()

        def trace_lineage(fid: str):
            if fid in visited:
                return
            visited.add(fid)

            record = self.get_provenance(fid)
            if record:
                lineage.append(record)
                for source_id in record.derived_from:
                    trace_lineage(source_id)

        trace_lineage(fact_id)
        return lineage

    def verify_fact(
        self,
        fact_id: str,
        verified_by: str,
        notes: str | None = None,
    ) -> ProvenanceRecord | None:
        """Mark a fact as human-verified.

        Args:
            fact_id: ID of the fact to verify
            verified_by: User/system that verified
            notes: Optional verification notes

        Returns:
            Updated ProvenanceRecord or None
        """
        record = self.get_provenance(fact_id)
        if not record:
            return None

        record.verified_at = datetime.now(timezone.utc)
        record.verified_by = verified_by
        record.updated_at = datetime.now(timezone.utc)

        if record.extraction:
            record.extraction.confidence_level = ConfidenceLevel.VERIFIED
            record.extraction.calibrated_confidence = 1.0

        return record

    def generate_audit_trail(
        self,
        fact_ids: list[str],
    ) -> dict[str, Any]:
        """Generate an audit trail for regulatory compliance.

        Args:
            fact_ids: List of fact IDs to audit

        Returns:
            Audit trail with full provenance chain
        """
        trail = {
            "audit_id": str(uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "facts_audited": len(fact_ids),
            "entries": [],
        }

        for fact_id in fact_ids:
            lineage = self.get_fact_lineage(fact_id)
            if lineage:
                trail["entries"].append({
                    "fact_id": fact_id,
                    "lineage_depth": len(lineage),
                    "provenance": [r.to_dict() for r in lineage],
                })

        return trail

    def format_citation(self, record: ProvenanceRecord) -> str:
        """Format a provenance record as a human-readable citation.

        Args:
            record: ProvenanceRecord to format

        Returns:
            Formatted citation string
        """
        parts = []

        if record.primary_source:
            src = record.primary_source
            parts.append(f"Source: {src.document_type}")
            if src.document_date:
                parts.append(f"({src.document_date.strftime('%Y-%m-%d')})")
            if src.section:
                parts.append(f"Section: {src.section}")

        if record.extraction:
            parts.append(f"Method: {record.extraction.method.value}")
            parts.append(f"Confidence: {record.extraction.confidence_level.value}")

        if record.verified_at:
            parts.append(f"Verified: {record.verified_at.strftime('%Y-%m-%d')}")

        return " | ".join(parts) if parts else "No provenance available"


# Singleton instance
_provenance_service: ProvenanceService | None = None
_provenance_lock = threading.Lock()


def get_provenance_service() -> ProvenanceService:
    """Get the singleton provenance service."""
    global _provenance_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _provenance_service is None:
        with _provenance_lock:
            if _provenance_service is None:
                from app.core.config import settings

                _provenance_service = ProvenanceService(
                    neo4j_uri=settings.neo4j_uri,
                    neo4j_user=settings.neo4j_user,
                    neo4j_password=settings.neo4j_password or "",
                )
    return _provenance_service
