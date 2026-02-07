"""Metriport Webhook Receiver.

Receives webhook events from Metriport's Medical API and feeds
FHIR Bundles into the import pipeline for OMOP normalization and
knowledge graph construction.

Metriport webhook message types:
    - medical.consolidated-data: Patient FHIR Bundle ready (may contain
      DocumentReference with pre-signed S3 URLs — not inline FHIR resources)
    - medical.document-download: Documents downloaded from HIE
    - medical.document-conversion: Documents converted to FHIR
    - network-query.hie/pharmacy/lab: Query status updates
    - patient.admit/transfer/discharge: ADT notifications

Webhook security:
    - Signature verification via HMAC-SHA256 using x-metriport-signature header
    - Message deduplication via meta.messageId

Endpoint:
    POST /api/v1/metriport/webhook - Receive Metriport webhook
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metriport", tags=["Metriport Integration"])

# In-memory set for message deduplication (bounded to last 10K messages)
_processed_message_ids: set[str] = set()
_MAX_DEDUP_SIZE = 10_000


# ==============================================================================
# Request/Response Models
# ==============================================================================


class WebhookMeta(BaseModel):
    """Metriport webhook metadata."""

    messageId: str
    type: str
    when: str | None = None
    requestId: str | None = None
    data: dict[str, Any] | None = None  # Custom metadata passed during queries


class PatientConsolidatedData(BaseModel):
    """Patient data from Metriport consolidated-data webhook."""

    patientId: str
    externalId: str | None = None
    status: str = "completed"
    bundle: dict[str, Any] | None = None
    filters: dict[str, Any] | None = None


class DocumentDownloadInfo(BaseModel):
    """Document info from document-download webhook."""

    id: str | None = None
    fileName: str | None = None
    description: str | None = None
    status: str | None = None
    mimeType: str | None = None


class MetriportWebhookPayload(BaseModel):
    """Metriport webhook payload."""

    meta: WebhookMeta
    patients: list[PatientConsolidatedData] | None = None
    documents: list[DocumentDownloadInfo] | None = None
    # For ping messages
    ping: str | None = None


class WebhookResponse(BaseModel):
    """Response to Metriport webhook."""

    status: str = "ok"
    message: str = ""
    patients_queued: int = 0


class PingResponse(BaseModel):
    """Ping response — must echo pong with the ping value."""

    pong: str


# ==============================================================================
# Webhook Processing — Background Tasks
# ==============================================================================


async def _process_consolidated_data(
    patient_id: str,
    external_id: str | None,
    bundle: dict[str, Any],
) -> None:
    """Process consolidated data in the background.

    The bundle from Metriport consolidated-data webhook may contain:
    1. Inline FHIR resources (simple case)
    2. DocumentReference resources with pre-signed S3 URLs pointing to
       the actual FHIR Bundle (common case)

    This handler detects S3 URLs in DocumentReferences, downloads the
    actual FHIR data, and feeds it through the import pipeline.
    """
    from app.core.database import async_session_maker
    from app.services.fhir_import import FHIRImportService
    from app.services.metriport_service import MetriportService

    internal_id = f"metriport-{patient_id}"
    logger.info(f"Processing Metriport consolidated data for patient {patient_id} as {internal_id}")

    # Check if bundle contains DocumentReference with S3 URLs
    actual_bundle = bundle
    entries = bundle.get("entry", [])

    s3_urls = []
    for entry in entries:
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "DocumentReference":
            for content in resource.get("content", []):
                attachment = content.get("attachment", {})
                url = attachment.get("url", "")
                if url and ("s3.amazonaws.com" in url or "s3." in url):
                    s3_urls.append(url)

    if s3_urls:
        # Download the actual FHIR Bundle from S3
        logger.info(
            f"Found {len(s3_urls)} S3 URL(s) in consolidated data for {internal_id}, downloading..."
        )
        async with MetriportService() as mp:
            for url in s3_urls:
                try:
                    downloaded = await mp.download_bundle_from_url(url)
                    if downloaded.get("resourceType") == "Bundle":
                        actual_bundle = downloaded
                        logger.info(
                            f"Downloaded FHIR Bundle from S3 for {internal_id}: "
                            f"{len(downloaded.get('entry', []))} entries"
                        )
                        break  # Use the first valid bundle
                except Exception as e:
                    logger.error(f"Failed to download S3 bundle for {internal_id}: {e}")
                    continue

    # Import the bundle
    service = FHIRImportService()
    try:
        async with async_session_maker() as session:
            result = await service.import_bundle(
                session=session,
                bundle=actual_bundle,
                internal_patient_id=internal_id,
            )
            if result.get("success"):
                logger.info(
                    f"Metriport import succeeded for {internal_id}: "
                    f"{result.get('conditions', 0)} conditions, "
                    f"{result.get('medications', 0)} medications, "
                    f"{result.get('observations', 0)} observations, "
                    f"{result.get('procedures', 0)} procedures, "
                    f"{result.get('clinical_notes', 0)} clinical notes, "
                    f"{result.get('diagnostic_reports', 0)} diagnostic reports"
                )
            else:
                logger.error(
                    f"Metriport import failed for {internal_id}: {result.get('error')}"
                )
    except Exception as e:
        logger.error(f"Error processing Metriport bundle for {internal_id}: {e}")
    finally:
        await service.close()


async def _process_document_download(
    patient_id: str,
    documents: list[dict[str, Any]],
) -> None:
    """Process document-download webhook in the background.

    Logs downloaded documents. In a production system, this would
    trigger document conversion or direct FHIR import.
    """
    logger.info(
        f"Document download complete for patient {patient_id}: "
        f"{len(documents)} document(s)"
    )
    for doc in documents:
        logger.info(
            f"  Document: {doc.get('fileName', 'unknown')} "
            f"({doc.get('mimeType', 'unknown')}) "
            f"status={doc.get('status', 'unknown')}"
        )


async def _process_document_conversion(
    patient_id: str,
    documents: list[dict[str, Any]],
) -> None:
    """Process document-conversion webhook in the background.

    After Metriport converts C-CDA/PDF documents to FHIR, this
    handler logs the conversion status. The actual FHIR data
    arrives via the consolidated-data webhook.
    """
    logger.info(
        f"Document conversion complete for patient {patient_id}: "
        f"{len(documents)} document(s) converted"
    )


# ==============================================================================
# Signature Verification
# ==============================================================================


def _verify_webhook_signature(
    payload_body: bytes,
    signature: str | None,
    webhook_key: str | None,
) -> bool:
    """Verify Metriport webhook signature using HMAC-SHA256.

    Metriport signs webhook payloads with the webhook key configured
    during setup. The signature is sent in the x-metriport-signature header.

    Args:
        payload_body: Raw request body bytes.
        signature: x-metriport-signature header value.
        webhook_key: Configured webhook key from settings.

    Returns:
        True if signature is valid or if verification is disabled (dev mode).
    """
    if not webhook_key:
        # No key configured — skip verification (dev mode)
        return True
    if not signature:
        return False

    expected = hmac.new(
        webhook_key.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _check_dedup(message_id: str) -> bool:
    """Check if a message has already been processed.

    Returns True if the message is a duplicate (already seen).
    """
    if message_id in _processed_message_ids:
        return True

    # Evict oldest entries if we hit the cap
    if len(_processed_message_ids) >= _MAX_DEDUP_SIZE:
        # Remove roughly half to avoid frequent evictions
        to_remove = list(_processed_message_ids)[: _MAX_DEDUP_SIZE // 2]
        for mid in to_remove:
            _processed_message_ids.discard(mid)

    _processed_message_ids.add(message_id)
    return False


# ==============================================================================
# Webhook Endpoint
# ==============================================================================


@router.post(
    "/webhook",
    summary="Receive Metriport webhook",
    description=(
        "Webhook receiver for Metriport Medical API. Handles ping verification, "
        "consolidated FHIR Bundle data, document download/conversion notifications, "
        "network query updates, and ADT notifications. Responds within 4 seconds "
        "per Metriport spec — heavy processing runs in background tasks."
    ),
)
async def receive_metriport_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_metriport_signature: str | None = Header(None, alias="x-metriport-signature"),
) -> Response:
    """Receive and process Metriport webhook.

    Must respond with 200 within 4 seconds per Metriport spec.
    Actual FHIR Bundle processing happens in background tasks.
    """
    # Read raw body for signature verification
    body = await request.body()

    # Verify webhook signature (x-metriport-signature header, HMAC-SHA256)
    webhook_key = settings.metriport_webhook_key
    if webhook_key and not _verify_webhook_signature(body, x_metriport_signature, webhook_key):
        logger.warning("Metriport webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse payload
    try:
        raw = json.loads(body)
        payload = MetriportWebhookPayload(**raw)
    except Exception as e:
        logger.error(f"Failed to parse Metriport webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {e}",
        )

    msg_type = payload.meta.type
    message_id = payload.meta.messageId
    logger.info(
        f"Metriport webhook received: type={msg_type} messageId={message_id}"
    )

    # --- Handle ping ---
    # Metriport expects {"pong": "<ping-value>"} response
    if payload.ping or msg_type == "ping":
        ping_value = payload.ping or ""
        return Response(
            content=json.dumps({"pong": ping_value}),
            media_type="application/json",
            status_code=200,
        )

    # --- Message deduplication ---
    if _check_dedup(message_id):
        logger.info(f"Duplicate webhook message ignored: {message_id}")
        return Response(
            content=json.dumps(WebhookResponse(
                status="ok", message="Duplicate message ignored"
            ).model_dump()),
            media_type="application/json",
            status_code=200,
        )

    # --- Handle consolidated data ---
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
                _process_consolidated_data,
                patient_id=patient.patientId,
                external_id=patient.externalId,
                bundle=patient.bundle,
            )
            patients_queued += 1

        return Response(
            content=json.dumps(WebhookResponse(
                status="ok",
                message=f"Queued {patients_queued} patient(s) for processing",
                patients_queued=patients_queued,
            ).model_dump()),
            media_type="application/json",
            status_code=200,
        )

    # --- Handle document download ---
    if msg_type == "medical.document-download":
        for patient in payload.patients or []:
            background_tasks.add_task(
                _process_document_download,
                patient_id=patient.patientId,
                documents=[d.model_dump() for d in (payload.documents or [])],
            )
        return Response(
            content=json.dumps(WebhookResponse(
                status="ok", message=f"Acknowledged {msg_type}"
            ).model_dump()),
            media_type="application/json",
            status_code=200,
        )

    # --- Handle document conversion ---
    if msg_type == "medical.document-conversion":
        for patient in payload.patients or []:
            background_tasks.add_task(
                _process_document_conversion,
                patient_id=patient.patientId,
                documents=[d.model_dump() for d in (payload.documents or [])],
            )
        return Response(
            content=json.dumps(WebhookResponse(
                status="ok", message=f"Acknowledged {msg_type}"
            ).model_dump()),
            media_type="application/json",
            status_code=200,
        )

    # --- Handle network query status updates ---
    if msg_type.startswith("network-query."):
        logger.info(f"Network query update: {msg_type}")
        return Response(
            content=json.dumps(WebhookResponse(
                status="ok", message=f"Acknowledged {msg_type}"
            ).model_dump()),
            media_type="application/json",
            status_code=200,
        )

    # --- Handle ADT notifications ---
    if msg_type.startswith("patient."):
        logger.info(f"Patient ADT notification: {msg_type}")
        return Response(
            content=json.dumps(WebhookResponse(
                status="ok", message=f"Acknowledged {msg_type}"
            ).model_dump()),
            media_type="application/json",
            status_code=200,
        )

    # --- Unknown message type — acknowledge anyway ---
    logger.warning(f"Unknown Metriport webhook type: {msg_type}")
    return Response(
        content=json.dumps(WebhookResponse(
            status="ok", message=f"Unknown type: {msg_type}"
        ).model_dump()),
        media_type="application/json",
        status_code=200,
    )
