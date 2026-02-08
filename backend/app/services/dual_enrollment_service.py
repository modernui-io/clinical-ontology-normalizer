"""Dual Enrollment Detection Service.

Finds patients currently enrolled in one trial who also qualify for other
active trials.  This is the high-value insight for pharma sponsors:
"This patient is in LIBERTY ADCHRONOS and also qualifies for EYLEA HD."

Usage:
    from app.services.dual_enrollment_service import get_dual_enrollment_service

    service = get_dual_enrollment_service()
    response = await service.find_dual_enrollment_candidates(request, session=session)
"""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trial import EnrollmentStatus, TrialStatus
from app.schemas.trial import (
    AdditionalTrialMatch,
    CDS_DISCLAIMER,
    CurrentEnrollmentInfo,
    DualEnrollmentCandidate,
    DualEnrollmentRequest,
    DualEnrollmentResponse,
    DualEnrollmentSummary,
)
from app.services.trial_eligibility_service import get_trial_service

logger = logging.getLogger(__name__)


class DualEnrollmentService:
    """Service for detecting cross-trial eligibility among enrolled patients."""

    async def find_dual_enrollment_candidates(
        self,
        request: DualEnrollmentRequest,
        *,
        session: AsyncSession,
    ) -> DualEnrollmentResponse:
        """Find patients enrolled in one trial who qualify for others.

        1. Gather all actively enrolled patients across trials.
        2. For each patient, screen them against trials they are NOT already in.
        3. Return patients who have at least one additional match.
        """
        start_time = time.perf_counter()

        trial_service = get_trial_service()
        await trial_service._ensure_loaded(session)

        active_statuses = set(request.enrollment_statuses)
        min_score = request.min_match_score

        # --- Determine which trials to consider ---
        if request.trial_id:
            # Find candidates specifically for this trial
            target_trial = trial_service._trials.get(request.trial_id)
            if not target_trial:
                # Return empty response if the target trial doesn't exist
                return DualEnrollmentResponse(
                    summary=DualEnrollmentSummary(
                        total_enrolled_patients_checked=0,
                        total_patients_with_additional_matches=0,
                        total_additional_matches=0,
                        trials_checked=0,
                        screening_duration_ms=0.0,
                    ),
                    candidates=[],
                )
            # All recruiting trials are candidates for cross-matching
            all_trial_ids = [
                tid for tid, rec in trial_service._trials.items()
                if rec.status == TrialStatus.RECRUITING
            ]
        else:
            all_trial_ids = [
                tid for tid, rec in trial_service._trials.items()
                if rec.status == TrialStatus.RECRUITING
            ]

        # --- Build patient -> current enrollments map ---
        # patient_id -> {trial_id -> enrollment_info}
        patient_enrollments: dict[str, dict[str, CurrentEnrollmentInfo]] = {}

        for trial_id in all_trial_ids:
            record = trial_service._trials.get(trial_id)
            if not record:
                continue

            for patient_id, enrollment in record.enrollments.items():
                if enrollment.enrollment_status not in active_statuses:
                    continue

                if patient_id not in patient_enrollments:
                    patient_enrollments[patient_id] = {}

                patient_enrollments[patient_id][trial_id] = CurrentEnrollmentInfo(
                    trial_id=trial_id,
                    trial_name=record.name,
                    nct_number=record.nct_number,
                    enrollment_status=enrollment.enrollment_status,
                    match_score=enrollment.match_score,
                )

        if not patient_enrollments:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return DualEnrollmentResponse(
                summary=DualEnrollmentSummary(
                    total_enrolled_patients_checked=0,
                    total_patients_with_additional_matches=0,
                    total_additional_matches=0,
                    trials_checked=len(all_trial_ids),
                    screening_duration_ms=round(elapsed_ms, 2),
                ),
                candidates=[],
            )

        # --- Screen each enrolled patient against trials they're NOT in ---
        dual_candidates: list[DualEnrollmentCandidate] = []
        total_additional = 0

        for patient_id, current_trials in patient_enrollments.items():
            # Find trials this patient is NOT already enrolled in
            other_trial_ids = [
                tid for tid in all_trial_ids
                if tid not in current_trials
            ]

            # If a specific trial_id was requested, only check that trial
            if request.trial_id:
                if request.trial_id in current_trials:
                    # Patient is already in the target trial, skip
                    continue
                other_trial_ids = [request.trial_id]

            additional_matches: list[AdditionalTrialMatch] = []

            for other_trial_id in other_trial_ids:
                other_record = trial_service._trials.get(other_trial_id)
                if not other_record:
                    continue

                eligibility = await trial_service.check_patient_eligibility(
                    other_trial_id, patient_id, session=session
                )
                if not eligibility:
                    continue

                # Apply min score filter
                if eligibility.match_score < min_score:
                    continue

                # Only include if there's some positive signal
                if eligibility.match_score > 0 or eligibility.eligible:
                    additional_matches.append(AdditionalTrialMatch(
                        trial_id=other_trial_id,
                        trial_name=other_record.name,
                        nct_number=other_record.nct_number,
                        eligible=eligibility.eligible,
                        match_score=eligibility.match_score,
                        key_criteria_met=eligibility.inclusion_met,
                        exclusion_triggered=eligibility.exclusion_triggered,
                        safety_blocked=eligibility.safety_blocked,
                    ))

            if additional_matches:
                # Sort by match_score descending
                additional_matches.sort(
                    key=lambda m: m.match_score, reverse=True
                )
                dual_candidates.append(DualEnrollmentCandidate(
                    patient_id=patient_id,
                    current_enrollments=list(current_trials.values()),
                    additional_matches=additional_matches,
                    total_additional_matches=len(additional_matches),
                ))
                total_additional += len(additional_matches)

        # Sort candidates by number of additional matches descending
        dual_candidates.sort(
            key=lambda c: c.total_additional_matches, reverse=True
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        summary = DualEnrollmentSummary(
            total_enrolled_patients_checked=len(patient_enrollments),
            total_patients_with_additional_matches=len(dual_candidates),
            total_additional_matches=total_additional,
            trials_checked=len(all_trial_ids),
            screening_duration_ms=round(elapsed_ms, 2),
        )

        logger.info(
            "Dual enrollment detection: checked %d enrolled patients across "
            "%d trials, found %d patients with %d additional matches in %.0fms",
            len(patient_enrollments),
            len(all_trial_ids),
            len(dual_candidates),
            total_additional,
            elapsed_ms,
        )

        return DualEnrollmentResponse(
            summary=summary,
            candidates=dual_candidates,
            requires_clinician_review=True,
            cds_disclaimer=CDS_DISCLAIMER,
        )


# ==============================================================================
# Singleton
# ==============================================================================

_dual_enrollment_service: DualEnrollmentService | None = None
_dual_lock = threading.Lock()


def get_dual_enrollment_service() -> DualEnrollmentService:
    """Get singleton dual enrollment detection service instance."""
    global _dual_enrollment_service
    if _dual_enrollment_service is None:
        with _dual_lock:
            if _dual_enrollment_service is None:
                _dual_enrollment_service = DualEnrollmentService()
                logger.info("Initialized DualEnrollmentService")
    return _dual_enrollment_service
