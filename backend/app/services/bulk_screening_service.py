"""Bulk Screening Service for batch patient-trial eligibility.

Screens large batches of patients against multiple clinical trials
by delegating to the existing TrialEligibilityService.check_patient_eligibility
method and aggregating results.

Usage:
    from app.services.bulk_screening_service import get_bulk_screening_service

    service = get_bulk_screening_service()
    response = await service.bulk_screen(request, session=session)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.trial import (
    BulkPatientResult,
    BulkScreeningRequest,
    BulkScreeningResponse,
    BulkScreeningSummary,
    BulkTrialResult,
    CDS_DISCLAIMER,
)
from app.services.trial_eligibility_service import get_trial_service

logger = logging.getLogger(__name__)

# Maximum number of patient-trial pairs per request to bound memory/time.
MAX_PAIRS = 50_000


class BulkScreeningService:
    """Service for batch patient-trial eligibility screening.

    Iterates over each trial, then screens each patient against that trial
    using the existing per-patient eligibility logic.  Results are streamed
    per-trial to avoid holding all data in memory simultaneously.
    """

    async def bulk_screen(
        self,
        request: BulkScreeningRequest,
        *,
        session: AsyncSession,
    ) -> BulkScreeningResponse:
        """Screen a batch of patients against a batch of trials.

        Args:
            request: The bulk screening request with patient_ids and trial_ids.
            session: Async SQLAlchemy session.

        Returns:
            BulkScreeningResponse with per-trial results and summary stats.
        """
        start_time = time.perf_counter()

        trial_service = get_trial_service()

        patient_ids = request.patient_ids
        trial_ids = request.trial_ids
        min_score = request.min_match_score
        include_details = request.include_details

        # Validate pair count to prevent runaway requests
        pair_count = len(patient_ids) * len(trial_ids)
        if pair_count > MAX_PAIRS:
            raise ValueError(
                f"Bulk screening request exceeds maximum of {MAX_PAIRS:,} "
                f"patient-trial pairs (requested {pair_count:,}). "
                f"Reduce patient_ids or trial_ids count."
            )

        trial_results: list[BulkTrialResult] = []
        trials_not_found: list[str] = []
        total_eligible = 0
        total_pairs = 0

        for trial_id in trial_ids:
            # Verify trial exists
            trial = await trial_service.get_trial(trial_id, session=session)
            if not trial:
                trials_not_found.append(trial_id)
                logger.warning(
                    "Bulk screening: trial %s not found, skipping", trial_id
                )
                continue

            candidates: list[BulkPatientResult] = []
            eligible_count = 0

            for patient_id in patient_ids:
                eligibility = await trial_service.check_patient_eligibility(
                    trial_id, patient_id, session=session
                )
                if not eligibility:
                    continue

                total_pairs += 1

                if eligibility.eligible:
                    eligible_count += 1

                # Apply minimum score filter
                if eligibility.match_score < min_score:
                    continue

                patient_result = BulkPatientResult(
                    patient_id=patient_id,
                    eligible=eligibility.eligible,
                    match_score=eligibility.match_score,
                    inclusion_met=eligibility.inclusion_met,
                    inclusion_total=eligibility.inclusion_total,
                    exclusion_triggered=eligibility.exclusion_triggered,
                    exclusion_total=eligibility.exclusion_total,
                    missing_data=eligibility.missing_data,
                    safety_blocked=eligibility.safety_blocked,
                    criteria_details=(
                        eligibility.criteria_details if include_details else None
                    ),
                )
                candidates.append(patient_result)

            # Sort candidates by match_score descending
            candidates.sort(key=lambda c: c.match_score, reverse=True)

            screened = len(patient_ids)
            pass_rate = (eligible_count / screened * 100) if screened > 0 else 0.0

            trial_results.append(BulkTrialResult(
                trial_id=trial_id,
                trial_name=trial.name,
                nct_number=trial.nct_number,
                total_screened=screened,
                eligible_count=eligible_count,
                ineligible_count=screened - eligible_count,
                pass_rate=round(pass_rate, 2),
                candidates=candidates,
            ))

            total_eligible += eligible_count

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        overall_pass_rate = (
            (total_eligible / total_pairs * 100) if total_pairs > 0 else 0.0
        )

        summary = BulkScreeningSummary(
            total_patients=len(patient_ids),
            total_trials=len(trial_ids),
            total_pairs_screened=total_pairs,
            total_eligible=total_eligible,
            overall_pass_rate=round(overall_pass_rate, 2),
            screening_duration_ms=round(elapsed_ms, 2),
            trials_not_found=trials_not_found,
        )

        logger.info(
            "Bulk screening complete: %d patients x %d trials = %d pairs, "
            "%d eligible (%.1f%%) in %.0fms",
            len(patient_ids),
            len(trial_ids),
            total_pairs,
            total_eligible,
            overall_pass_rate,
            elapsed_ms,
        )

        return BulkScreeningResponse(
            summary=summary,
            results=trial_results,
            requires_clinician_review=True,
            cds_disclaimer=CDS_DISCLAIMER,
        )


# ==============================================================================
# Singleton
# ==============================================================================

_bulk_screening_service: BulkScreeningService | None = None
_bulk_lock = threading.Lock()


def get_bulk_screening_service() -> BulkScreeningService:
    """Get singleton bulk screening service instance."""
    global _bulk_screening_service
    if _bulk_screening_service is None:
        with _bulk_lock:
            if _bulk_screening_service is None:
                _bulk_screening_service = BulkScreeningService()
                logger.info("Initialized BulkScreeningService")
    return _bulk_screening_service
