"""Value Set Management Service for Clinical Ontology Normalizer.

This module provides comprehensive value set management functionality:
- CRUD operations for value sets
- Version control (draft, active, retired)
- Extensional value sets (enumerated codes)
- Intensional value sets (rule-based, e.g., all descendants of a concept)
- Expansion (resolve rules to actual codes)
- Validation (check if a code is in a value set)
- Import/Export (FHIR ValueSet format, CSV)

Value sets are fundamental to clinical terminologies, allowing grouping of related codes
for use in clinical decision support, quality measures, and data validation.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class ValueSetStatus(str, Enum):
    """Status of a value set in its lifecycle."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class ValueSetType(str, Enum):
    """Type of value set definition."""

    EXTENSIONAL = "extensional"  # Enumerated list of codes
    INTENSIONAL = "intensional"  # Rule-based definition


class InclusionRuleType(str, Enum):
    """Types of inclusion rules for intensional value sets."""

    CODE = "code"  # Include specific code
    FILTER = "filter"  # Include codes matching a filter
    DESCENDANTS = "descendants"  # Include all descendants of a code
    ANCESTORS = "ancestors"  # Include all ancestors of a code
    VALUE_SET = "value_set"  # Include codes from another value set


class FilterOperator(str, Enum):
    """Operators for filter rules."""

    EQUALS = "="
    IS_A = "is-a"
    DESCENDENT_OF = "descendent-of"
    IS_NOT_A = "is-not-a"
    REGEX = "regex"
    IN = "in"
    NOT_IN = "not-in"
    GENERALIZES = "generalizes"
    CHILD_OF = "child-of"
    DESCENDENT_LEAF = "descendent-leaf"
    EXISTS = "exists"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ValueSetCode:
    """A code included in a value set."""

    system: str  # Code system URI
    code: str  # The code value
    display: str  # Display name
    version: str | None = None  # Code system version
    inactive: bool = False  # Whether code is inactive
    abstract: bool = False  # Whether code is abstract (can't be used directly)
    designation: list[dict[str, Any]] = field(default_factory=list)  # Additional names


@dataclass
class InclusionRule:
    """A rule for including codes in an intensional value set."""

    rule_type: InclusionRuleType
    system: str  # Code system URI
    code: str | None = None  # For CODE, DESCENDANTS, ANCESTORS rules
    filter_property: str | None = None  # Property to filter on
    filter_operator: FilterOperator | None = None  # Operator for filter
    filter_value: str | None = None  # Value to filter by
    value_set_id: str | None = None  # For VALUE_SET rule type
    include: bool = True  # True for include, False for exclude


@dataclass
class ValueSetVersion:
    """A version record for a value set."""

    version_id: str
    version: str
    status: ValueSetStatus
    created_at: datetime
    created_by: str | None = None
    notes: str | None = None
    code_count: int = 0


@dataclass
class ValueSet:
    """A value set definition.

    Value sets can be either:
    - Extensional: An explicit list of codes (codes list)
    - Intensional: A set of rules that define the codes (rules list)

    Both types can be expanded to produce a list of codes.
    """

    id: str
    name: str
    title: str | None = None
    description: str | None = None
    url: str | None = None  # Canonical URL for the value set
    version: str = "1.0.0"
    status: ValueSetStatus = ValueSetStatus.DRAFT
    value_set_type: ValueSetType = ValueSetType.EXTENSIONAL
    publisher: str | None = None
    contact: list[dict[str, Any]] = field(default_factory=list)
    use_context: list[dict[str, Any]] = field(default_factory=list)
    purpose: str | None = None
    copyright: str | None = None
    experimental: bool = False
    immutable: bool = False

    # Content
    codes: list[ValueSetCode] = field(default_factory=list)  # For extensional
    rules: list[InclusionRule] = field(default_factory=list)  # For intensional

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    updated_by: str | None = None

    # Version history
    version_history: list[ValueSetVersion] = field(default_factory=list)


@dataclass
class ValueSetExpansionResult:
    """Result of expanding a value set to its codes."""

    value_set_id: str
    value_set_url: str | None
    timestamp: datetime
    total: int
    offset: int = 0
    codes: list[ValueSetCode] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating a code against a value set."""

    valid: bool
    message: str | None = None
    display: str | None = None
    code: str | None = None
    system: str | None = None


# =============================================================================
# Fixture Path
# =============================================================================

VALUE_SETS_FIXTURE_FILE = (
    Path(__file__).parent.parent.parent / "fixtures" / "value_sets.json"
)


# =============================================================================
# Singleton Pattern
# =============================================================================

_value_set_service: "ValueSetService | None" = None
_value_set_lock = Lock()


def get_value_set_service() -> "ValueSetService":
    """Get the singleton ValueSetService instance.

    Returns:
        The singleton ValueSetService instance.
    """
    global _value_set_service

    if _value_set_service is None:
        with _value_set_lock:
            if _value_set_service is None:
                logger.info("Creating singleton ValueSetService instance")
                _value_set_service = ValueSetService()

    return _value_set_service


def reset_value_set_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _value_set_service
    with _value_set_lock:
        _value_set_service = None


# =============================================================================
# Value Set Service
# =============================================================================


class ValueSetService:
    """Service for managing value sets.

    Provides:
    - CRUD operations for value sets
    - Version control with draft/active/retired statuses
    - Expansion of intensional (rule-based) value sets
    - Validation of codes against value sets
    - Import/export in FHIR and CSV formats
    """

    def __init__(self) -> None:
        """Initialize the value set service."""
        self._value_sets: dict[str, ValueSet] = {}
        self._url_index: dict[str, str] = {}  # URL -> ID mapping
        self._snomed_service: Any = None
        self._icd10_service: Any = None
        self._rxnorm_service: Any = None
        self._cpt_service: Any = None

        self._load_value_sets()
        logger.info(f"ValueSetService initialized with {len(self._value_sets)} value sets")

    def _load_value_sets(self) -> None:
        """Load value sets from fixture file."""
        if VALUE_SETS_FIXTURE_FILE.exists():
            try:
                with open(VALUE_SETS_FIXTURE_FILE, "r") as f:
                    data = json.load(f)

                for vs_data in data.get("value_sets", []):
                    vs = self._parse_value_set(vs_data)
                    if vs:
                        self._value_sets[vs.id] = vs
                        if vs.url:
                            self._url_index[vs.url] = vs.id

                logger.info(f"Loaded {len(self._value_sets)} value sets from fixture")
            except Exception as e:
                logger.warning(f"Error loading value sets: {e}")
        else:
            # Create some default value sets
            self._create_default_value_sets()

    def _create_default_value_sets(self) -> None:
        """Create default value sets for common use cases."""
        # Diabetes Diagnoses Value Set
        diabetes_vs = ValueSet(
            id="vs-diabetes-diagnoses",
            name="DiabetesDiagnoses",
            title="Diabetes Mellitus Diagnoses",
            description="ICD-10-CM codes for diabetes mellitus diagnoses",
            url="http://example.org/ValueSet/diabetes-diagnoses",
            version="1.0.0",
            status=ValueSetStatus.ACTIVE,
            value_set_type=ValueSetType.EXTENSIONAL,
            codes=[
                ValueSetCode(
                    system="http://hl7.org/fhir/sid/icd-10-cm",
                    code="E11",
                    display="Type 2 diabetes mellitus",
                ),
                ValueSetCode(
                    system="http://hl7.org/fhir/sid/icd-10-cm",
                    code="E11.9",
                    display="Type 2 diabetes mellitus without complications",
                ),
                ValueSetCode(
                    system="http://hl7.org/fhir/sid/icd-10-cm",
                    code="E10",
                    display="Type 1 diabetes mellitus",
                ),
                ValueSetCode(
                    system="http://hl7.org/fhir/sid/icd-10-cm",
                    code="E10.9",
                    display="Type 1 diabetes mellitus without complications",
                ),
            ],
        )
        self._value_sets[diabetes_vs.id] = diabetes_vs
        if diabetes_vs.url:
            self._url_index[diabetes_vs.url] = diabetes_vs.id

        # Hypertension Medications (Intensional)
        htn_meds_vs = ValueSet(
            id="vs-hypertension-medications",
            name="HypertensionMedications",
            title="Hypertension Medications",
            description="RxNorm codes for antihypertensive medications",
            url="http://example.org/ValueSet/hypertension-medications",
            version="1.0.0",
            status=ValueSetStatus.ACTIVE,
            value_set_type=ValueSetType.INTENSIONAL,
            rules=[
                InclusionRule(
                    rule_type=InclusionRuleType.FILTER,
                    system="http://www.nlm.nih.gov/research/umls/rxnorm",
                    filter_property="therapeuticClass",
                    filter_operator=FilterOperator.IN,
                    filter_value="antihypertensive",
                ),
            ],
        )
        self._value_sets[htn_meds_vs.id] = htn_meds_vs
        if htn_meds_vs.url:
            self._url_index[htn_meds_vs.url] = htn_meds_vs.id

        # Common Lab Tests
        lab_tests_vs = ValueSet(
            id="vs-common-lab-tests",
            name="CommonLabTests",
            title="Common Laboratory Tests",
            description="LOINC codes for commonly ordered laboratory tests",
            url="http://example.org/ValueSet/common-lab-tests",
            version="1.0.0",
            status=ValueSetStatus.ACTIVE,
            value_set_type=ValueSetType.EXTENSIONAL,
            codes=[
                ValueSetCode(
                    system="http://loinc.org",
                    code="4548-4",
                    display="Hemoglobin A1c/Hemoglobin.total in Blood",
                ),
                ValueSetCode(
                    system="http://loinc.org",
                    code="2345-7",
                    display="Glucose [Mass/volume] in Serum or Plasma",
                ),
                ValueSetCode(
                    system="http://loinc.org",
                    code="2160-0",
                    display="Creatinine [Mass/volume] in Serum or Plasma",
                ),
                ValueSetCode(
                    system="http://loinc.org",
                    code="3094-0",
                    display="Urea nitrogen [Mass/volume] in Serum or Plasma",
                ),
                ValueSetCode(
                    system="http://loinc.org",
                    code="2823-3",
                    display="Potassium [Moles/volume] in Serum or Plasma",
                ),
            ],
        )
        self._value_sets[lab_tests_vs.id] = lab_tests_vs
        if lab_tests_vs.url:
            self._url_index[lab_tests_vs.url] = lab_tests_vs.id

        logger.info(f"Created {len(self._value_sets)} default value sets")

    def _parse_value_set(self, data: dict[str, Any]) -> ValueSet | None:
        """Parse a value set from JSON data."""
        try:
            vs_id = data.get("id", str(uuid.uuid4()))

            # Parse codes
            codes = []
            for code_data in data.get("codes", []):
                codes.append(
                    ValueSetCode(
                        system=code_data.get("system", ""),
                        code=code_data.get("code", ""),
                        display=code_data.get("display", ""),
                        version=code_data.get("version"),
                        inactive=code_data.get("inactive", False),
                        abstract=code_data.get("abstract", False),
                        designation=code_data.get("designation", []),
                    )
                )

            # Parse rules
            rules = []
            for rule_data in data.get("rules", []):
                rules.append(
                    InclusionRule(
                        rule_type=InclusionRuleType(rule_data.get("rule_type", "code")),
                        system=rule_data.get("system", ""),
                        code=rule_data.get("code"),
                        filter_property=rule_data.get("filter_property"),
                        filter_operator=(
                            FilterOperator(rule_data["filter_operator"])
                            if rule_data.get("filter_operator")
                            else None
                        ),
                        filter_value=rule_data.get("filter_value"),
                        value_set_id=rule_data.get("value_set_id"),
                        include=rule_data.get("include", True),
                    )
                )

            return ValueSet(
                id=vs_id,
                name=data.get("name", ""),
                title=data.get("title"),
                description=data.get("description"),
                url=data.get("url"),
                version=data.get("version", "1.0.0"),
                status=ValueSetStatus(data.get("status", "draft")),
                value_set_type=ValueSetType(data.get("value_set_type", "extensional")),
                publisher=data.get("publisher"),
                contact=data.get("contact", []),
                use_context=data.get("use_context", []),
                purpose=data.get("purpose"),
                copyright=data.get("copyright"),
                experimental=data.get("experimental", False),
                immutable=data.get("immutable", False),
                codes=codes,
                rules=rules,
                created_by=data.get("created_by"),
                updated_by=data.get("updated_by"),
            )
        except Exception as e:
            logger.warning(f"Error parsing value set: {e}")
            return None

    # =========================================================================
    # Lazy Loading of Code Services
    # =========================================================================

    def _get_snomed_service(self) -> Any:
        """Get SNOMED service (lazy loaded)."""
        if self._snomed_service is None:
            try:
                from app.services.snomed_service import get_snomed_service

                self._snomed_service = get_snomed_service()
            except ImportError:
                logger.warning("SNOMED service not available")
        return self._snomed_service

    def _get_icd10_service(self) -> Any:
        """Get ICD-10 service (lazy loaded)."""
        if self._icd10_service is None:
            try:
                from app.services.icd10_suggester import get_icd10_suggester_service

                self._icd10_service = get_icd10_suggester_service()
            except ImportError:
                logger.warning("ICD-10 service not available")
        return self._icd10_service

    def _get_rxnorm_service(self) -> Any:
        """Get RxNorm service (lazy loaded)."""
        if self._rxnorm_service is None:
            try:
                from app.services.rxnorm_service import get_rxnorm_service

                self._rxnorm_service = get_rxnorm_service()
            except ImportError:
                logger.warning("RxNorm service not available")
        return self._rxnorm_service

    def _get_cpt_service(self) -> Any:
        """Get CPT service (lazy loaded)."""
        if self._cpt_service is None:
            try:
                from app.services.cpt_suggester import get_cpt_suggester_service

                self._cpt_service = get_cpt_suggester_service()
            except ImportError:
                logger.warning("CPT service not available")
        return self._cpt_service

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create(
        self,
        name: str,
        value_set_type: ValueSetType = ValueSetType.EXTENSIONAL,
        title: str | None = None,
        description: str | None = None,
        url: str | None = None,
        version: str = "1.0.0",
        status: ValueSetStatus = ValueSetStatus.DRAFT,
        codes: list[ValueSetCode] | None = None,
        rules: list[InclusionRule] | None = None,
        created_by: str | None = None,
        **kwargs: Any,
    ) -> ValueSet:
        """Create a new value set.

        Args:
            name: Internal name of the value set
            value_set_type: Whether extensional or intensional
            title: Human-readable title
            description: Description of the value set
            url: Canonical URL for the value set
            version: Version string
            status: Initial status (usually draft)
            codes: List of codes for extensional value sets
            rules: List of rules for intensional value sets
            created_by: User who created the value set
            **kwargs: Additional properties

        Returns:
            The created ValueSet
        """
        vs_id = str(uuid.uuid4())

        # Check for URL uniqueness
        if url and url in self._url_index:
            raise ValueError(f"Value set with URL '{url}' already exists")

        value_set = ValueSet(
            id=vs_id,
            name=name,
            title=title,
            description=description,
            url=url,
            version=version,
            status=status,
            value_set_type=value_set_type,
            codes=codes or [],
            rules=rules or [],
            created_by=created_by,
            updated_by=created_by,
            publisher=kwargs.get("publisher"),
            contact=kwargs.get("contact", []),
            use_context=kwargs.get("use_context", []),
            purpose=kwargs.get("purpose"),
            copyright=kwargs.get("copyright"),
            experimental=kwargs.get("experimental", False),
            immutable=kwargs.get("immutable", False),
        )

        # Create initial version history entry
        value_set.version_history.append(
            ValueSetVersion(
                version_id=str(uuid.uuid4()),
                version=version,
                status=status,
                created_at=value_set.created_at,
                created_by=created_by,
                notes="Initial creation",
                code_count=len(codes) if codes else 0,
            )
        )

        self._value_sets[vs_id] = value_set
        if url:
            self._url_index[url] = vs_id

        logger.info(f"Created value set '{name}' with ID {vs_id}")
        return value_set

    def get(self, value_set_id: str) -> ValueSet | None:
        """Get a value set by ID.

        Args:
            value_set_id: The value set ID

        Returns:
            The ValueSet or None if not found
        """
        return self._value_sets.get(value_set_id)

    def get_by_url(self, url: str) -> ValueSet | None:
        """Get a value set by its canonical URL.

        Args:
            url: The canonical URL

        Returns:
            The ValueSet or None if not found
        """
        vs_id = self._url_index.get(url)
        return self._value_sets.get(vs_id) if vs_id else None

    def list(
        self,
        status: ValueSetStatus | None = None,
        value_set_type: ValueSetType | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[ValueSet], int]:
        """List value sets with optional filtering.

        Args:
            status: Filter by status
            value_set_type: Filter by type
            search: Search term for name/title/description
            offset: Pagination offset
            limit: Maximum results to return

        Returns:
            Tuple of (list of ValueSets, total count)
        """
        results = list(self._value_sets.values())

        # Apply filters
        if status:
            results = [vs for vs in results if vs.status == status]

        if value_set_type:
            results = [vs for vs in results if vs.value_set_type == value_set_type]

        if search:
            search_lower = search.lower()
            results = [
                vs
                for vs in results
                if (
                    search_lower in vs.name.lower()
                    or (vs.title and search_lower in vs.title.lower())
                    or (vs.description and search_lower in vs.description.lower())
                )
            ]

        # Sort by name
        results.sort(key=lambda vs: vs.name.lower())

        total = len(results)
        return results[offset : offset + limit], total

    def update(
        self,
        value_set_id: str,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        url: str | None = None,
        status: ValueSetStatus | None = None,
        codes: list[ValueSetCode] | None = None,
        rules: list[InclusionRule] | None = None,
        updated_by: str | None = None,
        **kwargs: Any,
    ) -> ValueSet | None:
        """Update an existing value set.

        Args:
            value_set_id: The value set ID
            name: New name (optional)
            title: New title (optional)
            description: New description (optional)
            url: New URL (optional)
            status: New status (optional)
            codes: New codes list (optional)
            rules: New rules list (optional)
            updated_by: User making the update
            **kwargs: Additional properties to update

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        # Check immutability
        if value_set.immutable and value_set.status == ValueSetStatus.ACTIVE:
            raise ValueError("Cannot modify an immutable active value set")

        # Update URL index if URL is changing
        if url and url != value_set.url:
            if url in self._url_index:
                raise ValueError(f"Value set with URL '{url}' already exists")
            if value_set.url:
                del self._url_index[value_set.url]
            self._url_index[url] = value_set_id

        # Update fields
        if name is not None:
            value_set.name = name
        if title is not None:
            value_set.title = title
        if description is not None:
            value_set.description = description
        if url is not None:
            value_set.url = url
        if status is not None:
            value_set.status = status
        if codes is not None:
            value_set.codes = codes
        if rules is not None:
            value_set.rules = rules

        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(value_set, key):
                setattr(value_set, key, value)

        value_set.updated_at = datetime.now(timezone.utc)
        value_set.updated_by = updated_by

        logger.info(f"Updated value set {value_set_id}")
        return value_set

    def delete(self, value_set_id: str) -> bool:
        """Delete a value set.

        Args:
            value_set_id: The value set ID

        Returns:
            True if deleted, False if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return False

        # Remove from URL index
        if value_set.url:
            del self._url_index[value_set.url]

        del self._value_sets[value_set_id]
        logger.info(f"Deleted value set {value_set_id}")
        return True

    # =========================================================================
    # Code Management
    # =========================================================================

    def add_code(
        self,
        value_set_id: str,
        code: ValueSetCode,
        updated_by: str | None = None,
    ) -> ValueSet | None:
        """Add a code to an extensional value set.

        Args:
            value_set_id: The value set ID
            code: The code to add
            updated_by: User making the update

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        if value_set.value_set_type != ValueSetType.EXTENSIONAL:
            raise ValueError("Cannot add individual codes to an intensional value set")

        # Check for duplicate
        for existing in value_set.codes:
            if existing.system == code.system and existing.code == code.code:
                raise ValueError(
                    f"Code {code.code} from {code.system} already exists in value set"
                )

        value_set.codes.append(code)
        value_set.updated_at = datetime.now(timezone.utc)
        value_set.updated_by = updated_by

        return value_set

    def remove_code(
        self,
        value_set_id: str,
        system: str,
        code: str,
        updated_by: str | None = None,
    ) -> ValueSet | None:
        """Remove a code from an extensional value set.

        Args:
            value_set_id: The value set ID
            system: The code system
            code: The code value
            updated_by: User making the update

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        if value_set.value_set_type != ValueSetType.EXTENSIONAL:
            raise ValueError(
                "Cannot remove individual codes from an intensional value set"
            )

        value_set.codes = [
            c for c in value_set.codes if not (c.system == system and c.code == code)
        ]
        value_set.updated_at = datetime.now(timezone.utc)
        value_set.updated_by = updated_by

        return value_set

    def add_rule(
        self,
        value_set_id: str,
        rule: InclusionRule,
        updated_by: str | None = None,
    ) -> ValueSet | None:
        """Add a rule to an intensional value set.

        Args:
            value_set_id: The value set ID
            rule: The rule to add
            updated_by: User making the update

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        if value_set.value_set_type != ValueSetType.INTENSIONAL:
            raise ValueError("Cannot add rules to an extensional value set")

        value_set.rules.append(rule)
        value_set.updated_at = datetime.now(timezone.utc)
        value_set.updated_by = updated_by

        return value_set

    def remove_rule(
        self,
        value_set_id: str,
        rule_index: int,
        updated_by: str | None = None,
    ) -> ValueSet | None:
        """Remove a rule from an intensional value set.

        Args:
            value_set_id: The value set ID
            rule_index: Index of the rule to remove
            updated_by: User making the update

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        if value_set.value_set_type != ValueSetType.INTENSIONAL:
            raise ValueError("Cannot remove rules from an extensional value set")

        if 0 <= rule_index < len(value_set.rules):
            del value_set.rules[rule_index]
            value_set.updated_at = datetime.now(timezone.utc)
            value_set.updated_by = updated_by

        return value_set

    # =========================================================================
    # Version Control
    # =========================================================================

    def create_version(
        self,
        value_set_id: str,
        new_version: str,
        status: ValueSetStatus = ValueSetStatus.DRAFT,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> ValueSet | None:
        """Create a new version of a value set.

        Args:
            value_set_id: The value set ID
            new_version: New version string
            status: Status for the new version
            notes: Version notes
            created_by: User creating the version

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        # Add version history entry
        value_set.version_history.append(
            ValueSetVersion(
                version_id=str(uuid.uuid4()),
                version=new_version,
                status=status,
                created_at=datetime.now(timezone.utc),
                created_by=created_by,
                notes=notes,
                code_count=len(value_set.codes),
            )
        )

        value_set.version = new_version
        value_set.status = status
        value_set.updated_at = datetime.now(timezone.utc)
        value_set.updated_by = created_by

        return value_set

    def get_version_history(self, value_set_id: str) -> list[ValueSetVersion]:
        """Get the version history of a value set.

        Args:
            value_set_id: The value set ID

        Returns:
            List of version records
        """
        value_set = self._value_sets.get(value_set_id)
        return value_set.version_history if value_set else []

    def activate(
        self, value_set_id: str, updated_by: str | None = None
    ) -> ValueSet | None:
        """Activate a value set (change status from draft to active).

        Args:
            value_set_id: The value set ID
            updated_by: User making the change

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        if value_set.status != ValueSetStatus.DRAFT:
            raise ValueError("Can only activate a draft value set")

        value_set.status = ValueSetStatus.ACTIVE
        value_set.updated_at = datetime.now(timezone.utc)
        value_set.updated_by = updated_by

        # Add version history entry
        value_set.version_history.append(
            ValueSetVersion(
                version_id=str(uuid.uuid4()),
                version=value_set.version,
                status=ValueSetStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                created_by=updated_by,
                notes="Activated",
                code_count=len(value_set.codes),
            )
        )

        return value_set

    def retire(
        self, value_set_id: str, updated_by: str | None = None
    ) -> ValueSet | None:
        """Retire a value set.

        Args:
            value_set_id: The value set ID
            updated_by: User making the change

        Returns:
            The updated ValueSet or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        value_set.status = ValueSetStatus.RETIRED
        value_set.updated_at = datetime.now(timezone.utc)
        value_set.updated_by = updated_by

        # Add version history entry
        value_set.version_history.append(
            ValueSetVersion(
                version_id=str(uuid.uuid4()),
                version=value_set.version,
                status=ValueSetStatus.RETIRED,
                created_at=datetime.now(timezone.utc),
                created_by=updated_by,
                notes="Retired",
                code_count=len(value_set.codes),
            )
        )

        return value_set

    # =========================================================================
    # Expansion
    # =========================================================================

    def expand(
        self,
        value_set_id: str,
        filter_text: str | None = None,
        offset: int = 0,
        count: int = 1000,
        active_only: bool = False,
    ) -> ValueSetExpansionResult | None:
        """Expand a value set to its contained codes.

        For extensional value sets, returns the enumerated codes.
        For intensional value sets, evaluates the rules to produce codes.

        Args:
            value_set_id: The value set ID
            filter_text: Optional text filter for the results
            offset: Pagination offset
            count: Maximum codes to return
            active_only: Only include active codes

        Returns:
            ValueSetExpansionResult or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        if value_set.value_set_type == ValueSetType.EXTENSIONAL:
            codes = self._expand_extensional(value_set, filter_text, active_only)
        else:
            codes = self._expand_intensional(value_set, filter_text, active_only)

        # Build parameters
        parameters: list[dict[str, Any]] = []
        if filter_text:
            parameters.append({"name": "filter", "valueString": filter_text})
        if active_only:
            parameters.append({"name": "activeOnly", "valueBoolean": True})

        return ValueSetExpansionResult(
            value_set_id=value_set_id,
            value_set_url=value_set.url,
            timestamp=datetime.now(timezone.utc),
            total=len(codes),
            offset=offset,
            codes=codes[offset : offset + count],
            parameters=parameters,
        )

    def _expand_extensional(
        self,
        value_set: ValueSet,
        filter_text: str | None,
        active_only: bool,
    ) -> list[ValueSetCode]:
        """Expand an extensional value set."""
        codes = list(value_set.codes)

        if active_only:
            codes = [c for c in codes if not c.inactive]

        if filter_text:
            filter_lower = filter_text.lower()
            codes = [
                c
                for c in codes
                if filter_lower in c.display.lower() or filter_lower in c.code.lower()
            ]

        return codes

    def _expand_intensional(
        self,
        value_set: ValueSet,
        filter_text: str | None,
        active_only: bool,
    ) -> list[ValueSetCode]:
        """Expand an intensional value set by evaluating its rules."""
        included_codes: dict[str, ValueSetCode] = {}
        excluded_codes: set[str] = set()

        for rule in value_set.rules:
            rule_codes = self._evaluate_rule(rule)

            for code in rule_codes:
                key = f"{code.system}|{code.code}"
                if rule.include:
                    if key not in excluded_codes:
                        included_codes[key] = code
                else:
                    excluded_codes.add(key)
                    if key in included_codes:
                        del included_codes[key]

        codes = list(included_codes.values())

        if active_only:
            codes = [c for c in codes if not c.inactive]

        if filter_text:
            filter_lower = filter_text.lower()
            codes = [
                c
                for c in codes
                if filter_lower in c.display.lower() or filter_lower in c.code.lower()
            ]

        return codes

    def _evaluate_rule(self, rule: InclusionRule) -> list[ValueSetCode]:
        """Evaluate a single inclusion/exclusion rule."""
        codes: list[ValueSetCode] = []

        if rule.rule_type == InclusionRuleType.CODE:
            # Single code inclusion
            if rule.code:
                codes.append(
                    ValueSetCode(
                        system=rule.system,
                        code=rule.code,
                        display=self._lookup_display(rule.system, rule.code),
                    )
                )

        elif rule.rule_type == InclusionRuleType.DESCENDANTS:
            # All descendants of a code
            if rule.code:
                codes = self._get_descendants(rule.system, rule.code)

        elif rule.rule_type == InclusionRuleType.ANCESTORS:
            # All ancestors of a code
            if rule.code:
                codes = self._get_ancestors(rule.system, rule.code)

        elif rule.rule_type == InclusionRuleType.FILTER:
            # Filter-based inclusion
            codes = self._evaluate_filter(
                rule.system,
                rule.filter_property,
                rule.filter_operator,
                rule.filter_value,
            )

        elif rule.rule_type == InclusionRuleType.VALUE_SET:
            # Include from another value set
            if rule.value_set_id:
                other_vs = self._value_sets.get(rule.value_set_id)
                if other_vs:
                    expansion = self.expand(rule.value_set_id)
                    if expansion:
                        codes = expansion.codes

        return codes

    def _lookup_display(self, system: str, code: str) -> str:
        """Look up the display name for a code."""
        if "snomed" in system.lower():
            service = self._get_snomed_service()
            if service:
                concept = service.get_concept(code)
                if concept:
                    return concept.concept_name
        elif "icd-10" in system.lower():
            service = self._get_icd10_service()
            if service:
                icd_code = service.get_code(code)
                if icd_code:
                    return icd_code.description
        elif "rxnorm" in system.lower():
            service = self._get_rxnorm_service()
            if service:
                drug = service.lookup_by_rxcui(code)
                if drug:
                    return drug.concept_name
        elif "cpt" in system.lower():
            service = self._get_cpt_service()
            if service:
                cpt_code = service.get_code(code)
                if cpt_code:
                    return cpt_code.description
        return code

    def _get_descendants(self, system: str, code: str) -> list[ValueSetCode]:
        """Get all descendants of a code."""
        codes: list[ValueSetCode] = []

        if "snomed" in system.lower():
            service = self._get_snomed_service()
            if service:
                descendants = service.get_descendants(code, max_depth=5)
                for concept in descendants:
                    codes.append(
                        ValueSetCode(
                            system=system,
                            code=concept.concept_code,
                            display=concept.concept_name,
                        )
                    )

        return codes

    def _get_ancestors(self, system: str, code: str) -> list[ValueSetCode]:
        """Get all ancestors of a code."""
        codes: list[ValueSetCode] = []

        if "snomed" in system.lower():
            service = self._get_snomed_service()
            if service:
                ancestors = service.get_ancestors(code, max_depth=5)
                for concept in ancestors:
                    codes.append(
                        ValueSetCode(
                            system=system,
                            code=concept.concept_code,
                            display=concept.concept_name,
                        )
                    )

        return codes

    def _evaluate_filter(
        self,
        system: str,
        property_name: str | None,
        operator: FilterOperator | None,
        value: str | None,
    ) -> list[ValueSetCode]:
        """Evaluate a filter-based rule."""
        codes: list[ValueSetCode] = []

        # This is a simplified implementation
        # A full implementation would support all FHIR filter operators

        if "rxnorm" in system.lower() and property_name == "therapeuticClass":
            service = self._get_rxnorm_service()
            if service and value:
                drugs = service.search_drugs(value, limit=100)
                for drug in drugs:
                    codes.append(
                        ValueSetCode(
                            system=system,
                            code=drug.rxcui,
                            display=drug.concept_name,
                        )
                    )

        return codes

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_code(
        self,
        value_set_id: str,
        system: str,
        code: str,
        display: str | None = None,
    ) -> ValidationResult:
        """Validate that a code is in a value set.

        Args:
            value_set_id: The value set ID
            system: The code system
            code: The code value
            display: Optional display name to validate

        Returns:
            ValidationResult indicating if the code is valid
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return ValidationResult(
                valid=False,
                message=f"Value set '{value_set_id}' not found",
                code=code,
                system=system,
            )

        # Expand the value set and check if code is present
        expansion = self.expand(value_set_id, count=10000)
        if not expansion:
            return ValidationResult(
                valid=False,
                message="Failed to expand value set",
                code=code,
                system=system,
            )

        for vs_code in expansion.codes:
            if vs_code.system == system and vs_code.code == code:
                # Code found
                if display and display.lower() != vs_code.display.lower():
                    return ValidationResult(
                        valid=True,
                        message=f"Code is valid but display '{display}' does not match expected '{vs_code.display}'",
                        display=vs_code.display,
                        code=code,
                        system=system,
                    )
                return ValidationResult(
                    valid=True,
                    message="Code is valid",
                    display=vs_code.display,
                    code=code,
                    system=system,
                )

        return ValidationResult(
            valid=False,
            message=f"Code '{code}' from system '{system}' is not in value set",
            code=code,
            system=system,
        )

    # =========================================================================
    # Import/Export
    # =========================================================================

    def import_fhir(self, fhir_value_set: dict[str, Any]) -> ValueSet:
        """Import a value set from FHIR ValueSet format.

        Args:
            fhir_value_set: FHIR ValueSet resource as dict

        Returns:
            The imported ValueSet
        """
        # Parse FHIR structure
        vs_id = fhir_value_set.get("id", str(uuid.uuid4()))
        name = fhir_value_set.get("name", "imported")
        title = fhir_value_set.get("title")
        description = fhir_value_set.get("description")
        url = fhir_value_set.get("url")
        version = fhir_value_set.get("version", "1.0.0")

        status_str = fhir_value_set.get("status", "draft")
        status = ValueSetStatus(status_str) if status_str in ValueSetStatus.__members__.values() else ValueSetStatus.DRAFT

        # Determine if extensional or intensional based on compose structure
        codes: list[ValueSetCode] = []
        rules: list[InclusionRule] = []
        value_set_type = ValueSetType.EXTENSIONAL

        compose = fhir_value_set.get("compose", {})
        for include in compose.get("include", []):
            system = include.get("system", "")

            # Check for concepts (extensional)
            for concept in include.get("concept", []):
                codes.append(
                    ValueSetCode(
                        system=system,
                        code=concept.get("code", ""),
                        display=concept.get("display", ""),
                    )
                )

            # Check for filters (intensional)
            for fhir_filter in include.get("filter", []):
                value_set_type = ValueSetType.INTENSIONAL
                operator_str = fhir_filter.get("op", "=")
                try:
                    operator = FilterOperator(operator_str)
                except ValueError:
                    operator = FilterOperator.EQUALS

                rules.append(
                    InclusionRule(
                        rule_type=InclusionRuleType.FILTER,
                        system=system,
                        filter_property=fhir_filter.get("property"),
                        filter_operator=operator,
                        filter_value=fhir_filter.get("value"),
                        include=True,
                    )
                )

        # Handle expansion if present
        expansion = fhir_value_set.get("expansion", {})
        for contains in expansion.get("contains", []):
            codes.append(
                ValueSetCode(
                    system=contains.get("system", ""),
                    code=contains.get("code", ""),
                    display=contains.get("display", ""),
                    inactive=contains.get("inactive", False),
                    abstract=contains.get("abstract", False),
                )
            )

        return self.create(
            name=name,
            value_set_type=value_set_type,
            title=title,
            description=description,
            url=url,
            version=version,
            status=status,
            codes=codes if value_set_type == ValueSetType.EXTENSIONAL else None,
            rules=rules if value_set_type == ValueSetType.INTENSIONAL else None,
            publisher=fhir_value_set.get("publisher"),
            copyright=fhir_value_set.get("copyright"),
            experimental=fhir_value_set.get("experimental", False),
            immutable=fhir_value_set.get("immutable", False),
        )

    def export_fhir(self, value_set_id: str, include_expansion: bool = False) -> dict[str, Any] | None:
        """Export a value set to FHIR ValueSet format.

        Args:
            value_set_id: The value set ID
            include_expansion: Whether to include the expansion

        Returns:
            FHIR ValueSet resource as dict or None if not found
        """
        value_set = self._value_sets.get(value_set_id)
        if not value_set:
            return None

        fhir_vs: dict[str, Any] = {
            "resourceType": "ValueSet",
            "id": value_set.id,
            "url": value_set.url,
            "name": value_set.name,
            "title": value_set.title,
            "status": value_set.status.value,
            "version": value_set.version,
            "description": value_set.description,
            "experimental": value_set.experimental,
            "immutable": value_set.immutable,
        }

        if value_set.publisher:
            fhir_vs["publisher"] = value_set.publisher
        if value_set.copyright:
            fhir_vs["copyright"] = value_set.copyright
        if value_set.purpose:
            fhir_vs["purpose"] = value_set.purpose

        # Build compose section
        if value_set.value_set_type == ValueSetType.EXTENSIONAL and value_set.codes:
            # Group codes by system
            codes_by_system: dict[str, list[dict[str, Any]]] = {}
            for code in value_set.codes:
                if code.system not in codes_by_system:
                    codes_by_system[code.system] = []
                codes_by_system[code.system].append({
                    "code": code.code,
                    "display": code.display,
                })

            fhir_vs["compose"] = {
                "include": [
                    {"system": system, "concept": concepts}
                    for system, concepts in codes_by_system.items()
                ]
            }

        elif value_set.value_set_type == ValueSetType.INTENSIONAL and value_set.rules:
            include_rules: list[dict[str, Any]] = []
            exclude_rules: list[dict[str, Any]] = []

            for rule in value_set.rules:
                rule_dict: dict[str, Any] = {"system": rule.system}

                if rule.rule_type == InclusionRuleType.CODE and rule.code:
                    rule_dict["concept"] = [{"code": rule.code}]
                elif rule.rule_type == InclusionRuleType.FILTER:
                    rule_dict["filter"] = [{
                        "property": rule.filter_property,
                        "op": rule.filter_operator.value if rule.filter_operator else "=",
                        "value": rule.filter_value,
                    }]
                elif rule.rule_type == InclusionRuleType.VALUE_SET:
                    rule_dict["valueSet"] = [rule.value_set_id]

                if rule.include:
                    include_rules.append(rule_dict)
                else:
                    exclude_rules.append(rule_dict)

            fhir_vs["compose"] = {"include": include_rules}
            if exclude_rules:
                fhir_vs["compose"]["exclude"] = exclude_rules

        # Include expansion if requested
        if include_expansion:
            expansion = self.expand(value_set_id)
            if expansion:
                fhir_vs["expansion"] = {
                    "identifier": f"urn:uuid:{value_set_id}-expansion",
                    "timestamp": expansion.timestamp.isoformat(),
                    "total": expansion.total,
                    "contains": [
                        {
                            "system": c.system,
                            "code": c.code,
                            "display": c.display,
                            "inactive": c.inactive,
                            "abstract": c.abstract,
                        }
                        for c in expansion.codes
                    ],
                }

        return fhir_vs

    def import_csv(
        self,
        csv_data: str,
        name: str,
        system: str,
        title: str | None = None,
        description: str | None = None,
        code_column: str = "code",
        display_column: str = "display",
    ) -> ValueSet:
        """Import a value set from CSV format.

        Args:
            csv_data: CSV data as string
            name: Name for the value set
            system: Code system for all codes
            title: Optional title
            description: Optional description
            code_column: Name of the code column
            display_column: Name of the display column

        Returns:
            The imported ValueSet
        """
        codes: list[ValueSetCode] = []
        reader = csv.DictReader(io.StringIO(csv_data))

        for row in reader:
            code_value = row.get(code_column, "").strip()
            display_value = row.get(display_column, "").strip()

            if code_value:
                codes.append(
                    ValueSetCode(
                        system=system,
                        code=code_value,
                        display=display_value or code_value,
                    )
                )

        return self.create(
            name=name,
            value_set_type=ValueSetType.EXTENSIONAL,
            title=title,
            description=description,
            codes=codes,
        )

    def export_csv(self, value_set_id: str) -> str | None:
        """Export a value set to CSV format.

        Args:
            value_set_id: The value set ID

        Returns:
            CSV data as string or None if not found
        """
        expansion = self.expand(value_set_id)
        if not expansion:
            return None

        output = io.StringIO()
        writer = csv.DictWriter(
            output, fieldnames=["system", "code", "display", "inactive", "abstract"]
        )
        writer.writeheader()

        for code in expansion.codes:
            writer.writerow({
                "system": code.system,
                "code": code.code,
                "display": code.display,
                "inactive": code.inactive,
                "abstract": code.abstract,
            })

        return output.getvalue()

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about value sets."""
        total = len(self._value_sets)
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        total_codes = 0

        for vs in self._value_sets.values():
            status = vs.status.value
            by_status[status] = by_status.get(status, 0) + 1

            vs_type = vs.value_set_type.value
            by_type[vs_type] = by_type.get(vs_type, 0) + 1

            total_codes += len(vs.codes)

        return {
            "total_value_sets": total,
            "total_codes": total_codes,
            "by_status": by_status,
            "by_type": by_type,
        }


# =============================================================================
# Dir-CI-3.3: Clinical Trial Value Set Management
# =============================================================================


class ClinicalValueSetService:
    """Value set management for clinical trial criteria matching.

    Dir-CI-3.3: Manages curated code lists used to match patients against
    trial eligibility criteria.  Replaces ad-hoc ILIKE patterns with
    versioned, hierarchical code sets.

    Key features:
    - Pre-loaded value sets for trial-relevant conditions
    - ICD-10 hierarchical expansion (prefix matching)
    - Code membership checking for eligibility screening
    - In-memory singleton with thread-safe access

    Usage::

        from app.services.value_set_service import get_clinical_value_set_service

        svc = get_clinical_value_set_service()
        vs = svc.get_value_set("diabetes_mellitus")
        is_match = svc.check_membership("E11.65", "ICD10CM", "diabetes_mellitus")
    """

    def __init__(self) -> None:
        self._value_sets: dict[str, "_ClinicalValueSet"] = {}
        self._load_clinical_value_sets()
        logger.info(
            "ClinicalValueSetService initialized with %d value sets",
            len(self._value_sets),
        )

    # =========================================================================
    # Pre-loaded Clinical Value Sets
    # =========================================================================

    def _load_clinical_value_sets(self) -> None:
        """Pre-load value sets for trial-relevant clinical conditions."""

        # --- Diabetes Mellitus ---
        self.create_value_set(
            name="diabetes_mellitus",
            oid="2.16.840.1.113883.3.464.1003.103.12.1001",
            code_system="ICD10CM",
            codes=[
                ("E10", "Type 1 diabetes mellitus"),
                ("E10.9", "Type 1 diabetes mellitus without complications"),
                ("E10.65", "Type 1 diabetes mellitus with hyperglycemia"),
                ("E11", "Type 2 diabetes mellitus"),
                ("E11.9", "Type 2 diabetes mellitus without complications"),
                ("E11.65", "Type 2 diabetes mellitus with hyperglycemia"),
                ("E13", "Other specified diabetes mellitus"),
                ("E13.9", "Other specified diabetes mellitus without complications"),
            ],
            description="Diabetes Mellitus diagnosis codes (ICD-10 + SNOMED)",
            version="1.0.0",
            domain="Endocrinology",
        )
        # Add SNOMED codes to diabetes value set
        self.update_value_set(
            name="diabetes_mellitus",
            codes_to_add=[
                ("73211009", "SNOMED", "Diabetes mellitus"),
                ("44054006", "SNOMED", "Type 2 diabetes mellitus"),
                ("46635009", "SNOMED", "Type 1 diabetes mellitus"),
            ],
            new_version="1.0.0",
        )

        # --- Diabetic Macular Edema (DME) ---
        self.create_value_set(
            name="diabetic_macular_edema",
            oid="2.16.840.1.113883.3.526.3.1449",
            code_system="ICD10CM",
            codes=[
                ("H35.81", "Retinal edema"),
                ("E11.311", "Type 2 DM with unspecified diabetic retinopathy with macular edema"),
                ("E11.3211", "Type 2 DM with mild nonproliferative diabetic retinopathy with macular edema, right eye"),
                ("E11.3212", "Type 2 DM with mild nonproliferative diabetic retinopathy with macular edema, left eye"),
                ("E11.3213", "Type 2 DM with mild nonproliferative diabetic retinopathy with macular edema, bilateral"),
                ("E11.3311", "Type 2 DM with moderate nonproliferative diabetic retinopathy with macular edema, right eye"),
                ("E10.311", "Type 1 DM with unspecified diabetic retinopathy with macular edema"),
            ],
            description="Diabetic Macular Edema diagnosis codes for EYLEA trials",
            version="1.0.0",
            domain="Ophthalmology",
        )
        # Add SNOMED codes to DME value set
        self.update_value_set(
            name="diabetic_macular_edema",
            codes_to_add=[
                ("312912001", "SNOMED", "Diabetic macular edema"),
                ("232020009", "SNOMED", "Diabetic macular edema - Loss of central vision"),
            ],
            new_version="1.0.0",
        )

        # --- Atopic Dermatitis ---
        self.create_value_set(
            name="atopic_dermatitis",
            oid="2.16.840.1.113883.3.526.3.1437",
            code_system="ICD10CM",
            codes=[
                ("L20", "Atopic dermatitis"),
                ("L20.0", "Besnier's prurigo"),
                ("L20.81", "Atopic neurodermatitis"),
                ("L20.82", "Flexural eczema"),
                ("L20.84", "Intrinsic (allergic) eczema"),
                ("L20.89", "Other atopic dermatitis"),
                ("L20.9", "Atopic dermatitis, unspecified"),
            ],
            description="Atopic Dermatitis diagnosis codes for DUPIXENT trials",
            version="1.0.0",
            domain="Dermatology",
        )
        # Add SNOMED codes
        self.update_value_set(
            name="atopic_dermatitis",
            codes_to_add=[
                ("24079001", "SNOMED", "Atopic dermatitis"),
                ("200775004", "SNOMED", "Eczema of eyelid"),
            ],
            new_version="1.0.0",
        )

        # --- Cutaneous Squamous Cell Carcinoma (CSCC) ---
        self.create_value_set(
            name="cutaneous_scc",
            oid="2.16.840.1.113883.3.526.3.1500",
            code_system="ICD10CM",
            codes=[
                ("C44.0", "Malignant neoplasm of skin of lip"),
                ("C44.1", "Malignant neoplasm of skin of eyelid"),
                ("C44.2", "Malignant neoplasm of skin of ear and external auricular canal"),
                ("C44.3", "Malignant neoplasm of skin of other and unspecified parts of face"),
                ("C44.4", "Malignant neoplasm of skin of scalp and neck"),
                ("C44.5", "Malignant neoplasm of skin of trunk"),
                ("C44.6", "Malignant neoplasm of skin of upper limb"),
                ("C44.7", "Malignant neoplasm of skin of lower limb"),
                ("C44.8", "Malignant neoplasm of overlapping sites of skin"),
                ("C44.9", "Malignant neoplasm of skin, unspecified"),
                ("C44.92", "Squamous cell carcinoma of skin, unspecified"),
            ],
            description="Cutaneous Squamous Cell Carcinoma codes for LIBTAYO trials",
            version="1.0.0",
            domain="Oncology",
        )
        # Add SNOMED codes
        self.update_value_set(
            name="cutaneous_scc",
            codes_to_add=[
                ("402561009", "SNOMED", "Squamous cell carcinoma of skin"),
                ("254651007", "SNOMED", "Squamous cell carcinoma of skin of face"),
            ],
            new_version="1.0.0",
        )

        # --- HbA1c (Lab Tests) ---
        self.create_value_set(
            name="hba1c",
            oid="2.16.840.1.113883.3.464.1003.198.12.1013",
            code_system="LOINC",
            codes=[
                ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),
                ("17856-6", "Hemoglobin A1c/Hemoglobin.total in Blood by HPLC"),
                ("4549-2", "Hemoglobin A1c/Hemoglobin.total in Blood by Electrophoresis"),
                ("62388-4", "Hemoglobin A1c/Hemoglobin.total in Blood by JDS/JSCC protocol"),
                ("71875-9", "Hemoglobin A1c/Hemoglobin.total in Blood by IFCC protocol"),
            ],
            description="HbA1c lab test LOINC codes for diabetes trial screening",
            version="1.0.0",
            domain="Laboratory",
        )

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_value_set(
        self,
        name: str,
        oid: str | None = None,
        code_system: str | None = None,
        codes: list[tuple[str, str]] | None = None,
        description: str | None = None,
        version: str = "1.0.0",
        domain: str | None = None,
    ) -> "_ClinicalValueSet":
        """Create a new clinical value set.

        Args:
            name: Unique name for the value set.
            oid: Optional OID identifier.
            code_system: Primary code system (ICD10CM, SNOMED, LOINC, RxNorm).
            codes: List of (code, display_name) tuples.
            description: Human-readable description.
            version: Semantic version string.
            domain: Clinical domain (e.g., "Endocrinology").

        Returns:
            The created _ClinicalValueSet.

        Raises:
            ValueError: If a value set with this name already exists.
        """
        if name in self._value_sets:
            raise ValueError(f"Value set '{name}' already exists")

        now = datetime.now(timezone.utc)
        members: list[_ClinicalCodeMember] = []
        if codes:
            for code_val, display in codes:
                members.append(
                    _ClinicalCodeMember(
                        code=code_val,
                        code_system=code_system or "",
                        display_name=display,
                        is_active=True,
                    )
                )

        vs = _ClinicalValueSet(
            name=name,
            oid=oid,
            version=version,
            description=description,
            code_system=code_system,
            codes=members,
            domain=domain,
            created_at=now,
            updated_at=now,
        )
        self._value_sets[name] = vs
        logger.info(
            "Created clinical value set '%s' with %d codes",
            name,
            len(members),
        )
        return vs

    def get_value_set(self, name: str) -> "_ClinicalValueSet | None":
        """Retrieve a value set by name.

        Args:
            name: Value set name.

        Returns:
            The value set, or None if not found.
        """
        return self._value_sets.get(name)

    def list_value_sets(self, domain: str | None = None) -> list["_ClinicalValueSet"]:
        """List all value sets, optionally filtered by clinical domain.

        Args:
            domain: Optional domain filter (case-insensitive).

        Returns:
            List of matching value sets.
        """
        results = list(self._value_sets.values())
        if domain:
            domain_lower = domain.lower()
            results = [
                vs for vs in results
                if vs.domain and domain_lower in vs.domain.lower()
            ]
        return sorted(results, key=lambda vs: vs.name)

    def update_value_set(
        self,
        name: str,
        codes_to_add: list[tuple[str, str, str]] | None = None,
        codes_to_remove: list[tuple[str, str]] | None = None,
        new_version: str | None = None,
    ) -> "_ClinicalValueSet | None":
        """Update a value set by adding/removing codes.

        Args:
            name: Value set name.
            codes_to_add: List of (code, code_system, display_name) tuples to add.
            codes_to_remove: List of (code, code_system) tuples to remove.
            new_version: New version string.

        Returns:
            The updated value set, or None if not found.
        """
        vs = self._value_sets.get(name)
        if not vs:
            return None

        if codes_to_add:
            existing_keys = {(m.code, m.code_system) for m in vs.codes}
            for code_val, code_sys, display in codes_to_add:
                if (code_val, code_sys) not in existing_keys:
                    vs.codes.append(
                        _ClinicalCodeMember(
                            code=code_val,
                            code_system=code_sys,
                            display_name=display,
                            is_active=True,
                        )
                    )

        if codes_to_remove:
            remove_keys = {(c, s) for c, s in codes_to_remove}
            vs.codes = [
                m for m in vs.codes
                if (m.code, m.code_system) not in remove_keys
            ]

        if new_version:
            vs.version = new_version

        vs.updated_at = datetime.now(timezone.utc)
        return vs

    # =========================================================================
    # Expansion (Hierarchical Code Resolution)
    # =========================================================================

    def expand_value_set(self, name: str) -> list["_ClinicalCodeMember"]:
        """Expand a value set to include all hierarchical children.

        For ICD-10 codes, expansion uses prefix matching: if a value set
        contains ``E11``, then ``E11.0``, ``E11.65``, ``E11.3211`` all
        match because they start with ``E11``.

        For other code systems (SNOMED, LOINC, RxNorm), returns the flat
        code list as-is.

        Args:
            name: Value set name.

        Returns:
            Expanded list of code members including hierarchical children.
            Returns empty list if value set not found.
        """
        vs = self._value_sets.get(name)
        if not vs:
            return []

        # For non-ICD10 or mixed sets, just return the flat list.
        # ICD-10 hierarchy is handled by check_membership at query time.
        # Expansion returns the curated list as stored.
        return list(vs.codes)

    # =========================================================================
    # Membership Checking
    # =========================================================================

    def check_membership(
        self,
        code: str,
        code_system: str,
        value_set_name: str,
    ) -> bool:
        """Check whether a code is a member of a value set.

        For ICD-10 codes, uses hierarchical prefix matching: if the value
        set contains ``E11``, then ``E11.65`` is a member because it is
        a child of ``E11``.

        For other code systems, performs exact match.

        Args:
            code: The code to check (e.g., "E11.65").
            code_system: Code system of the code (e.g., "ICD10CM").
            value_set_name: Name of the value set to check against.

        Returns:
            True if the code is a member, False otherwise.
        """
        vs = self._value_sets.get(value_set_name)
        if not vs:
            return False

        return self._is_member(code, code_system, vs)

    def check_membership_detailed(
        self,
        code: str,
        code_system: str,
        value_set_name: str,
    ) -> tuple[bool, str | None]:
        """Check membership and return the matched code.

        Like check_membership, but also returns which code in the value
        set matched (useful for hierarchical matches where the matched
        parent differs from the input code).

        Args:
            code: The code to check.
            code_system: Code system.
            value_set_name: Value set name.

        Returns:
            Tuple of (is_member, matched_code_or_none).
        """
        vs = self._value_sets.get(value_set_name)
        if not vs:
            return False, None

        return self._find_match(code, code_system, vs)

    def _is_member(
        self,
        code: str,
        code_system: str,
        vs: "_ClinicalValueSet",
    ) -> bool:
        """Internal: check if code is a member of value set."""
        matched, _ = self._find_match(code, code_system, vs)
        return matched

    def _find_match(
        self,
        code: str,
        code_system: str,
        vs: "_ClinicalValueSet",
    ) -> tuple[bool, str | None]:
        """Internal: find the matching code in a value set.

        ICD-10 hierarchy: a patient code is a member if it exactly matches
        a value set code OR if it starts with a value set code followed by
        a dot.  For example, value set code ``E11`` matches patient codes
        ``E11``, ``E11.9``, ``E11.65``, ``E11.3211``.
        """
        code_upper = code.upper().strip()
        system_upper = code_system.upper().strip()

        for member in vs.codes:
            member_system = member.code_system.upper().strip()
            member_code = member.code.upper().strip()

            if member_system != system_upper:
                continue

            # Exact match
            if member_code == code_upper:
                return True, member.code

            # ICD-10 hierarchical prefix matching
            if system_upper == "ICD10CM":
                # Parent code in VS matches child patient code
                if code_upper.startswith(member_code + "."):
                    return True, member.code
                if code_upper.startswith(member_code) and len(code_upper) > len(member_code):
                    # Handle codes without dot separator (e.g., E11 -> E119)
                    next_char = code_upper[len(member_code)]
                    if next_char == "." or next_char.isdigit():
                        return True, member.code

        return False, None

    # =========================================================================
    # Bulk membership for screening pipelines
    # =========================================================================

    def check_any_membership(
        self,
        codes: list[tuple[str, str]],
        value_set_name: str,
    ) -> tuple[bool, str | None]:
        """Check if any code in a list is a member of a value set.

        Useful for patient screening where a patient may have multiple
        diagnosis codes and any match is sufficient.

        Args:
            codes: List of (code, code_system) tuples.
            value_set_name: Value set to check against.

        Returns:
            Tuple of (any_match, first_matched_code).
        """
        vs = self._value_sets.get(value_set_name)
        if not vs:
            return False, None

        for code, code_system in codes:
            matched, matched_code = self._find_match(code, code_system, vs)
            if matched:
                return True, matched_code

        return False, None


@dataclass
class _ClinicalCodeMember:
    """Internal code member representation."""

    code: str
    code_system: str
    display_name: str
    is_active: bool = True


@dataclass
class _ClinicalValueSet:
    """Internal value set representation."""

    name: str
    oid: str | None
    version: str
    description: str | None
    code_system: str | None
    codes: list[_ClinicalCodeMember]
    domain: str | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Clinical Value Set Singleton
# =============================================================================

_clinical_value_set_service: ClinicalValueSetService | None = None
_clinical_value_set_lock = Lock()


def get_clinical_value_set_service() -> ClinicalValueSetService:
    """Get the singleton ClinicalValueSetService instance.

    Returns:
        The singleton ClinicalValueSetService.
    """
    global _clinical_value_set_service

    if _clinical_value_set_service is None:
        with _clinical_value_set_lock:
            if _clinical_value_set_service is None:
                logger.info("Creating singleton ClinicalValueSetService instance")
                _clinical_value_set_service = ClinicalValueSetService()

    return _clinical_value_set_service


def reset_clinical_value_set_service() -> None:
    """Reset the clinical value set singleton (for testing)."""
    global _clinical_value_set_service
    with _clinical_value_set_lock:
        _clinical_value_set_service = None
