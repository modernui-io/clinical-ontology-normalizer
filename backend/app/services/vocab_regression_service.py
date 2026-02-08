"""Vocabulary Update Regression Testing Service.

Dir-CI-3.5: Detects when OMOP vocabulary updates break existing mappings.
Captures baselines of current vocabulary mappings and compares against
new vocabulary versions to identify concept ID changes, deprecations,
domain changes, new mappings, and confidence changes.

Supports impact assessment for clinical trial eligibility criteria
to prevent vocabulary updates from silently breaking trial screening.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.vocab_regression import (
    ChangeType,
    RiskLevel,
    VocabBaseline,
    VocabChange,
    VocabMapping,
    VocabRegressionReport,
    VocabUpdatePreview,
)

logger = logging.getLogger(__name__)

# Terms associated with clinical trial eligibility criteria.
# Changes to these concepts are classified as high risk because they
# directly affect which patients are screened as eligible/ineligible.
TRIAL_CRITICAL_TERMS: set[str] = {
    # Ophthalmology / Retinal
    "diabetic macular edema",
    "dme",
    "diabetic retinopathy",
    "macular degeneration",
    "age-related macular degeneration",
    "wet amd",
    "dry amd",
    "retinal vein occlusion",
    "neovascular amd",
    # Dermatology
    "atopic dermatitis",
    "eczema",
    "psoriasis",
    "cutaneous squamous cell carcinoma",
    "cscc",
    "basal cell carcinoma",
    "melanoma",
    # Oncology
    "non-small cell lung cancer",
    "nsclc",
    "small cell lung cancer",
    "colorectal cancer",
    "breast cancer",
    "hepatocellular carcinoma",
    "renal cell carcinoma",
    "lymphoma",
    "multiple myeloma",
    "acute myeloid leukemia",
    "chronic lymphocytic leukemia",
    # Immunology / Rheumatology
    "rheumatoid arthritis",
    "systemic lupus erythematosus",
    "lupus",
    "ankylosing spondylitis",
    "crohn's disease",
    "ulcerative colitis",
    # Cardiology
    "heart failure",
    "atrial fibrillation",
    "acute coronary syndrome",
    "myocardial infarction",
    "pulmonary arterial hypertension",
    # Endocrinology
    "type 1 diabetes",
    "type 2 diabetes",
    "diabetes mellitus type 2",
    "diabetic nephropathy",
    "diabetic neuropathy",
    # Neurology
    "alzheimer's disease",
    "parkinson's disease",
    "multiple sclerosis",
    "epilepsy",
    "migraine",
    # Respiratory
    "asthma",
    "copd",
    "chronic obstructive pulmonary disease",
    "idiopathic pulmonary fibrosis",
    "cystic fibrosis",
    # Infectious Disease
    "hiv",
    "hepatitis b",
    "hepatitis c",
    "covid-19",
    # Key Lab Values
    "hemoglobin a1c",
    "hba1c",
    "egfr",
    "estimated glomerular filtration rate",
    "creatinine",
    "serum creatinine",
    "alt",
    "alanine aminotransferase",
    "ast",
    "aspartate aminotransferase",
    "inr",
    "international normalized ratio",
    # Key Medications
    "dupilumab",
    "cemiplimab",
    "aflibercept",
    "nivolumab",
    "pembrolizumab",
    "adalimumab",
    "infliximab",
    "methotrexate",
    "rituximab",
}

# Domains where changes are considered higher risk for trial eligibility
HIGH_RISK_DOMAINS: set[str] = {"Condition", "Drug", "Measurement"}


class VocabRegressionService:
    """Service for vocabulary update regression testing.

    Captures baselines of term-to-concept mappings and detects regressions
    when vocabulary versions change. Baselines are stored in memory with
    optional file persistence for version control.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        """Initialize the regression service.

        Args:
            storage_dir: Optional directory for persisting baselines as JSON.
                         If None, baselines are stored in memory only.
        """
        self._baselines: dict[str, VocabBaseline] = {}
        self._storage_dir = storage_dir
        if storage_dir and not storage_dir.exists():
            storage_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Baseline capture
    # ------------------------------------------------------------------

    def capture_baseline(
        self,
        name: str,
        mappings: list[VocabMapping],
        *,
        version: str = "unknown",
        description: str = "",
        persist: bool = True,
    ) -> VocabBaseline:
        """Capture a baseline snapshot of current vocabulary mappings.

        Args:
            name: Unique name for this baseline (e.g. 'v5.0-2026-01').
            mappings: List of current term-to-concept mappings.
            version: Vocabulary version identifier.
            description: Optional description.
            persist: Whether to persist the baseline to disk.

        Returns:
            The captured VocabBaseline.
        """
        baseline = VocabBaseline(
            name=name,
            version=version,
            timestamp=datetime.utcnow(),
            mappings=mappings,
            total_count=len(mappings),
            description=description,
        )

        self._baselines[name] = baseline
        logger.info(
            "Captured vocabulary baseline '%s' with %d mappings (version=%s)",
            name,
            len(mappings),
            version,
        )

        if persist and self._storage_dir:
            self._save_baseline(baseline)

        return baseline

    def capture_baseline_from_dict(
        self,
        name: str,
        raw_mappings: list[dict[str, Any]],
        *,
        version: str = "unknown",
        description: str = "",
        persist: bool = True,
    ) -> VocabBaseline:
        """Capture a baseline from raw dictionary data.

        Convenience method for loading from JSON fixtures or API responses.

        Args:
            name: Unique baseline name.
            raw_mappings: List of mapping dicts with term, concept_id, etc.
            version: Vocabulary version.
            description: Optional description.
            persist: Whether to persist to disk.

        Returns:
            The captured VocabBaseline.
        """
        mappings = [VocabMapping(**m) for m in raw_mappings]
        return self.capture_baseline(
            name,
            mappings,
            version=version,
            description=description,
            persist=persist,
        )

    def get_baseline(self, name: str) -> VocabBaseline | None:
        """Retrieve a named baseline.

        Checks in-memory cache first, then attempts to load from disk.

        Args:
            name: Baseline name to look up.

        Returns:
            VocabBaseline if found, None otherwise.
        """
        if name in self._baselines:
            return self._baselines[name]

        # Try loading from disk
        if self._storage_dir:
            loaded = self._load_baseline(name)
            if loaded:
                self._baselines[name] = loaded
                return loaded

        return None

    def list_baselines(self) -> list[str]:
        """List all available baseline names."""
        names = set(self._baselines.keys())
        if self._storage_dir and self._storage_dir.exists():
            for path in self._storage_dir.glob("*.json"):
                names.add(path.stem)
        return sorted(names)

    # ------------------------------------------------------------------
    # Comparison engine
    # ------------------------------------------------------------------

    def compare_against_baseline(
        self,
        baseline: VocabBaseline,
        current_mappings: list[VocabMapping],
        *,
        current_version: str = "current",
    ) -> VocabRegressionReport:
        """Compare current mappings against a baseline to detect regressions.

        Detects five types of changes:
        1. ID_CHANGED: Same term now maps to a different concept_id
        2. DEPRECATED: Concept is no longer standard (standard_concept changed)
        3. DOMAIN_CHANGED: Concept moved to a different domain
        4. NEW_MAPPING: Term not in baseline but present in current
        5. CONFIDENCE_CHANGED: Mapping confidence score significantly changed
        6. NAME_CHANGED: Concept name changed for the same concept_id

        Args:
            baseline: The baseline to compare against.
            current_mappings: Current term-to-concept mappings.
            current_version: Version label for the current vocabulary.

        Returns:
            VocabRegressionReport with all detected changes.
        """
        # Index baseline mappings by normalized term
        baseline_index: dict[str, VocabMapping] = {
            m.term.lower().strip(): m for m in baseline.mappings
        }
        current_index: dict[str, VocabMapping] = {
            m.term.lower().strip(): m for m in current_mappings
        }

        changes: list[VocabChange] = []
        unchanged_count = 0

        # Check each baseline mapping against current
        for term_key, baseline_mapping in baseline_index.items():
            if term_key not in current_index:
                # Term no longer has a mapping -> treat as deprecation
                change = VocabChange(
                    term=baseline_mapping.term,
                    change_type=ChangeType.DEPRECATED,
                    old_value=baseline_mapping.concept_name,
                    new_value=None,
                    old_concept_id=baseline_mapping.concept_id,
                    new_concept_id=None,
                    domain_id=baseline_mapping.domain_id,
                    risk_level=self._assess_risk(
                        baseline_mapping.term,
                        ChangeType.DEPRECATED,
                        baseline_mapping.domain_id,
                    ),
                    detail=(
                        f"Term '{baseline_mapping.term}' (concept {baseline_mapping.concept_id}) "
                        f"no longer has a mapping in the current vocabulary"
                    ),
                )
                changes.append(change)
                continue

            current_mapping = current_index[term_key]
            term_changes = self._detect_changes(baseline_mapping, current_mapping)

            if term_changes:
                changes.extend(term_changes)
            else:
                unchanged_count += 1

        # Check for new mappings (in current but not in baseline)
        for term_key, current_mapping in current_index.items():
            if term_key not in baseline_index:
                change = VocabChange(
                    term=current_mapping.term,
                    change_type=ChangeType.NEW_MAPPING,
                    old_value=None,
                    new_value=current_mapping.concept_name,
                    old_concept_id=None,
                    new_concept_id=current_mapping.concept_id,
                    domain_id=current_mapping.domain_id,
                    risk_level=RiskLevel.LOW,
                    detail=(
                        f"New mapping available: '{current_mapping.term}' -> "
                        f"{current_mapping.concept_name} ({current_mapping.concept_id})"
                    ),
                )
                changes.append(change)

        # Classify changes
        high_risk = [c for c in changes if c.risk_level == RiskLevel.HIGH]
        medium_risk = [c for c in changes if c.risk_level == RiskLevel.MEDIUM]
        low_risk = [c for c in changes if c.risk_level == RiskLevel.LOW]
        new_mappings = [c for c in changes if c.change_type == ChangeType.NEW_MAPPING]
        deprecated = [c for c in changes if c.change_type == ChangeType.DEPRECATED]
        trial_impacting = self._get_trial_impacting_changes(changes)

        return VocabRegressionReport(
            baseline_name=baseline.name,
            baseline_version=baseline.version,
            current_version=current_version,
            comparison_timestamp=datetime.utcnow(),
            total_checked=len(baseline_index),
            unchanged=unchanged_count,
            changed=len(changes) - len(new_mappings),
            changes=changes,
            high_risk_changes=len(high_risk),
            medium_risk_changes=len(medium_risk),
            low_risk_changes=len(low_risk),
            new_mappings=len(new_mappings),
            deprecated_mappings=len(deprecated),
            trial_impacting_changes=trial_impacting,
        )

    def _detect_changes(
        self,
        baseline: VocabMapping,
        current: VocabMapping,
    ) -> list[VocabChange]:
        """Detect all changes between a baseline and current mapping for a term.

        Args:
            baseline: Baseline mapping entry.
            current: Current mapping entry.

        Returns:
            List of VocabChange objects (may be empty if no changes).
        """
        changes: list[VocabChange] = []

        # 1. Concept ID change
        if baseline.concept_id != current.concept_id:
            changes.append(
                VocabChange(
                    term=baseline.term,
                    change_type=ChangeType.ID_CHANGED,
                    old_value=f"{baseline.concept_name} ({baseline.concept_id})",
                    new_value=f"{current.concept_name} ({current.concept_id})",
                    old_concept_id=baseline.concept_id,
                    new_concept_id=current.concept_id,
                    domain_id=baseline.domain_id,
                    risk_level=self._assess_risk(
                        baseline.term, ChangeType.ID_CHANGED, baseline.domain_id
                    ),
                    detail=(
                        f"Concept ID changed from {baseline.concept_id} "
                        f"({baseline.concept_name}) to {current.concept_id} "
                        f"({current.concept_name})"
                    ),
                )
            )

        # 2. Standard concept status change (deprecation)
        if baseline.standard_concept != current.standard_concept:
            is_deprecation = (
                baseline.standard_concept == "S" and current.standard_concept != "S"
            )
            change_type = ChangeType.DEPRECATED if is_deprecation else ChangeType.CONFIDENCE_CHANGED
            changes.append(
                VocabChange(
                    term=baseline.term,
                    change_type=change_type,
                    old_value=f"standard_concept={baseline.standard_concept}",
                    new_value=f"standard_concept={current.standard_concept}",
                    old_concept_id=baseline.concept_id,
                    new_concept_id=current.concept_id,
                    domain_id=baseline.domain_id,
                    risk_level=self._assess_risk(
                        baseline.term,
                        change_type,
                        baseline.domain_id,
                    ),
                    detail=(
                        f"Standard concept status changed from "
                        f"'{baseline.standard_concept}' to '{current.standard_concept}'"
                    ),
                )
            )

        # 3. Domain change
        if baseline.domain_id != current.domain_id:
            changes.append(
                VocabChange(
                    term=baseline.term,
                    change_type=ChangeType.DOMAIN_CHANGED,
                    old_value=baseline.domain_id,
                    new_value=current.domain_id,
                    old_concept_id=baseline.concept_id,
                    new_concept_id=current.concept_id,
                    domain_id=current.domain_id,
                    risk_level=self._assess_risk(
                        baseline.term, ChangeType.DOMAIN_CHANGED, baseline.domain_id
                    ),
                    detail=(
                        f"Domain changed from '{baseline.domain_id}' to "
                        f"'{current.domain_id}'"
                    ),
                )
            )

        # 4. Concept name change (same concept_id, different name)
        if (
            baseline.concept_id == current.concept_id
            and baseline.concept_name != current.concept_name
        ):
            changes.append(
                VocabChange(
                    term=baseline.term,
                    change_type=ChangeType.NAME_CHANGED,
                    old_value=baseline.concept_name,
                    new_value=current.concept_name,
                    old_concept_id=baseline.concept_id,
                    new_concept_id=current.concept_id,
                    domain_id=baseline.domain_id,
                    risk_level=RiskLevel.LOW,
                    detail=(
                        f"Concept name changed from '{baseline.concept_name}' "
                        f"to '{current.concept_name}'"
                    ),
                )
            )

        # 5. Confidence change (>10% difference)
        if abs(baseline.confidence - current.confidence) > 0.1:
            changes.append(
                VocabChange(
                    term=baseline.term,
                    change_type=ChangeType.CONFIDENCE_CHANGED,
                    old_value=f"{baseline.confidence:.3f}",
                    new_value=f"{current.confidence:.3f}",
                    old_concept_id=baseline.concept_id,
                    new_concept_id=current.concept_id,
                    domain_id=baseline.domain_id,
                    risk_level=self._assess_risk(
                        baseline.term,
                        ChangeType.CONFIDENCE_CHANGED,
                        baseline.domain_id,
                    ),
                    detail=(
                        f"Mapping confidence changed from {baseline.confidence:.3f} "
                        f"to {current.confidence:.3f}"
                    ),
                )
            )

        return changes

    # ------------------------------------------------------------------
    # Risk assessment
    # ------------------------------------------------------------------

    def _assess_risk(
        self,
        term: str,
        change_type: ChangeType,
        domain_id: str,
    ) -> RiskLevel:
        """Assess the risk level of a vocabulary change.

        High risk criteria:
        - Term is in TRIAL_CRITICAL_TERMS and domain is clinical
        - Concept ID changed for a term in a high-risk domain
        - Deprecation of a concept in a high-risk domain

        Medium risk criteria:
        - Domain change for any term
        - Concept ID change for non-trial-critical terms

        Low risk criteria:
        - Confidence changes
        - Name changes
        - New mappings

        Args:
            term: The clinical term.
            change_type: Type of change detected.
            domain_id: Domain of the affected concept.

        Returns:
            Assessed RiskLevel.
        """
        is_trial_critical = term.lower().strip() in TRIAL_CRITICAL_TERMS
        is_high_risk_domain = domain_id in HIGH_RISK_DOMAINS

        # Trial-critical term changes are always high risk
        if is_trial_critical and change_type in (
            ChangeType.ID_CHANGED,
            ChangeType.DEPRECATED,
            ChangeType.DOMAIN_CHANGED,
        ):
            return RiskLevel.HIGH

        # Deprecation in high-risk domains
        if change_type == ChangeType.DEPRECATED and is_high_risk_domain:
            return RiskLevel.HIGH

        # Concept ID changes in high-risk domains
        if change_type == ChangeType.ID_CHANGED and is_high_risk_domain:
            return RiskLevel.MEDIUM

        # Domain changes are at least medium risk
        if change_type == ChangeType.DOMAIN_CHANGED:
            return RiskLevel.MEDIUM

        # Confidence changes for trial-critical terms
        if change_type == ChangeType.CONFIDENCE_CHANGED and is_trial_critical:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def get_high_risk_changes(
        self, report: VocabRegressionReport
    ) -> list[VocabChange]:
        """Extract high-risk changes from a regression report.

        High-risk changes are those that could affect trial eligibility
        criteria or break critical clinical workflows.

        Args:
            report: A completed VocabRegressionReport.

        Returns:
            List of VocabChange entries with HIGH risk level.
        """
        return [c for c in report.changes if c.risk_level == RiskLevel.HIGH]

    def _get_trial_impacting_changes(
        self, changes: list[VocabChange]
    ) -> list[VocabChange]:
        """Identify changes that specifically affect trial eligibility criteria.

        A change is trial-impacting if the term is in TRIAL_CRITICAL_TERMS
        and the change type could affect screening results.

        Args:
            changes: All detected changes.

        Returns:
            Subset of changes that impact trial eligibility.
        """
        impacting = []
        for change in changes:
            term_lower = change.term.lower().strip()
            if term_lower in TRIAL_CRITICAL_TERMS and change.change_type in (
                ChangeType.ID_CHANGED,
                ChangeType.DEPRECATED,
                ChangeType.DOMAIN_CHANGED,
                ChangeType.CONFIDENCE_CHANGED,
            ):
                impacting.append(change)
        return impacting

    # ------------------------------------------------------------------
    # Vocabulary update preview
    # ------------------------------------------------------------------

    def preview_vocabulary_update(
        self,
        baseline_name: str,
        new_vocab_mappings: list[VocabMapping],
        *,
        new_version: str = "preview",
    ) -> VocabUpdatePreview:
        """Preview the impact of a vocabulary update before applying it.

        Runs a full comparison and generates a recommendation.

        Args:
            baseline_name: Name of the baseline to compare against.
            new_vocab_mappings: Proposed new vocabulary mappings.
            new_version: Version label for the new vocabulary.

        Returns:
            VocabUpdatePreview with impact assessment and recommendation.

        Raises:
            ValueError: If the baseline is not found.
        """
        baseline = self.get_baseline(baseline_name)
        if baseline is None:
            raise ValueError(f"Baseline '{baseline_name}' not found")

        report = self.compare_against_baseline(
            baseline,
            new_vocab_mappings,
            current_version=new_version,
        )

        # Generate recommendation
        if report.high_risk_changes > 0:
            recommendation = "block_update"
        elif report.medium_risk_changes > 5 or report.changed > len(baseline.mappings) * 0.1:
            recommendation = "review_required"
        else:
            recommendation = "safe_to_apply"

        return VocabUpdatePreview(
            baseline_name=baseline_name,
            total_mappings=baseline.total_count,
            affected_mappings=report.changed,
            breaking_changes=report.high_risk_changes,
            safe_changes=report.low_risk_changes + report.medium_risk_changes,
            recommendation=recommendation,
            report=report,
        )

    # ------------------------------------------------------------------
    # File persistence
    # ------------------------------------------------------------------

    def _save_baseline(self, baseline: VocabBaseline) -> None:
        """Persist a baseline to a JSON file.

        Args:
            baseline: The baseline to save.
        """
        if not self._storage_dir:
            return

        file_path = self._storage_dir / f"{baseline.name}.json"
        data = baseline.model_dump(mode="json")
        # Convert datetime to ISO string for JSON serialization
        if isinstance(data.get("timestamp"), datetime):
            data["timestamp"] = data["timestamp"].isoformat()

        file_path.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Saved baseline '%s' to %s", baseline.name, file_path)

    def _load_baseline(self, name: str) -> VocabBaseline | None:
        """Load a baseline from a JSON file.

        Args:
            name: Baseline name (used as filename stem).

        Returns:
            VocabBaseline if found, None otherwise.
        """
        if not self._storage_dir:
            return None

        file_path = self._storage_dir / f"{name}.json"
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text())
            return VocabBaseline(**data)
        except Exception:
            logger.exception("Failed to load baseline '%s' from %s", name, file_path)
            return None

    def load_baseline_from_file(self, file_path: Path) -> VocabBaseline:
        """Load a baseline from an arbitrary JSON file path.

        Useful for loading test fixtures or externally provided baselines.

        Args:
            file_path: Path to the JSON file.

        Returns:
            VocabBaseline parsed from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file cannot be parsed.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Baseline file not found: {file_path}")

        try:
            data = json.loads(file_path.read_text())
            baseline = VocabBaseline(**data)
            self._baselines[baseline.name] = baseline
            return baseline
        except Exception as exc:
            raise ValueError(f"Failed to parse baseline file: {exc}") from exc


# Module-level singleton
_service: VocabRegressionService | None = None


def get_vocab_regression_service(
    storage_dir: Path | None = None,
) -> VocabRegressionService:
    """Get or create the vocabulary regression service singleton.

    Args:
        storage_dir: Optional directory for baseline persistence.

    Returns:
        VocabRegressionService instance.
    """
    global _service
    if _service is None:
        _service = VocabRegressionService(storage_dir=storage_dir)
    return _service


def reset_vocab_regression_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
