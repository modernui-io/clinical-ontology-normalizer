"""API endpoints for Physician Evaluation of clinical QA responses.

Supports the NeurIPS paper's clinical validation section:
blind evaluation of responses from 3 ablation conditions.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research/physician-eval", tags=["physician-evaluation"])

_service = None


def _get_service():
    global _service
    if _service is None:
        from app.services.physician_evaluation_service import PhysicianEvaluationService
        _service = PhysicianEvaluationService()
    return _service


class CreateSessionRequest(BaseModel):
    evaluator_name: str = Field(..., description="Physician name")
    specialty: str = Field(..., description="Medical specialty (e.g., Emergency Medicine)")
    years_experience: int = Field(..., ge=0, description="Years of clinical experience")
    num_questions: int = Field(default=100, ge=10, le=600)
    ablation_results_path: str | None = Field(default=None)


class SubmitEvaluationRequest(BaseModel):
    question_id: str
    scores: dict[str, dict[str, int]] = Field(
        ..., description="condition_id -> {factual_correctness, clinical_safety, assertion_handling, temporal_handling}",
    )
    preference_ranking: list[str] = Field(
        ..., description="condition_ids ordered by preference (best first)",
    )
    notes: str = Field(default="")


@router.post("/sessions")
async def create_session(req: CreateSessionRequest) -> dict[str, Any]:
    """Create a new physician evaluation session."""
    service = _get_service()
    session = service.create_session(
        evaluator_name=req.evaluator_name,
        specialty=req.specialty,
        years_experience=req.years_experience,
        ablation_results_path=req.ablation_results_path,
        num_questions=req.num_questions,
    )
    return {
        "session_id": session.session_id,
        "evaluator_id": session.evaluator_id,
        "num_questions": len(session.questions),
        "conditions": list(service.EVAL_CONDITIONS),
    }


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    """List all evaluation sessions."""
    return _get_service().list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get session details including questions and progress."""
    service = _get_service()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    evaluated_ids = {ev.question_id for ev in session.evaluations}

    return {
        "session_id": session.session_id,
        "evaluator_name": session.evaluator_name,
        "specialty": session.specialty,
        "status": session.status,
        "total_questions": len(session.questions),
        "completed_evaluations": len(session.evaluations),
        "remaining": len(session.questions) - len(session.evaluations),
    }


@router.get("/sessions/{session_id}/questions/{index}")
async def get_question(session_id: str, index: int) -> dict[str, Any]:
    """Get a specific question for evaluation (blind: no condition labels)."""
    service = _get_service()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if index < 0 or index >= len(session.questions):
        raise HTTPException(status_code=404, detail="Question index out of range")

    q = session.questions[index]

    # Present responses with blind labels (A, B, C)
    blind_responses = {}
    for label, cid in q.label_to_condition.items():
        blind_responses[label] = q.responses.get(cid, "")

    return {
        "index": index,
        "question_id": q.question_id,
        "question_text": q.question_text,
        "clinical_context": q.clinical_context,
        "category": q.category,
        "task": q.task,
        "responses": blind_responses,
        "labels": list(q.label_to_condition.keys()),
        # Don't expose label_to_condition mapping (blind evaluation)
    }


@router.post("/sessions/{session_id}/evaluate")
async def submit_evaluation(
    session_id: str,
    req: SubmitEvaluationRequest,
) -> dict[str, Any]:
    """Submit a physician's evaluation for one question."""
    service = _get_service()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    evaluation = service.submit_evaluation(
        session_id=session_id,
        question_id=req.question_id,
        scores=req.scores,
        preference_ranking=req.preference_ranking,
        notes=req.notes,
    )

    return {
        "question_id": evaluation.question_id,
        "evaluator_id": evaluation.evaluator_id,
        "total_evaluations": len(session.evaluations),
        "remaining": len(session.questions) - len(session.evaluations),
    }


@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str) -> dict[str, Any]:
    """Mark an evaluation session as complete."""
    service = _get_service()
    session = service.complete_session(session_id)
    return {
        "session_id": session.session_id,
        "status": session.status,
        "total_evaluations": len(session.evaluations),
    }


@router.get("/stats")
async def get_agreement_stats() -> dict[str, Any]:
    """Get inter-rater agreement statistics."""
    return _get_service().compute_agreement_stats()


@router.get("/export")
async def export_results() -> dict[str, Any]:
    """Export all evaluation results for paper inclusion."""
    return _get_service().export_results()
