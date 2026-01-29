"""Privacy safeguards for protecting sensitive data.

Provides utilities for:
- Detecting potential PHI in text
- Validating that synthetic/test data is being used
- Warning about privacy risks

NOTE: This is a basic implementation for demonstration.
Production systems should use comprehensive PHI detection
and comply with HIPAA/GDPR requirements.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that might indicate real PHI (overly cautious for safety)
PHI_PATTERNS = [
    # SSN patterns
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN-like pattern"),
    # Phone numbers (US format)
    (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "Phone number pattern"),
    # Email addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email pattern"),
    # Date of birth patterns
    (r"\b(?:DOB|Date of Birth|Born)[\s:]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "DOB pattern"),
    # MRN patterns
    (r"\b(?:MRN|Medical Record Number)[\s#:]+\d{6,}\b", "MRN pattern"),
]

# Patient ID patterns that indicate synthetic/test data
SAFE_PATIENT_ID_PATTERNS = [
    r"^P\d{3}$",  # P001, P002, etc.
    r"^TEST[-_]?\d+$",  # TEST1, TEST_1, etc.
    r"^DEMO[-_]?\d+$",  # DEMO1, DEMO_1, etc.
    r"^SAMPLE[-_]?\d+$",  # SAMPLE1, etc.
    r"^SYNTHETIC[-_]?\d+$",  # SYNTHETIC1, etc.
]


def detect_potential_phi(text: str) -> list[tuple[str, str]]:
    """Detect patterns that might indicate real PHI.

    This is a heuristic check that errs on the side of caution.
    It may have false positives.

    Args:
        text: Text to scan for PHI patterns

    Returns:
        List of (matched_text, pattern_description) tuples
    """
    findings = []

    for pattern, description in PHI_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            findings.append((match, description))

    return findings


def is_synthetic_patient_id(patient_id: str) -> bool:
    """Check if a patient ID follows synthetic/test data patterns.

    Args:
        patient_id: The patient identifier to check

    Returns:
        True if the ID matches safe synthetic patterns
    """
    for pattern in SAFE_PATIENT_ID_PATTERNS:
        if re.match(pattern, patient_id, re.IGNORECASE):
            return True
    return False


def validate_no_real_phi(text: str, patient_id: str, warn_only: bool = True) -> bool:
    """Validate that data doesn't appear to contain real PHI.

    This performs basic checks to catch accidental use of real
    patient data. In production, this should be more comprehensive.

    Args:
        text: Clinical note text to check
        patient_id: Patient identifier
        warn_only: If True, log warnings but don't raise. If False, raise on PHI.

    Returns:
        True if no PHI detected, False if potential PHI found

    Raises:
        ValueError: If potential PHI found and warn_only is False
    """
    issues = []

    # Check patient ID
    if not is_synthetic_patient_id(patient_id):
        issues.append(f"Patient ID '{patient_id}' doesn't match synthetic patterns")

    # Check for PHI patterns in text
    phi_findings = detect_potential_phi(text)
    for match, description in phi_findings:
        issues.append(f"Found {description}: '{match}'")

    if issues:
        message = "Potential PHI detected:\n" + "\n".join(f"  - {i}" for i in issues)

        if warn_only:
            logger.warning(f"PRIVACY WARNING: {message}")
            return False
        else:
            raise ValueError(f"PHI validation failed: {message}")

    return True


def sanitize_for_logging(text: str, max_length: int = 100) -> str:
    """Sanitize text for safe logging.

    Truncates and redacts potential sensitive data.

    Args:
        text: Text to sanitize
        max_length: Maximum length of returned text

    Returns:
        Sanitized text safe for logging
    """
    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "..."

    # Redact potential PHI patterns
    for pattern, _ in PHI_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)

    return text


class PrivacyGuard:
    """Context manager for privacy-safe operations.

    Validates data before processing and logs privacy events.
    """

    def __init__(self, patient_id: str, strict: bool = False):
        """Initialize privacy guard.

        Args:
            patient_id: Patient ID to validate
            strict: If True, raise on potential PHI. If False, warn only.
        """
        self.patient_id = patient_id
        self.strict = strict
        self.validated = False

    def validate_text(self, text: str) -> bool:
        """Validate clinical text for PHI.

        Args:
            text: Text to validate

        Returns:
            True if no PHI detected
        """
        result = validate_no_real_phi(
            text=text,
            patient_id=self.patient_id,
            warn_only=not self.strict,
        )
        self.validated = True
        return result

    def __enter__(self) -> "PrivacyGuard":
        """Enter privacy guard context."""
        if not is_synthetic_patient_id(self.patient_id):
            msg = f"Patient ID '{self.patient_id}' doesn't match synthetic patterns"
            if self.strict:
                raise ValueError(f"PHI validation failed: {msg}")
            logger.warning(f"PRIVACY WARNING: {msg}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit privacy guard context."""
        if exc_type is not None:
            logger.error(
                f"Error during privacy-guarded operation for patient {self.patient_id}"
            )
