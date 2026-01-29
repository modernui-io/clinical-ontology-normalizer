"""Notification API Endpoints.

Provides endpoints for notification management:
- GET /notifications - List user notifications
- POST /notifications/mark-read - Mark notifications as read
- GET /notifications/preferences - Get notification preferences
- PUT /notifications/preferences - Update notification preferences
- POST /webhooks - Create webhook endpoint
- GET /webhooks - List webhooks
- DELETE /webhooks/{id} - Delete webhook
- POST /webhooks/{id}/test - Test webhook
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.errors import log_and_raise_internal_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ============================================================================
# Request/Response Models
# ============================================================================


class NotificationChannelParam(str, Enum):
    """Notification channel options."""

    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationTypeParam(str, Enum):
    """Notification type options."""

    DRUG_INTERACTION = "drug_interaction"
    CODING_ERROR = "coding_error"
    CRITICAL_LAB = "critical_lab"
    SYSTEM_ERROR = "system_error"
    DOCUMENT_PROCESSED = "document_processed"
    EXPORT_READY = "export_ready"
    PATIENT_UPDATED = "patient_updated"
    JOB_COMPLETE = "job_complete"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_DIGEST = "weekly_digest"
    SECURITY_ALERT = "security_alert"
    MAINTENANCE = "maintenance"


class NotificationPriorityParam(str, Enum):
    """Notification priority options."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationItem(BaseModel):
    """A notification item in the list."""

    id: str = Field(..., description="Notification ID")
    type: str = Field(..., description="Notification type")
    subject: str = Field(..., description="Notification subject")
    body: str = Field(..., description="Notification body")
    priority: str = Field(..., description="Priority level")
    created_at: datetime = Field(..., description="Creation timestamp")
    read: bool = Field(default=False, description="Whether notification was read")
    read_at: datetime | None = Field(None, description="When notification was read")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class NotificationListResponse(BaseModel):
    """Response for notification list."""

    notifications: list[NotificationItem] = Field(..., description="List of notifications")
    total: int = Field(..., description="Total notification count")
    unread_count: int = Field(..., description="Number of unread notifications")


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read."""

    notification_ids: list[str] = Field(..., description="IDs of notifications to mark as read")


class MarkReadResponse(BaseModel):
    """Response from marking notifications as read."""

    marked_count: int = Field(..., description="Number of notifications marked as read")


class ChannelPreferences(BaseModel):
    """Channel-specific preferences."""

    slack: bool = Field(default=False, description="Slack notifications enabled")
    email: bool = Field(default=True, description="Email notifications enabled")
    webhook: bool = Field(default=False, description="Webhook notifications enabled")
    in_app: bool = Field(default=True, description="In-app notifications enabled")


class TypePreferences(BaseModel):
    """Type-specific preferences."""

    drug_interaction: bool = Field(default=True, description="Drug interaction alerts")
    coding_error: bool = Field(default=True, description="Coding error alerts")
    critical_lab: bool = Field(default=True, description="Critical lab alerts")
    document_processed: bool = Field(default=True, description="Document processed notifications")
    export_ready: bool = Field(default=True, description="Export ready notifications")
    daily_summary: bool = Field(default=False, description="Daily summary digest")
    security_alert: bool = Field(default=True, description="Security alerts")


class NotificationPreferences(BaseModel):
    """User notification preferences."""

    channels: ChannelPreferences = Field(default_factory=ChannelPreferences, description="Channel preferences")
    types: TypePreferences = Field(default_factory=TypePreferences, description="Type preferences")
    slack_webhook_url: str | None = Field(None, description="Slack webhook URL")
    email_address: str | None = Field(None, description="Email address for notifications")
    digest_frequency: str = Field(default="daily", description="Digest frequency: none, daily, weekly")
    quiet_hours_start: int | None = Field(None, ge=0, le=23, description="Quiet hours start (0-23)")
    quiet_hours_end: int | None = Field(None, ge=0, le=23, description="Quiet hours end (0-23)")


class WebhookCreate(BaseModel):
    """Request to create a webhook."""

    name: str = Field(..., min_length=1, max_length=100, description="Webhook name")
    url: str = Field(..., description="Webhook URL")
    event_types: list[NotificationTypeParam] = Field(..., min_length=1, description="Event types to trigger webhook")
    secret: str | None = Field(None, description="Signing secret for webhook")


class WebhookItem(BaseModel):
    """A webhook configuration."""

    id: str = Field(..., description="Webhook ID")
    name: str = Field(..., description="Webhook name")
    url: str = Field(..., description="Webhook URL")
    event_types: list[str] = Field(..., description="Event types")
    is_active: bool = Field(..., description="Whether webhook is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_triggered_at: datetime | None = Field(None, description="Last trigger timestamp")
    failure_count: int = Field(default=0, description="Recent failure count")


class WebhookListResponse(BaseModel):
    """Response for webhook list."""

    webhooks: list[WebhookItem] = Field(..., description="List of webhooks")
    total: int = Field(..., description="Total webhook count")


class WebhookTestResponse(BaseModel):
    """Response from webhook test."""

    success: bool = Field(..., description="Whether test succeeded")
    status_code: int | None = Field(None, description="HTTP status code")
    error_message: str | None = Field(None, description="Error message if failed")
    response_time_ms: float | None = Field(None, description="Response time in milliseconds")


class DeliveryLogItem(BaseModel):
    """A delivery log entry."""

    id: str = Field(..., description="Log ID")
    notification_id: str = Field(..., description="Notification ID")
    channel: str = Field(..., description="Delivery channel")
    status: str = Field(..., description="Delivery status")
    attempt: int = Field(..., description="Attempt number")
    timestamp: datetime = Field(..., description="Timestamp")
    error_message: str | None = Field(None, description="Error message if failed")
    response_code: int | None = Field(None, description="HTTP response code")


class DeliveryLogResponse(BaseModel):
    """Response for delivery logs."""

    logs: list[DeliveryLogItem] = Field(..., description="List of delivery logs")
    total: int = Field(..., description="Total log count")


class SendNotificationRequest(BaseModel):
    """Request to send a notification."""

    type: NotificationTypeParam = Field(..., description="Notification type")
    user_id: str = Field(..., description="Target user ID")
    channels: list[NotificationChannelParam] | None = Field(None, description="Override channels")
    variables: dict[str, Any] = Field(default_factory=dict, description="Template variables")


class SendNotificationResponse(BaseModel):
    """Response from sending a notification."""

    notification_id: str = Field(..., description="Created notification ID")
    channels_attempted: list[str] = Field(..., description="Channels attempted")
    success: bool = Field(..., description="Whether any delivery succeeded")


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
    description="Get notifications for the current user.",
)
async def list_notifications(
    user_id: str = Query("demo-user", description="User ID"),
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number to return"),
) -> NotificationListResponse:
    """List notifications for a user.

    Args:
        user_id: User ID
        unread_only: Only return unread notifications
        limit: Maximum number to return

    Returns:
        NotificationListResponse with notifications
    """
    try:
        from app.services.notification_service import get_notification_service

        service = get_notification_service()
        notifications = service.get_in_app_notifications(user_id, unread_only, limit)
        unread_count = service.get_unread_count(user_id)

        items = [
            NotificationItem(
                id=n.id,
                type=n.type.value,
                subject=n.subject,
                body=n.body,
                priority=n.priority.value,
                created_at=n.created_at,
                read=n.read,
                read_at=n.read_at,
                metadata=n.metadata,
            )
            for n in notifications
        ]

        return NotificationListResponse(
            notifications=items,
            total=len(items),
            unread_count=unread_count,
        )

    except Exception as e:
        # VP-Security-1: Sanitize error messages
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/notifications",
            user_message="Failed to list notifications",
        )


@router.post(
    "/mark-read",
    response_model=MarkReadResponse,
    summary="Mark notifications as read",
    description="Mark one or more notifications as read.",
)
async def mark_notifications_read(
    request: MarkReadRequest,
    user_id: str = Query("demo-user", description="User ID"),
) -> MarkReadResponse:
    """Mark notifications as read.

    Args:
        request: Mark read request with notification IDs
        user_id: User ID

    Returns:
        MarkReadResponse with count of marked notifications
    """
    try:
        from app.services.notification_service import get_notification_service

        service = get_notification_service()
        count = service.mark_notifications_read(user_id, request.notification_ids)

        return MarkReadResponse(marked_count=count)

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/notifications/mark-read",
            user_message="Failed to mark notifications",
        )


@router.get(
    "/preferences",
    response_model=NotificationPreferences,
    summary="Get notification preferences",
    description="Get notification preferences for the current user.",
)
async def get_notification_preferences(
    user_id: str = Query("demo-user", description="User ID"),
) -> NotificationPreferences:
    """Get notification preferences for a user.

    Args:
        user_id: User ID

    Returns:
        NotificationPreferences for the user
    """
    try:
        from app.services.notification_service import (
            NotificationChannel,
            NotificationType,
            get_notification_service,
        )

        service = get_notification_service()
        prefs = service.get_preferences(user_id)

        return NotificationPreferences(
            channels=ChannelPreferences(
                slack=prefs.channels_enabled.get(NotificationChannel.SLACK, False),
                email=prefs.channels_enabled.get(NotificationChannel.EMAIL, True),
                webhook=prefs.channels_enabled.get(NotificationChannel.WEBHOOK, False),
                in_app=prefs.channels_enabled.get(NotificationChannel.IN_APP, True),
            ),
            types=TypePreferences(
                drug_interaction=prefs.types_enabled.get(NotificationType.DRUG_INTERACTION, True),
                coding_error=prefs.types_enabled.get(NotificationType.CODING_ERROR, True),
                critical_lab=prefs.types_enabled.get(NotificationType.CRITICAL_LAB, True),
                document_processed=prefs.types_enabled.get(NotificationType.DOCUMENT_PROCESSED, True),
                export_ready=prefs.types_enabled.get(NotificationType.EXPORT_READY, True),
                daily_summary=prefs.types_enabled.get(NotificationType.DAILY_SUMMARY, False),
                security_alert=prefs.types_enabled.get(NotificationType.SECURITY_ALERT, True),
            ),
            slack_webhook_url=prefs.slack_webhook_url,
            email_address=prefs.email_address,
            digest_frequency=prefs.digest_frequency,
            quiet_hours_start=prefs.quiet_hours_start,
            quiet_hours_end=prefs.quiet_hours_end,
        )

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/notifications/preferences",
            user_message="Failed to get preferences",
        )


@router.put(
    "/preferences",
    response_model=NotificationPreferences,
    summary="Update notification preferences",
    description="Update notification preferences for the current user.",
)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    user_id: str = Query("demo-user", description="User ID"),
) -> NotificationPreferences:
    """Update notification preferences for a user.

    Args:
        preferences: New preferences
        user_id: User ID

    Returns:
        Updated NotificationPreferences
    """
    try:
        from app.services.notification_service import (
            NotificationChannel,
            NotificationType,
            UserNotificationPreferences,
            get_notification_service,
        )

        service = get_notification_service()

        # Convert to service preferences
        service_prefs = UserNotificationPreferences(
            user_id=user_id,
            channels_enabled={
                NotificationChannel.SLACK: preferences.channels.slack,
                NotificationChannel.EMAIL: preferences.channels.email,
                NotificationChannel.WEBHOOK: preferences.channels.webhook,
                NotificationChannel.IN_APP: preferences.channels.in_app,
            },
            types_enabled={
                NotificationType.DRUG_INTERACTION: preferences.types.drug_interaction,
                NotificationType.CODING_ERROR: preferences.types.coding_error,
                NotificationType.CRITICAL_LAB: preferences.types.critical_lab,
                NotificationType.DOCUMENT_PROCESSED: preferences.types.document_processed,
                NotificationType.EXPORT_READY: preferences.types.export_ready,
                NotificationType.DAILY_SUMMARY: preferences.types.daily_summary,
                NotificationType.SECURITY_ALERT: preferences.types.security_alert,
            },
            slack_webhook_url=preferences.slack_webhook_url,
            email_address=preferences.email_address,
            digest_frequency=preferences.digest_frequency,
            quiet_hours_start=preferences.quiet_hours_start,
            quiet_hours_end=preferences.quiet_hours_end,
        )

        service.update_preferences(user_id, service_prefs)

        return preferences

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/notifications/preferences",
            user_message="Failed to update preferences",
        )


@router.post(
    "/send",
    response_model=SendNotificationResponse,
    summary="Send a notification",
    description="Send a notification to a user using a template.",
)
async def send_notification(
    request: SendNotificationRequest,
) -> SendNotificationResponse:
    """Send a notification to a user.

    Args:
        request: Notification send request

    Returns:
        SendNotificationResponse with result
    """
    try:
        from app.services.notification_service import (
            NotificationChannel,
            NotificationType,
            get_notification_service,
        )

        service = get_notification_service()

        # Map type
        notification_type = NotificationType(request.type.value)

        # Map channels
        channels = None
        if request.channels:
            channels = [NotificationChannel(c.value) for c in request.channels]

        # Send notification
        notification = await service.send_notification(
            notification_type=notification_type,
            user_id=request.user_id,
            channels=channels,
            **request.variables,
        )

        return SendNotificationResponse(
            notification_id=notification.id,
            channels_attempted=[c.value for c in notification.channels],
            success=True,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/notifications/send",
            user_message="Failed to send notification",
        )


# ============================================================================
# Webhook Endpoints
# ============================================================================


@router.post(
    "/webhooks",
    response_model=WebhookItem,
    summary="Create webhook",
    description="Create a new webhook endpoint.",
)
async def create_webhook(
    request: WebhookCreate,
    user_id: str = Query("demo-user", description="User ID"),
) -> WebhookItem:
    """Create a new webhook.

    Args:
        request: Webhook creation request
        user_id: User ID

    Returns:
        Created WebhookItem
    """
    try:
        from app.services.notification_service import NotificationType, get_notification_service

        service = get_notification_service()

        event_types = [NotificationType(t.value) for t in request.event_types]

        webhook = service.create_webhook(
            user_id=user_id,
            name=request.name,
            url=request.url,
            event_types=event_types,
            secret=request.secret,
        )

        return WebhookItem(
            id=webhook.id,
            name=webhook.name,
            url=webhook.url,
            event_types=[t.value for t in webhook.event_types],
            is_active=webhook.is_active,
            created_at=webhook.created_at,
            last_triggered_at=webhook.last_triggered_at,
            failure_count=webhook.failure_count,
        )

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/webhooks",
            user_message="Failed to create webhook",
        )


@router.get(
    "/webhooks",
    response_model=WebhookListResponse,
    summary="List webhooks",
    description="List all webhooks for the current user.",
)
async def list_webhooks(
    user_id: str = Query("demo-user", description="User ID"),
) -> WebhookListResponse:
    """List webhooks for a user.

    Args:
        user_id: User ID

    Returns:
        WebhookListResponse with webhooks
    """
    try:
        from app.services.notification_service import get_notification_service

        service = get_notification_service()
        webhooks = service.get_webhooks(user_id)

        items = [
            WebhookItem(
                id=w.id,
                name=w.name,
                url=w.url,
                event_types=[t.value for t in w.event_types],
                is_active=w.is_active,
                created_at=w.created_at,
                last_triggered_at=w.last_triggered_at,
                failure_count=w.failure_count,
            )
            for w in webhooks
        ]

        return WebhookListResponse(
            webhooks=items,
            total=len(items),
        )

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/webhooks",
            user_message="Failed to list webhooks",
        )


@router.delete(
    "/webhooks/{webhook_id}",
    summary="Delete webhook",
    description="Delete a webhook endpoint.",
)
async def delete_webhook(
    webhook_id: str,
    user_id: str = Query("demo-user", description="User ID"),
) -> dict[str, str]:
    """Delete a webhook.

    Args:
        webhook_id: Webhook ID
        user_id: User ID

    Returns:
        Success message
    """
    try:
        from app.services.notification_service import get_notification_service

        service = get_notification_service()
        service.delete_webhook(webhook_id)

        return {"message": f"Webhook {webhook_id} deleted successfully"}

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/webhooks",
            user_message="Failed to delete webhook",
        )


@router.post(
    "/webhooks/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Test webhook",
    description="Send a test notification to a webhook.",
)
async def test_webhook(
    webhook_id: str,
    user_id: str = Query("demo-user", description="User ID"),
) -> WebhookTestResponse:
    """Test a webhook by sending a test notification.

    Args:
        webhook_id: Webhook ID
        user_id: User ID

    Returns:
        WebhookTestResponse with test result
    """
    try:
        import time

        from app.services.notification_service import DeliveryStatus, get_notification_service

        service = get_notification_service()

        start_time = time.perf_counter()
        log = await service.test_webhook(webhook_id)
        response_time_ms = (time.perf_counter() - start_time) * 1000

        return WebhookTestResponse(
            success=log.status == DeliveryStatus.DELIVERED,
            status_code=log.response_code,
            error_message=log.error_message,
            response_time_ms=round(response_time_ms, 2),
        )

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/webhooks/test",
            user_message="Failed to test webhook",
        )


@router.get(
    "/delivery-logs",
    response_model=DeliveryLogResponse,
    summary="Get delivery logs",
    description="Get notification delivery logs.",
)
async def get_delivery_logs(
    notification_id: str | None = Query(None, description="Filter by notification ID"),
    channel: NotificationChannelParam | None = Query(None, description="Filter by channel"),
    limit: int = Query(100, ge=1, le=500, description="Maximum logs to return"),
) -> DeliveryLogResponse:
    """Get delivery logs with optional filters.

    Args:
        notification_id: Filter by notification ID
        channel: Filter by channel
        limit: Maximum logs to return

    Returns:
        DeliveryLogResponse with logs
    """
    try:
        from app.services.notification_service import NotificationChannel, get_notification_service

        service = get_notification_service()

        channel_filter = None
        if channel:
            channel_filter = NotificationChannel(channel.value)

        logs = service.get_delivery_logs(
            notification_id=notification_id,
            channel=channel_filter,
            limit=limit,
        )

        items = [
            DeliveryLogItem(
                id=log.id,
                notification_id=log.notification_id,
                channel=log.channel.value,
                status=log.status.value,
                attempt=log.attempt,
                timestamp=log.timestamp,
                error_message=log.error_message,
                response_code=log.response_code,
            )
            for log in logs
        ]

        return DeliveryLogResponse(
            logs=items,
            total=len(items),
        )

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/webhooks/delivery-logs",
            user_message="Failed to get delivery logs",
        )


@router.get(
    "/stats",
    summary="Get notification service stats",
    description="Get statistics for the notification service.",
)
async def get_notification_stats() -> dict:
    """Get notification service statistics.

    Returns:
        Statistics dictionary
    """
    try:
        from app.services.notification_service import get_notification_service

        service = get_notification_service()
        return service.get_stats()

    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/notifications/stats",
            user_message="Failed to get stats",
        )
