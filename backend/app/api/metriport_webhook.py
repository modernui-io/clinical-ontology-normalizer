"""Metriport Webhook Receiver.

Receives webhook events from Metriport's Medical API and feeds
FHIR Bundles into the import pipeline for OMOP normalization and
knowledge graph construction.

Metriport webhook message types:
    - medical.consolidated-data: Patient FHIR Bundle ready (may contain
      DocumentReference with pre-signed S3 URLs -- not inline FHIR resources)
    - medical.document-download: Documents downloaded from HIE
    - medical.document-conversion: Documents converted to FHIR
    - network-query.hie/pharmacy/lab: Query status updates
    - patient.admit/transfer/discharge: ADT notifications

Webhook security (CISO-6 hardening):
    - Signature verification via HMAC-SHA256 using x-metriport-signature header
    - Webhook key REQUIRED in production (startup fails if missing)
    - Timestamp validation: reject webhooks older than 5 minutes (replay protection)
    - Message deduplication via TTL-based LRU cache (with Redis fallback)
    - Rate limiting awareness: log warnings when webhook rate exceeds threshold

Endpoint:
    POST /api/v1/metriport/webhook - Receive Metriport webhook
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metriport", tags=["Metriport Integration"])

# ==============================================================================
# CISO-6: TTL-based LRU Deduplication Cache
# ==============================================================================

# Maximum age for webhook timestamps (replay attack protection)
_WEBHOOK_MAX_AGE_SECONDS = 300  # 5 minutes

# Deduplication cache settings
_MAX_DEDUP_SIZE = 10_000
_DEDUP_TTL_SECONDS = 600  # 10 minutes -- keep entries longer than max age to catch stragglers

# Rate limiting awareness settings
_RATE_WINDOW_SECONDS = 60  # 1-minute sliding window
_RATE_WARN_THRESHOLD = 100  # Warn if more than 100 webhooks per minute


class _TTLLRUCache:
    """Thread-safe LRU cache with TTL expiry for webhook deduplication.

    CISO-6: Replaces unbounded in-memory set with a proper bounded
    cache that evicts entries both by age (TTL) and by count (max_size).

    This is the in-process fallback when Redis is not available.
    """

    def __init__(self, max_size: int = _MAX_DEDUP_SIZE, ttl_seconds: int = _DEDUP_TTL_SECONDS):
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def contains(self, key: str) -> bool:
        """Check if key exists and has not expired."""
        if key not in self._cache:
            return False
        inserted_at = self._cache[key]
        if time.monotonic() - inserted_at > self._ttl_seconds:
            # Expired -- remove and return False
            del self._cache[key]
            return False
        # Move to end (most recently accessed)
        self._cache.move_to_end(key)
        return True

    def add(self, key: str) -> None:
        """Add key with current timestamp. Evicts oldest if at capacity."""
        now = time.monotonic()
        # Evict expired entries first
        self._evict_expired(now)
        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[key] = now

    def _evict_expired(self, now: float) -> None:
        """Remove entries older than TTL."""
        expired_keys = [
            k for k, ts in self._cache.items()
            if now - ts > self._ttl_seconds
        ]
        for k in expired_keys:
            del self._cache[k]

    def clear(self) -> None:
        """Clear all entries (used in tests)."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


# Module-level deduplication cache instance
_dedup_cache = _TTLLRUCache()


class _RateTracker:
    """Simple sliding-window rate tracker for webhook rate awareness.

    CISO-6: Logs warnings when webhook delivery rate exceeds the
    configured threshold, which may indicate abuse or misconfiguration.
    """

    def __init__(self, window_seconds: int = _RATE_WINDOW_SECONDS, threshold: int = _RATE_WARN_THRESHOLD):
        self._window_seconds = window_seconds
        self._threshold = threshold
        self._timestamps: list[float] = []
        self._last_warning_time: float = 0.0

    def record(self) -> None:
        """Record a webhook arrival and warn if rate is excessive."""
        now = time.monotonic()
        cutoff = now - self._window_seconds
        # Trim old entries
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]
        self._timestamps.append(now)

        current_rate = len(self._timestamps)
        if current_rate > self._threshold:
            # Only warn at most once per window to avoid log spam
            if now - self._last_warning_time > self._window_seconds:
                logger.warning(
                    f"CISO-6: Webhook rate exceeds threshold: "
                    f"{current_rate} webhooks in last {self._window_seconds}s "
                    f"(threshold: {self._threshold}). "
                    f"Possible abuse or misconfiguration."
                )
                self._last_warning_time = now

    @property
    def current_rate(self) -> int:
        """Return current count within the window (for testing)."""
        now = time.monotonic()
        cutoff = now - self._window_seconds
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]
        return len(self._timestamps)

    def clear(self) -> None:
        """Clear all entries (used in tests)."""
        self._timestamps.clear()
        self._last_warning_time = 0.0


# Module-level rate tracker instance
_rate_tracker = _RateTracker()


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
    """Ping response -- must echo pong with the ping value."""

    pong: str


# ==============================================================================
# Webhook Processing -- Background Tasks
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

                # Auto-screen patient against active trials and persist results
                try:
                    from app.services.trial_eligibility_service import get_trial_service
                    from app.models.screening_result import (
                        OverallScreeningStatus,
                        ScreeningResult,
                        ScreeningTrigger,
                    )

                    trial_service = get_trial_service()
                    screen_results = await trial_service.auto_screen_patient(
                        internal_id, session=session
                    )
                    matched_trials = [r for r in screen_results if r.get("eligible")]
                    logger.info(
                        f"Auto-screening for {internal_id}: "
                        f"{len(matched_trials)}/{len(screen_results)} trial(s) matched"
                    )

                    # Persist each screening result to the DB
                    now = datetime.now(timezone.utc)
                    for sr in screen_results:
                        if sr.get("eligible"):
                            db_status = OverallScreeningStatus.ELIGIBLE
                        elif sr.get("safety_blocked"):
                            db_status = OverallScreeningStatus.INELIGIBLE
                        elif sr.get("match_score", 0) == 0:
                            db_status = OverallScreeningStatus.INELIGIBLE
                        else:
                            db_status = OverallScreeningStatus.UNKNOWN

                        db_row = ScreeningResult(
                            patient_id=internal_id,
                            trial_id=sr["trial_id"],
                            trial_name=sr.get("trial_name"),
                            screening_date=now,
                            overall_status=db_status,
                            match_score=sr.get("match_score"),
                            safety_blocked=sr.get("safety_blocked", False),
                            triggered_by=ScreeningTrigger.WEBHOOK,
                            criterion_results=sr,
                        )
                        session.add(db_row)

                    await session.commit()
                    logger.info(
                        f"Persisted {len(screen_results)} screening result(s) "
                        f"for {internal_id}"
                    )
                except Exception as e:
                    logger.error(f"Auto-screening failed for {internal_id}: {e}")
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
# CISO-6: Signature & Timestamp Verification
# ==============================================================================


def _verify_webhook_signature(
    payload_body: bytes,
    signature: str | None,
    webhook_key: str | None,
) -> bool:
    """Verify Metriport webhook signature using HMAC-SHA256.

    Metriport signs webhook payloads with the webhook key configured
    during setup. The signature is sent in the x-metriport-signature header.

    CISO-6: In production, webhook_key is always present (enforced at startup).
    In development without a key, verification is skipped.

    Args:
        payload_body: Raw request body bytes.
        signature: x-metriport-signature header value.
        webhook_key: Configured webhook key from settings.

    Returns:
        True if signature is valid or if verification is disabled (dev mode).
    """
    if not webhook_key:
        # No key configured -- skip verification (dev mode only; production
        # enforces the key at startup via config validation)
        return True
    if not signature:
        return False

    expected = hmac.new(
        webhook_key.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _validate_webhook_timestamp(when_value: str | None) -> bool:
    """Validate webhook timestamp is within acceptable window.

    CISO-6: Reject webhooks with timestamps older than 5 minutes
    to prevent replay attacks.

    Args:
        when_value: ISO 8601 timestamp string from meta.when field.

    Returns:
        True if timestamp is valid (within window) or if no timestamp provided.
    """
    if not when_value:
        # No timestamp in payload -- allow (some webhook types may not include it)
        return True

    try:
        # Parse ISO 8601 timestamp
        webhook_time = datetime.fromisoformat(when_value.replace("Z", "+00:00"))
        # Ensure timezone-aware
        if webhook_time.tzinfo is None:
            webhook_time = webhook_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_seconds = (now - webhook_time).total_seconds()

        if age_seconds > _WEBHOOK_MAX_AGE_SECONDS:
            logger.warning(
                f"CISO-6: Webhook timestamp too old: {when_value} "
                f"(age: {age_seconds:.0f}s, max: {_WEBHOOK_MAX_AGE_SECONDS}s). "
                f"Possible replay attack."
            )
            return False

        if age_seconds < -60:
            # Timestamp is more than 60s in the future -- suspicious
            logger.warning(
                f"CISO-6: Webhook timestamp is in the future: {when_value} "
                f"(drift: {abs(age_seconds):.0f}s). Possible clock skew or tampering."
            )
            return False

        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"CISO-6: Could not parse webhook timestamp '{when_value}': {e}")
        # Reject unparseable timestamps in production, allow in dev
        return settings.debug


async def _check_dedup(message_id: str) -> bool:
    """Check if a message has already been processed.

    CISO-6: Uses Redis SET with TTL when available, falls back to
    in-process TTL-based LRU cache.

    Returns True if the message is a duplicate (already seen).
    """
    # Try Redis first for distributed deduplication
    try:
        from app.core.redis import get_async_redis

        redis = await get_async_redis()
        dedup_key = f"webhook:dedup:{message_id}"
        # SET with NX (only set if not exists) + EX (TTL)
        was_set = await redis.set(dedup_key, "1", nx=True, ex=_DEDUP_TTL_SECONDS)
        if was_set:
            # Key was newly set -- not a duplicate
            return False
        else:
            # Key already existed -- duplicate
            return True
    except Exception:
        # Redis unavailable -- fall back to in-process cache
        pass

    # Fallback: in-process TTL LRU cache
    if _dedup_cache.contains(message_id):
        return True

    _dedup_cache.add(message_id)
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
        "per Metriport spec -- heavy processing runs in background tasks. "
        "CISO-6: Includes HMAC signature verification, timestamp validation, "
        "deduplication, and rate monitoring."
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

    CISO-6 security checks (in order):
    1. HMAC signature verification
    2. Timestamp validation (replay protection)
    3. Rate monitoring
    4. Message deduplication
    """
    # CISO-6: Record webhook arrival for rate monitoring
    _rate_tracker.record()

    # Read raw body for signature verification
    body = await request.body()

    # CISO-6: Verify webhook signature (x-metriport-signature header, HMAC-SHA256)
    # In production, webhook_key is guaranteed to be set (config validation).
    # In development without a key, verification is skipped.
    webhook_key = settings.metriport_webhook_key
    if not _verify_webhook_signature(body, x_metriport_signature, webhook_key):
        logger.warning(
            "CISO-6: Metriport webhook signature verification failed "
            f"(key_configured={bool(webhook_key)})"
        )
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

    # CISO-6: Validate webhook timestamp (replay attack protection)
    if not _validate_webhook_timestamp(payload.meta.when):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook timestamp outside acceptable window",
        )

    # --- Message deduplication ---
    if await _check_dedup(message_id):
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

    # --- Unknown message type -- acknowledge anyway ---
    logger.warning(f"Unknown Metriport webhook type: {msg_type}")
    return Response(
        content=json.dumps(WebhookResponse(
            status="ok", message=f"Unknown type: {msg_type}"
        ).model_dump()),
        media_type="application/json",
        status_code=200,
    )
