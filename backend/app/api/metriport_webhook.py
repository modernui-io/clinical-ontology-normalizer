"""Metriport Webhook Receiver.

Receives FHIR Bundles from Metriport's Medical API webhook and feeds
them into the FHIR Bundle import pipeline for OMOP normalization and
knowledge graph construction.

Metriport webhook message types:
    - medical.consolidated-data: Patient FHIR Bundle ready
    - network-query.hie/pharmacy/lab: Query status updates
    - patient.admit/transfer/discharge: ADT notifications

Endpoint:
    POST /api/v1/metriport/webhook - Receive Metriport webhook
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metriport", tags=["Metriport Integration"])


# ==============================================================================
# Request/Response Models
# ==============================================================================


class WebhookMeta(BaseModel):
    """Metriport webhook metadata."""

    messageId: str
    type: str
    when: str | None = None
    requestId: str | None = None


class PatientConsolidatedData(BaseModel):
    """Patient data from Metriport consolidated-data webhook."""

    patientId: str
    externalId: str | None = None
    status: str = "completed"
    bundle: dict[str, Any] | None = None
    filters: dict[str, Any] | None = None


class MetriportWebhookPayload(BaseModel):
    """Metriport webhook payload."""

    meta: WebhookMeta
    patients: list[PatientConsolidatedData] | None = None
    # For ping messages
    ping: str | None = None


class WebhookResponse(BaseModel):
    """Response to Metriport webhook."""

    status: str = "ok"
    message: str = ""
    patients_queued: int = 0


# ==============================================================================
# Webhook Processing
# ==============================================================================


async def _process_patient_bundle(
    patient_id: str,
    external_id: str | None,
    bundle: dict[str, Any],
) -> None:
    """Process a patient's FHIR Bundle in the background.

    Imports the Bundle via FHIRImportService and logs the result.
    Runs as a background task so the webhook responds within 4 seconds.
    """
    from app.core.database import async_session_maker
    from app.services.fhir_import import FHIRImportService

    internal_id = f"metriport-{patient_id}"
    logger.info(f"Processing Metriport bundle for patient {patient_id} as {internal_id}")

    service = FHIRImportService()
    try:
        async with async_session_maker() as session:
            result = await service.import_bundle(
                session=session,
                bundle=bundle,
                internal_patient_id=internal_id,
            )
            if result.get("success"):
                logger.info(
                    f"Metriport import succeeded for {internal_id}: "
                    f"{result.get('conditions', 0)} conditions, "
                    f"{result.get('medications', 0)} medications, "
                    f"{result.get('observations', 0)} observations, "
                    f"{result.get('procedures', 0)} procedures"
                )
            else:
                logger.error(
                    f"Metriport import failed for {internal_id}: {result.get('error')}"
                )
    except Exception as e:
        logger.error(f"Error processing Metriport bundle for {internal_id}: {e}")
    finally:
        await service.close()


def _verify_webhook_signature(
    payload_body: bytes,
    signature: str | None,
    webhook_key: str | None,
) -> bool:
    """Verify Metriport webhook signature using HMAC-SHA256.

    Args:
        payload_body: Raw request body bytes
        signature: x-webhook-signature header value
        webhook_key: Configured webhook key from settings

    Returns:
        True if signature is valid or if verification is disabled
    """
    if not webhook_key:
        # No key configured - skip verification (dev mode)
        return True
    if not signature:
        return False

    expected = hmac.new(
        webhook_key.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ==============================================================================
# Webhook Endpoint
# ==============================================================================


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Receive Metriport webhook",
    description=(
        "Webhook receiver for Metriport Medical API. Accepts consolidated "
        "FHIR Bundle data per patient, validates the payload, and queues "
        "background processing through the FHIR import pipeline."
    ),
)
async def receive_metriport_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_key: str | None = Header(None, alias="x-webhook-key"),
) -> WebhookResponse:
    """Receive and process Metriport webhook.

    Must respond with 200 within 4 seconds per Metriport spec.
    Actual FHIR Bundle processing happens in background tasks.
    """
    # Read raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    webhook_key = getattr(settings, "METRIPORT_WEBHOOK_KEY", None)
    if webhook_key and not _verify_webhook_signature(body, x_webhook_key, webhook_key):
        logger.warning("Metriport webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse payload
    try:
        import json
        payload = MetriportWebhookPayload(**json.loads(body))
    except Exception as e:
        logger.error(f"Failed to parse Metriport webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {e}",
        )

    msg_type = payload.meta.type
    logger.info(
        f"Metriport webhook received: type={msg_type} "
        f"messageId={payload.meta.messageId}"
    )

    # Handle ping
    if payload.ping or msg_type == "ping":
        return WebhookResponse(status="ok", message="pong")

    # Handle consolidated data
    if msg_type == "medical.consolidated-data":
        patients_queued = 0
        for patient in payload.patients or []:
            if patient.status != "completed":
                logger.info(
                    f"Skipping patient {patient.patientId}: status={patient.status}"
                )
                continue
            if not patient.bundle:
                logger.warning(
                    f"Patient {patient.patientId} has no bundle data"
                )
                continue

            background_tasks.add_task(
                _process_patient_bundle,
                patient_id=patient.patientId,
                external_id=patient.externalId,
                bundle=patient.bundle,
            )
            patients_queued += 1

        return WebhookResponse(
            status="ok",
            message=f"Queued {patients_queued} patient(s) for processing",
            patients_queued=patients_queued,
        )

    # Handle network query status updates (log only)
    if msg_type.startswith("network-query."):
        logger.info(f"Network query update: {msg_type}")
        return WebhookResponse(status="ok", message=f"Acknowledged {msg_type}")

    # Handle ADT notifications (log only for now)
    if msg_type.startswith("patient."):
        logger.info(f"Patient ADT notification: {msg_type}")
        return WebhookResponse(status="ok", message=f"Acknowledged {msg_type}")

    # Unknown message type - acknowledge anyway
    logger.warning(f"Unknown Metriport webhook type: {msg_type}")
    return WebhookResponse(status="ok", message=f"Unknown type: {msg_type}")
