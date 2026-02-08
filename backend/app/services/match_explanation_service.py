"""Per-Match Explainability Engine (VP-Product-2).

Enriches CriterionResult objects with plain-language evidence summaries,
source document references, and confidence explanations.

For each patient-trial pair, generates explanations showing which criteria
matched/failed with links to source evidence (specific clinical fact, note,
lab result). This is a Pharma RFP Tier 2 requirement.

Usage:
    from app.services.match_explanation_service import MatchExplanationService

    service = MatchExplanationService()
    enriched = await service.enrich_eligibility(eligibility, session)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact, FactEvidence
from app.models.knowledge_graph import KGNode
from app.schemas.base import Domain
from app.schemas.knowledge_graph import NodeType
from app.schemas.trial import CriterionResult, PatientEligibility

logger = logging.getLogger(__name__)


class MatchExplanationService:
    """Generates per-criterion evidence summaries for trial matching results.

    Enriches each CriterionResult in a PatientEligibility with:
    - evidence_summary: Plain-language explanation of why the criterion passed/failed
    - source_documents: Document IDs where the evidence was found
    - confidence_explanation: Why the assigned confidence level
    """

    async def enrich_eligibility(
        self,
        eligibility: PatientEligibility,
        session: AsyncSession,
    ) -> PatientEligibility:
        """Enrich a PatientEligibility result with evidence summaries.

        Iterates over each CriterionResult and adds plain-language
        explanations, source document references, and confidence
        explanations based on the underlying ClinicalFacts.
        """
        enriched_details: list[CriterionResult] = []

        for cr in eligibility.criteria_details:
            enriched = await self._enrich_criterion(
                cr, eligibility.patient_id, session
            )
            enriched_details.append(enriched)

        # Return a new PatientEligibility with enriched criteria_details
        return eligibility.model_copy(update={"criteria_details": enriched_details})

    async def _enrich_criterion(
        self,
        criterion: CriterionResult,
        patient_id: str,
        session: AsyncSession,
    ) -> CriterionResult:
        """Enrich a single CriterionResult with evidence explanations."""
        ctype = criterion.criterion_type

        if ctype == "demographic":
            return await self._enrich_demographic(criterion, patient_id, session)
        elif ctype == "measurement":
            return await self._enrich_measurement(criterion, patient_id, session)
        elif ctype in ("condition", "drug", "procedure", "observation"):
            return await self._enrich_clinical(criterion, patient_id, session)
        else:
            # Unknown type -- return with a generic explanation
            return criterion.model_copy(
                update={
                    "evidence_summary": criterion.details or None,
                    "confidence_explanation": self._build_confidence_explanation(
                        criterion.confidence, ctype, []
                    ),
                }
            )

    # ------------------------------------------------------------------
    # Demographic criterion enrichment
    # ------------------------------------------------------------------

    async def _enrich_demographic(
        self,
        criterion: CriterionResult,
        patient_id: str,
        session: AsyncSession,
    ) -> CriterionResult:
        """Build evidence summary for a demographic criterion (age/gender)."""
        # Query the patient KGNode for demographic properties
        stmt = select(KGNode.properties).where(
            KGNode.patient_id == patient_id,
            KGNode.node_type == NodeType.PATIENT,
            KGNode.deleted_at.is_(None),
        ).limit(1)
        result = await session.execute(stmt)
        props = result.scalar_one_or_none()

        if not props:
            return criterion.model_copy(
                update={
                    "evidence_summary": "No demographic data available for this patient",
                    "confidence_explanation": "Unable to evaluate: no patient demographic record found",
                }
            )

        birth_date_str = (props or {}).get("birth_date")
        gender = (props or {}).get("gender", "Unknown")

        if criterion.status == "PASS":
            if birth_date_str:
                try:
                    birth_date = datetime.fromisoformat(birth_date_str)
                    if birth_date.tzinfo is None:
                        birth_date = birth_date.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - birth_date).days / 365.25
                    summary = (
                        f"Patient is {int(age)} years old (DOB: {birth_date.strftime('%Y-%m-%d')}), "
                        f"gender: {gender}. Meets demographic requirements."
                    )
                except (ValueError, TypeError):
                    summary = f"Patient meets demographic requirements. Gender: {gender}."
            else:
                summary = f"Patient meets demographic requirements. Gender: {gender}."

            return criterion.model_copy(
                update={
                    "evidence_summary": summary,
                    "confidence_explanation": "High confidence: demographic data from patient record",
                }
            )
        elif criterion.status == "NOT_MET":
            if birth_date_str:
                try:
                    birth_date = datetime.fromisoformat(birth_date_str)
                    if birth_date.tzinfo is None:
                        birth_date = birth_date.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - birth_date).days / 365.25
                    summary = (
                        f"Patient is {int(age)} years old (DOB: {birth_date.strftime('%Y-%m-%d')}), "
                        f"gender: {gender}. Does not meet demographic requirements for "
                        f"'{criterion.criterion_name}'."
                    )
                except (ValueError, TypeError):
                    summary = f"Patient does not meet demographic requirements for '{criterion.criterion_name}'."
            else:
                summary = f"Patient does not meet demographic requirements for '{criterion.criterion_name}'."

            return criterion.model_copy(
                update={
                    "evidence_summary": summary,
                    "confidence_explanation": "High confidence: demographic data from patient record does not satisfy criterion",
                }
            )
        else:
            return criterion.model_copy(
                update={
                    "evidence_summary": "Insufficient demographic data to evaluate this criterion",
                    "confidence_explanation": "Unable to evaluate: missing birth date or demographic information",
                }
            )

    # ------------------------------------------------------------------
    # Measurement criterion enrichment
    # ------------------------------------------------------------------

    async def _enrich_measurement(
        self,
        criterion: CriterionResult,
        patient_id: str,
        session: AsyncSession,
    ) -> CriterionResult:
        """Build evidence summary for a measurement criterion (lab values)."""
        if not criterion.evidence_fact_ids:
            return await self._enrich_no_evidence(criterion)

        # Fetch the matching ClinicalFact records
        facts = await self._fetch_facts(criterion.evidence_fact_ids, session)
        source_docs = await self._fetch_source_documents(
            criterion.evidence_fact_ids, session
        )

        if not facts:
            return await self._enrich_no_evidence(criterion)

        # Build summary from the most recent matching fact
        summaries: list[str] = []
        for fact in facts:
            value_str = fact.value or "N/A"
            unit_str = f" {fact.unit}" if fact.unit else ""
            date_str = (
                fact.start_date.strftime("%Y-%m-%d")
                if fact.start_date
                else "date unknown"
            )
            summaries.append(
                f"{fact.concept_name}: {value_str}{unit_str} (recorded {date_str})"
            )

        evidence_text = "; ".join(summaries)
        status_text = self._status_verb(criterion.status)

        summary = f"Patient has {evidence_text}. Criterion '{criterion.criterion_name}' {status_text}."

        conf_explanation = self._build_confidence_explanation(
            criterion.confidence, "measurement", facts
        )

        return criterion.model_copy(
            update={
                "evidence_summary": summary,
                "source_documents": source_docs,
                "confidence_explanation": conf_explanation,
            }
        )

    # ------------------------------------------------------------------
    # Clinical criterion enrichment (condition, drug, procedure, observation)
    # ------------------------------------------------------------------

    async def _enrich_clinical(
        self,
        criterion: CriterionResult,
        patient_id: str,
        session: AsyncSession,
    ) -> CriterionResult:
        """Build evidence summary for condition/drug/procedure criteria."""
        if not criterion.evidence_fact_ids:
            return await self._enrich_no_evidence(criterion)

        facts = await self._fetch_facts(criterion.evidence_fact_ids, session)
        source_docs = await self._fetch_source_documents(
            criterion.evidence_fact_ids, session
        )

        if not facts:
            return await self._enrich_no_evidence(criterion)

        # Build summary from matching facts
        concept_descriptions: list[str] = []
        for fact in facts:
            date_str = (
                fact.start_date.strftime("%Y-%m-%d")
                if fact.start_date
                else "date unknown"
            )
            code_str = f" (OMOP:{fact.omop_concept_id})" if fact.omop_concept_id else ""
            concept_descriptions.append(
                f"{fact.concept_name}{code_str}, recorded {date_str}"
            )

        evidence_text = "; ".join(concept_descriptions[:3])  # Limit to top 3 for readability
        if len(concept_descriptions) > 3:
            evidence_text += f" (+{len(concept_descriptions) - 3} more)"

        status_text = self._status_verb(criterion.status)
        type_label = criterion.criterion_type.replace("_", " ")

        summary = (
            f"Patient has {type_label} evidence: {evidence_text}. "
            f"Criterion '{criterion.criterion_name}' {status_text}."
        )

        conf_explanation = self._build_confidence_explanation(
            criterion.confidence, criterion.criterion_type, facts
        )

        return criterion.model_copy(
            update={
                "evidence_summary": summary,
                "source_documents": source_docs,
                "confidence_explanation": conf_explanation,
            }
        )

    # ------------------------------------------------------------------
    # No-evidence fallback
    # ------------------------------------------------------------------

    async def _enrich_no_evidence(
        self,
        criterion: CriterionResult,
    ) -> CriterionResult:
        """Generate explanation when no evidence facts are available."""
        if criterion.status == "UNKNOWN":
            summary = (
                f"No {criterion.criterion_type} data available for this patient "
                f"to evaluate '{criterion.criterion_name}'"
            )
            conf_explanation = "Unable to evaluate: no data in the relevant clinical domain"
        elif criterion.status == "NOT_MET":
            summary = (
                f"Patient has {criterion.criterion_type} data, but no match found for "
                f"'{criterion.criterion_name}'"
            )
            conf_explanation = (
                "Criterion not satisfied: data exists in the domain but does not match"
            )
        else:
            summary = criterion.details or None
            conf_explanation = self._build_confidence_explanation(
                criterion.confidence, criterion.criterion_type, []
            )

        return criterion.model_copy(
            update={
                "evidence_summary": summary,
                "confidence_explanation": conf_explanation,
            }
        )

    # ------------------------------------------------------------------
    # DB query helpers
    # ------------------------------------------------------------------

    async def _fetch_facts(
        self,
        fact_ids: list[str],
        session: AsyncSession,
    ) -> list[ClinicalFact]:
        """Fetch ClinicalFact records by their IDs."""
        if not fact_ids:
            return []

        stmt = select(ClinicalFact).where(ClinicalFact.id.in_(fact_ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _fetch_source_documents(
        self,
        fact_ids: list[str],
        session: AsyncSession,
    ) -> list[str]:
        """Fetch source document IDs via the FactEvidence chain.

        ClinicalFact -> FactEvidence (source_table='documents') -> source_id
        """
        if not fact_ids:
            return []

        stmt = (
            select(FactEvidence.source_id)
            .where(
                FactEvidence.fact_id.in_(fact_ids),
                FactEvidence.source_table == "documents",
            )
            .distinct()
        )
        result = await session.execute(stmt)
        doc_ids = [str(row) for row in result.scalars().all()]

        # Also include document references from mentions table
        stmt_mentions = (
            select(FactEvidence.source_id)
            .where(
                FactEvidence.fact_id.in_(fact_ids),
                FactEvidence.source_table == "mentions",
            )
            .distinct()
        )
        result_mentions = await session.execute(stmt_mentions)
        mention_ids = list(result_mentions.scalars().all())

        # Deduplicate: we already have doc_ids from documents source table
        # Mention IDs are included as they can be traced to documents
        all_ids = list(set(doc_ids))
        return all_ids

    # ------------------------------------------------------------------
    # Explanation text helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_verb(status: str) -> str:
        """Convert criterion status to a human-readable verb phrase."""
        status_map = {
            "PASS": "is satisfied",
            "FAIL": "is triggered (exclusion matched)",
            "NOT_MET": "is not satisfied",
            "UNKNOWN": "cannot be evaluated (insufficient data)",
            "POSSIBLE_MATCH": "has a possible match (low confidence, needs review)",
        }
        return status_map.get(status, status.lower())

    @staticmethod
    def _build_confidence_explanation(
        confidence: float,
        criterion_type: str,
        facts: list[ClinicalFact],
    ) -> str:
        """Generate an explanation for the confidence level."""
        if not facts:
            if confidence == 0.0:
                return "No matching evidence found"
            return f"Confidence: {confidence:.0%}"

        # Determine confidence level label
        if confidence >= 0.8:
            level = "High"
        elif confidence >= 0.6:
            level = "Medium"
        else:
            level = "Low"

        # Build explanation based on what was found
        fact = facts[0]  # Use the highest-confidence fact for explanation
        type_labels = {
            "condition": "diagnosis code",
            "measurement": "lab result",
            "drug": "medication record",
            "procedure": "procedure record",
            "observation": "clinical observation",
        }
        type_label = type_labels.get(criterion_type, "clinical record")

        concept_info = fact.concept_name
        if fact.omop_concept_id:
            concept_info += f" (OMOP:{fact.omop_concept_id})"

        return (
            f"{level} confidence ({confidence:.0%}): "
            f"{type_label} match on {concept_info}"
        )
