"""Validation Study Service for clinical trial screening accuracy measurement.

CMO-1.4: Clinical Validation Study Design

Manages the lifecycle of validation studies that compare the system's
automated screening results against gold-standard clinical review
(board-certified physician).  Computes sensitivity, specificity, PPV, NPV,
Cohen's Kappa, and confusion matrices.

Usage:
    from app.services.validation_study_service import get_validation_study_service

    service = get_validation_study_service()
    study = service.create_study("AD Screening Validation", ...)
    service.add_case(study.id, case_data)
    metrics = service.compute_metrics(study.id)
"""

from __future__ import annotations

import logging
import math
import threading
from uuid import uuid4

from app.schemas.validation_study import (
    ConfidenceInterval,
    ConfusionMatrix,
    ScreeningResult,
    StudyCaseCreate,
    StudyCase,
    StudyMethodology,
    StudyReport,
    StudyStatus,
    ValidationMetrics,
    ValidationStudy,
    ValidationStudyCreate,
)

logger = logging.getLogger(__name__)


class ValidationStudyService:
    """Service for managing clinical validation studies.

    All data is stored in-memory.  Thread-safe via lock.
    """

    def __init__(self) -> None:
        self._studies: dict[str, ValidationStudy] = {}
        self._cases: dict[str, list[StudyCase]] = {}  # study_id -> cases
        self._lock = threading.Lock()

    # ==========================================================================
    # Study CRUD
    # ==========================================================================

    def create_study(self, create: ValidationStudyCreate) -> ValidationStudy:
        """Create a new validation study."""
        study_id = str(uuid4())
        study = ValidationStudy(
            id=study_id,
            name=create.name,
            description=create.description,
            trial_id=create.trial_id,
            sample_size=create.sample_size,
            methodology=create.methodology,
            status=StudyStatus.DESIGN,
        )
        with self._lock:
            self._studies[study_id] = study
            self._cases[study_id] = []

        logger.info(
            "Created validation study %s: '%s' for trial %s (target n=%d)",
            study_id,
            create.name,
            create.trial_id,
            create.sample_size,
        )
        return study

    def get_study(self, study_id: str) -> ValidationStudy | None:
        """Get a study by ID."""
        return self._studies.get(study_id)

    def list_studies(self) -> list[ValidationStudy]:
        """List all validation studies, ordered by creation time descending."""
        studies = list(self._studies.values())
        studies.sort(key=lambda s: s.created_at, reverse=True)
        return studies

    # ==========================================================================
    # Case Management
    # ==========================================================================

    def add_case(
        self,
        study_id: str,
        create: StudyCaseCreate,
    ) -> StudyCase | None:
        """Add a reviewed case to a validation study.

        Automatically transitions study status:
        - DESIGN -> IN_PROGRESS on first case
        - IN_PROGRESS -> COMPLETE when sample_size is reached

        Returns None if study not found.
        """
        with self._lock:
            study = self._studies.get(study_id)
            if study is None:
                return None

            case_id = str(uuid4())
            case = StudyCase(
                id=case_id,
                study_id=study_id,
                patient_id=create.patient_id,
                system_result=create.system_result,
                gold_standard_result=create.gold_standard_result,
                reviewer_id=create.reviewer_id,
                notes=create.notes,
            )
            self._cases[study_id].append(case)

            # Update case count
            study.case_count = len(self._cases[study_id])

            # Transition study status
            if study.status == StudyStatus.DESIGN:
                study.status = StudyStatus.IN_PROGRESS
                logger.info("Study %s transitioned to IN_PROGRESS", study_id)

            if study.case_count >= study.sample_size and study.status == StudyStatus.IN_PROGRESS:
                study.status = StudyStatus.COMPLETE
                logger.info(
                    "Study %s COMPLETE: %d/%d cases reviewed",
                    study_id,
                    study.case_count,
                    study.sample_size,
                )

        logger.info(
            "Added case %s to study %s: system=%s, gold=%s (reviewer=%s)",
            case_id,
            study_id,
            create.system_result.value,
            create.gold_standard_result.value,
            create.reviewer_id,
        )
        return case

    def get_cases(self, study_id: str) -> list[StudyCase]:
        """Get all cases for a study."""
        return list(self._cases.get(study_id, []))

    # ==========================================================================
    # Metrics Computation
    # ==========================================================================

    def _build_confusion_matrix(self, cases: list[StudyCase]) -> ConfusionMatrix:
        """Build a 2x2 confusion matrix from study cases.

        Positive = ELIGIBLE, Negative = INELIGIBLE.
        System result is the "test", gold standard is the "truth".
        """
        tp = tn = fp = fn = 0
        for case in cases:
            sys = case.system_result
            gold = case.gold_standard_result
            if sys == ScreeningResult.ELIGIBLE and gold == ScreeningResult.ELIGIBLE:
                tp += 1
            elif sys == ScreeningResult.INELIGIBLE and gold == ScreeningResult.INELIGIBLE:
                tn += 1
            elif sys == ScreeningResult.ELIGIBLE and gold == ScreeningResult.INELIGIBLE:
                fp += 1
            elif sys == ScreeningResult.INELIGIBLE and gold == ScreeningResult.ELIGIBLE:
                fn += 1
        return ConfusionMatrix(
            true_positive=tp,
            true_negative=tn,
            false_positive=fp,
            false_negative=fn,
        )

    @staticmethod
    def _wilson_ci(successes: int, total: int, z: float = 1.96) -> ConfidenceInterval:
        """Compute Wilson score confidence interval for a proportion.

        More accurate than the normal approximation for small samples
        or proportions near 0 or 1.
        """
        if total == 0:
            return ConfidenceInterval(lower=0.0, upper=1.0)

        p = successes / total
        denominator = 1 + z * z / total
        centre = (p + z * z / (2 * total)) / denominator
        spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator

        lower = max(0.0, centre - spread)
        upper = min(1.0, centre + spread)
        return ConfidenceInterval(lower=round(lower, 4), upper=round(upper, 4))

    def compute_metrics(self, study_id: str) -> ValidationMetrics | None:
        """Compute validation metrics for a study.

        Returns None if study not found.
        Returns metrics with None values for individual metrics where
        the denominator is zero (e.g., sensitivity when there are no
        actual positives).
        """
        cases = self._cases.get(study_id)
        if cases is None:
            return None

        cm = self._build_confusion_matrix(cases)
        total = cm.total

        # Sensitivity = TP / (TP + FN)
        sensitivity = None
        if (cm.true_positive + cm.false_negative) > 0:
            sensitivity = round(
                cm.true_positive / (cm.true_positive + cm.false_negative), 4
            )

        # Specificity = TN / (TN + FP)
        specificity = None
        if (cm.true_negative + cm.false_positive) > 0:
            specificity = round(
                cm.true_negative / (cm.true_negative + cm.false_positive), 4
            )

        # PPV = TP / (TP + FP)
        ppv = None
        if (cm.true_positive + cm.false_positive) > 0:
            ppv = round(
                cm.true_positive / (cm.true_positive + cm.false_positive), 4
            )

        # NPV = TN / (TN + FN)
        npv = None
        if (cm.true_negative + cm.false_negative) > 0:
            npv = round(
                cm.true_negative / (cm.true_negative + cm.false_negative), 4
            )

        # Accuracy = (TP + TN) / total
        accuracy = None
        if total > 0:
            accuracy = round((cm.true_positive + cm.true_negative) / total, 4)

        # F1 Score = 2 * (PPV * Sensitivity) / (PPV + Sensitivity)
        f1_score = None
        if ppv is not None and sensitivity is not None and (ppv + sensitivity) > 0:
            f1_score = round(2 * (ppv * sensitivity) / (ppv + sensitivity), 4)

        # Cohen's Kappa
        cohens_kappa = self._compute_cohens_kappa(cm)

        # Confidence intervals
        sensitivity_ci = None
        if (cm.true_positive + cm.false_negative) > 0:
            sensitivity_ci = self._wilson_ci(
                cm.true_positive, cm.true_positive + cm.false_negative
            )

        specificity_ci = None
        if (cm.true_negative + cm.false_positive) > 0:
            specificity_ci = self._wilson_ci(
                cm.true_negative, cm.true_negative + cm.false_positive
            )

        return ValidationMetrics(
            sensitivity=sensitivity,
            specificity=specificity,
            ppv=ppv,
            npv=npv,
            accuracy=accuracy,
            f1_score=f1_score,
            cohens_kappa=cohens_kappa,
            confusion_matrix=cm,
            total_cases=total,
            sensitivity_ci=sensitivity_ci,
            specificity_ci=specificity_ci,
        )

    @staticmethod
    def _compute_cohens_kappa(cm: ConfusionMatrix) -> float | None:
        """Compute Cohen's Kappa for inter-rater agreement.

        Kappa = (p_o - p_e) / (1 - p_e)

        Where:
        - p_o = observed agreement (accuracy)
        - p_e = expected agreement by chance

        Returns None if total is zero.
        Returns 1.0 for perfect agreement when p_e = 1.0 (edge case where
        both raters always give the same category).
        """
        total = cm.total
        if total == 0:
            return None

        # Observed agreement
        p_o = (cm.true_positive + cm.true_negative) / total

        # Marginals
        # System says ELIGIBLE: TP + FP
        # System says INELIGIBLE: TN + FN
        # Gold says ELIGIBLE: TP + FN
        # Gold says INELIGIBLE: TN + FP
        sys_positive = cm.true_positive + cm.false_positive
        sys_negative = cm.true_negative + cm.false_negative
        gold_positive = cm.true_positive + cm.false_negative
        gold_negative = cm.true_negative + cm.false_positive

        # Expected agreement by chance
        p_e = (
            (sys_positive * gold_positive + sys_negative * gold_negative)
            / (total * total)
        )

        if p_e == 1.0:
            # Both raters always pick the same category -- perfect agreement
            # but kappa is undefined; by convention return 1.0
            return 1.0

        kappa = (p_o - p_e) / (1 - p_e)
        return round(kappa, 4)

    # ==========================================================================
    # Report
    # ==========================================================================

    def get_study_report(self, study_id: str) -> StudyReport | None:
        """Generate a full study report with metrics and completion stats.

        Returns None if study not found.
        """
        study = self._studies.get(study_id)
        if study is None:
            return None

        metrics = self.compute_metrics(study_id)
        sample_size_achieved = study.case_count
        completion_rate = (
            round(sample_size_achieved / study.sample_size, 4)
            if study.sample_size > 0
            else 0.0
        )
        # Cap at 1.0
        completion_rate = min(1.0, completion_rate)

        meets_sensitivity = None
        meets_specificity = None
        if metrics is not None:
            if metrics.sensitivity is not None:
                meets_sensitivity = metrics.sensitivity >= 0.95
            if metrics.specificity is not None:
                meets_specificity = metrics.specificity >= 0.85

        return StudyReport(
            study=study,
            metrics=metrics,
            sample_size_achieved=sample_size_achieved,
            completion_rate=completion_rate,
            meets_sensitivity_target=meets_sensitivity,
            meets_specificity_target=meets_specificity,
        )


# ==============================================================================
# Singleton
# ==============================================================================

_validation_study_service: ValidationStudyService | None = None
_validation_study_lock = threading.Lock()


def get_validation_study_service() -> ValidationStudyService:
    """Get singleton validation study service instance."""
    global _validation_study_service
    if _validation_study_service is None:
        with _validation_study_lock:
            if _validation_study_service is None:
                _validation_study_service = ValidationStudyService()
                logger.info("Initialized ValidationStudyService")
    return _validation_study_service
