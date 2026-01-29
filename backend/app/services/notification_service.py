"""Notification Service for Multi-Channel Delivery.

Provides centralized notification management with support for:
- Slack (webhook integration)
- Email (SMTP)
- Custom Webhooks
- In-app notifications

Features:
- Message templating system
- Delivery queue with retry logic
- Delivery logging and tracking
- User preference management
"""

import asyncio
import hashlib
import hmac
import json
import logging
import smtplib
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================


class NotificationDeliveryError(Exception):
    """VP-Reliability-2: Exception for critical notification delivery failures.

    Raised when a critical notification fails permanently after all retries.
    This allows callers to handle critical failures appropriately.
    """

    def __init__(
        self,
        notification_id: str,
        priority: "NotificationPriority",
        channel: "NotificationChannel",
        error_message: str,
        attempts: int,
    ):
        self.notification_id = notification_id
        self.priority = priority
        self.channel = channel
        self.error_message = error_message
        self.attempts = attempts
        super().__init__(
            f"Critical notification {notification_id} failed on {channel.value} "
            f"after {attempts} attempts: {error_message}"
        )


# ============================================================================
# Enums and Types
# ============================================================================


class NotificationChannel(str, Enum):
    """Supported notification channels."""

    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationType(str, Enum):
    """Types of notifications."""

    # Critical alerts
    DRUG_INTERACTION = "drug_interaction"
    CODING_ERROR = "coding_error"
    CRITICAL_LAB = "critical_lab"
    SYSTEM_ERROR = "system_error"

    # Informational
    DOCUMENT_PROCESSED = "document_processed"
    EXPORT_READY = "export_ready"
    PATIENT_UPDATED = "patient_updated"
    JOB_COMPLETE = "job_complete"

    # Digest
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_DIGEST = "weekly_digest"

    # System
    SECURITY_ALERT = "security_alert"
    MAINTENANCE = "maintenance"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryStatus(str, Enum):
    """Delivery status for notifications."""

    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class NotificationTemplate:
    """Template for notification messages."""

    type: NotificationType
    channels: list[NotificationChannel]
    subject: str
    body: str
    priority: NotificationPriority
    variables: list[str] = field(default_factory=list)

    def render(self, **kwargs: Any) -> tuple[str, str]:
        """Render the template with variables.

        Args:
            **kwargs: Template variables

        Returns:
            Tuple of (rendered_subject, rendered_body)
        """
        subject = self.subject
        body = self.body

        for key, value in kwargs.items():
            placeholder = f"{{{{{key}}}}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return subject, body


@dataclass
class Notification:
    """A notification to be delivered."""

    id: str
    type: NotificationType
    user_id: str | None
    channels: list[NotificationChannel]
    subject: str
    body: str
    priority: NotificationPriority
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    read: bool = False
    read_at: datetime | None = None


@dataclass
class DeliveryLog:
    """Log entry for notification delivery."""

    id: str
    notification_id: str
    channel: NotificationChannel
    status: DeliveryStatus
    attempt: int
    timestamp: datetime
    error_message: str | None = None
    response_code: int | None = None
    response_body: str | None = None


@dataclass
class WebhookConfig:
    """Configuration for a custom webhook."""

    id: str
    user_id: str
    name: str
    url: str
    secret: str | None
    event_types: list[NotificationType]
    is_active: bool
    created_at: datetime
    last_triggered_at: datetime | None = None
    failure_count: int = 0


@dataclass
class UserNotificationPreferences:
    """User preferences for notifications."""

    user_id: str
    channels_enabled: dict[NotificationChannel, bool]
    types_enabled: dict[NotificationType, bool]
    slack_webhook_url: str | None = None
    email_address: str | None = None
    digest_frequency: str = "daily"  # "none", "daily", "weekly"
    quiet_hours_start: int | None = None  # Hour (0-23)
    quiet_hours_end: int | None = None  # Hour (0-23)


# ============================================================================
# Default Templates
# ============================================================================


DEFAULT_TEMPLATES: dict[NotificationType, NotificationTemplate] = {
    NotificationType.DRUG_INTERACTION: NotificationTemplate(
        type=NotificationType.DRUG_INTERACTION,
        channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        subject="Critical: Drug Interaction Alert",
        body="Drug interaction detected between {{drug1}} and {{drug2}}. Severity: {{severity}}. Patient: {{patient_name}} ({{patient_id}}). Please review immediately.",
        priority=NotificationPriority.CRITICAL,
        variables=["drug1", "drug2", "severity", "patient_name", "patient_id"],
    ),
    NotificationType.CODING_ERROR: NotificationTemplate(
        type=NotificationType.CODING_ERROR,
        channels=[NotificationChannel.SLACK, NotificationChannel.IN_APP],
        subject="Coding Error Detected",
        body="A coding error was detected in document {{document_id}}. Error: {{error_description}}. Affected codes: {{codes}}.",
        priority=NotificationPriority.HIGH,
        variables=["document_id", "error_description", "codes"],
    ),
    NotificationType.CRITICAL_LAB: NotificationTemplate(
        type=NotificationType.CRITICAL_LAB,
        channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        subject="Critical Lab Value Alert",
        body="Critical lab value for {{patient_name}} ({{patient_id}}). {{lab_name}}: {{lab_value}} {{unit}} (Reference: {{reference_range}})",
        priority=NotificationPriority.CRITICAL,
        variables=["patient_name", "patient_id", "lab_name", "lab_value", "unit", "reference_range"],
    ),
    NotificationType.DOCUMENT_PROCESSED: NotificationTemplate(
        type=NotificationType.DOCUMENT_PROCESSED,
        channels=[NotificationChannel.IN_APP],
        subject="Document Processing Complete",
        body="Document '{{document_name}}' has been processed successfully. {{mention_count}} clinical mentions extracted, {{code_count}} codes suggested.",
        priority=NotificationPriority.LOW,
        variables=["document_name", "mention_count", "code_count"],
    ),
    NotificationType.EXPORT_READY: NotificationTemplate(
        type=NotificationType.EXPORT_READY,
        channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        subject="Export Ready for Download",
        body="Your export '{{export_name}}' is ready for download. Format: {{format}}. Size: {{file_size}}. The download link will expire in {{expiry_hours}} hours.",
        priority=NotificationPriority.MEDIUM,
        variables=["export_name", "format", "file_size", "expiry_hours"],
    ),
    NotificationType.JOB_COMPLETE: NotificationTemplate(
        type=NotificationType.JOB_COMPLETE,
        channels=[NotificationChannel.IN_APP],
        subject="Background Job Complete",
        body="Job '{{job_name}}' ({{job_id}}) completed with status: {{status}}. Duration: {{duration}}.",
        priority=NotificationPriority.LOW,
        variables=["job_name", "job_id", "status", "duration"],
    ),
    NotificationType.DAILY_SUMMARY: NotificationTemplate(
        type=NotificationType.DAILY_SUMMARY,
        channels=[NotificationChannel.EMAIL],
        subject="Daily Activity Summary - {{date}}",
        body="Here's your daily summary:\n\n- Documents processed: {{doc_count}}\n- Codes suggested: {{code_count}}\n- Alerts generated: {{alert_count}}\n\nTop activity areas: {{top_areas}}",
        priority=NotificationPriority.LOW,
        variables=["date", "doc_count", "code_count", "alert_count", "top_areas"],
    ),
    NotificationType.SECURITY_ALERT: NotificationTemplate(
        type=NotificationType.SECURITY_ALERT,
        channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        subject="Security Alert: {{alert_type}}",
        body="A security event was detected: {{description}}. Time: {{timestamp}}. IP Address: {{ip_address}}. Please review your account activity.",
        priority=NotificationPriority.HIGH,
        variables=["alert_type", "description", "timestamp", "ip_address"],
    ),
    NotificationType.SYSTEM_ERROR: NotificationTemplate(
        type=NotificationType.SYSTEM_ERROR,
        channels=[NotificationChannel.SLACK, NotificationChannel.IN_APP],
        subject="System Error Alert",
        body="A system error occurred: {{error_type}}. Details: {{error_message}}. Request ID: {{request_id}}.",
        priority=NotificationPriority.HIGH,
        variables=["error_type", "error_message", "request_id"],
    ),
}


# ============================================================================
# Channel Handlers
# ============================================================================


class ChannelHandler(ABC):
    """Abstract base class for notification channel handlers."""

    @abstractmethod
    async def send(
        self,
        notification: Notification,
        preferences: UserNotificationPreferences,
    ) -> DeliveryLog:
        """Send a notification through this channel.

        Args:
            notification: The notification to send
            preferences: User notification preferences

        Returns:
            DeliveryLog with delivery status
        """
        pass


class SlackHandler(ChannelHandler):
    """Handler for Slack webhook notifications."""

    async def send(
        self,
        notification: Notification,
        preferences: UserNotificationPreferences,
    ) -> DeliveryLog:
        """Send notification via Slack webhook."""
        log_id = str(uuid4())
        webhook_url = preferences.slack_webhook_url

        if not webhook_url:
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.SLACK,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message="No Slack webhook URL configured",
            )

        # Build Slack message payload
        color = self._get_priority_color(notification.priority)
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": notification.subject,
                    "text": notification.body,
                    "footer": "Clinical Ontology Normalizer",
                    "ts": int(notification.created_at.timestamp()),
                    "fields": [
                        {"title": "Priority", "value": notification.priority.value, "short": True},
                        {"title": "Type", "value": notification.type.value, "short": True},
                    ],
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(webhook_url, json=payload)

                if response.status_code == 200:
                    return DeliveryLog(
                        id=log_id,
                        notification_id=notification.id,
                        channel=NotificationChannel.SLACK,
                        status=DeliveryStatus.DELIVERED,
                        attempt=1,
                        timestamp=datetime.now(UTC),
                        response_code=response.status_code,
                    )
                else:
                    return DeliveryLog(
                        id=log_id,
                        notification_id=notification.id,
                        channel=NotificationChannel.SLACK,
                        status=DeliveryStatus.FAILED,
                        attempt=1,
                        timestamp=datetime.now(UTC),
                        error_message=f"Slack API returned {response.status_code}",
                        response_code=response.status_code,
                        response_body=response.text[:500],
                    )

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.SLACK,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message=str(e),
            )

    def _get_priority_color(self, priority: NotificationPriority) -> str:
        """Get Slack color for priority level."""
        colors = {
            NotificationPriority.LOW: "#36a64f",      # Green
            NotificationPriority.MEDIUM: "#2196F3",   # Blue
            NotificationPriority.HIGH: "#ff9800",     # Orange
            NotificationPriority.CRITICAL: "#f44336", # Red
        }
        return colors.get(priority, "#808080")


class EmailHandler(ChannelHandler):
    """Handler for email notifications."""

    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_address: str = "notifications@clinicalont.local",
        use_tls: bool = True,
    ):
        """Initialize email handler.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_address: Sender email address
            use_tls: Whether to use TLS
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.use_tls = use_tls

    async def send(
        self,
        notification: Notification,
        preferences: UserNotificationPreferences,
    ) -> DeliveryLog:
        """Send notification via email."""
        log_id = str(uuid4())
        to_address = preferences.email_address

        if not to_address:
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message="No email address configured",
            )

        try:
            # Build email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = notification.subject
            msg["From"] = self.from_address
            msg["To"] = to_address

            # Plain text version
            text_content = notification.body

            # HTML version
            html_content = self._build_html_email(notification)

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Send email (run in thread pool to avoid blocking)
            # VP-Deprecation-3: Use asyncio.to_thread() instead of deprecated get_event_loop()
            await asyncio.to_thread(self._send_smtp, msg, to_address)

            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.DELIVERED,
                attempt=1,
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message=str(e),
            )

    def _send_smtp(self, msg: MIMEMultipart, to_address: str) -> None:
        """Send email via SMTP (blocking)."""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.from_address, to_address, msg.as_string())

    def _build_html_email(self, notification: Notification) -> str:
        """Build HTML email content."""
        priority_color = {
            NotificationPriority.LOW: "#36a64f",
            NotificationPriority.MEDIUM: "#2196F3",
            NotificationPriority.HIGH: "#ff9800",
            NotificationPriority.CRITICAL: "#f44336",
        }.get(notification.priority, "#808080")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {priority_color}; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; }}
                .footer {{ text-align: center; padding: 15px; color: #666; font-size: 12px; }}
                .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; background-color: {priority_color}; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0;">{notification.subject}</h2>
                </div>
                <div class="content">
                    <p>{notification.body.replace(chr(10), '<br>')}</p>
                    <p><span class="badge">{notification.priority.value.upper()}</span></p>
                </div>
                <div class="footer">
                    <p>Clinical Ontology Normalizer</p>
                    <p>{notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """


class WebhookHandler(ChannelHandler):
    """Handler for custom webhook notifications."""

    def __init__(self, webhook_configs: list[WebhookConfig] | None = None):
        """Initialize webhook handler.

        Args:
            webhook_configs: List of webhook configurations
        """
        self._webhooks: dict[str, WebhookConfig] = {}
        if webhook_configs:
            for config in webhook_configs:
                self._webhooks[config.id] = config

    def add_webhook(self, config: WebhookConfig) -> None:
        """Add a webhook configuration."""
        self._webhooks[config.id] = config

    def remove_webhook(self, webhook_id: str) -> None:
        """Remove a webhook configuration."""
        self._webhooks.pop(webhook_id, None)

    def get_webhooks_for_user(self, user_id: str) -> list[WebhookConfig]:
        """Get all webhooks for a user."""
        return [w for w in self._webhooks.values() if w.user_id == user_id and w.is_active]

    async def send(
        self,
        notification: Notification,
        preferences: UserNotificationPreferences,
    ) -> DeliveryLog:
        """Send notification to all matching webhooks."""
        log_id = str(uuid4())

        # Get webhooks for user that match notification type
        webhooks = [
            w for w in self.get_webhooks_for_user(preferences.user_id)
            if notification.type in w.event_types
        ]

        if not webhooks:
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.WEBHOOK,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message="No matching webhooks configured",
            )

        # Send to all matching webhooks
        success_count = 0
        errors = []

        for webhook in webhooks:
            try:
                await self._send_to_webhook(notification, webhook)
                success_count += 1
            except Exception as e:
                errors.append(f"{webhook.name}: {str(e)}")

        if success_count == len(webhooks):
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.WEBHOOK,
                status=DeliveryStatus.DELIVERED,
                attempt=1,
                timestamp=datetime.now(UTC),
            )
        elif success_count > 0:
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.WEBHOOK,
                status=DeliveryStatus.DELIVERED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message=f"Partial delivery: {success_count}/{len(webhooks)}. Errors: {'; '.join(errors)}",
            )
        else:
            return DeliveryLog(
                id=log_id,
                notification_id=notification.id,
                channel=NotificationChannel.WEBHOOK,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message="; ".join(errors),
            )

    async def _send_to_webhook(self, notification: Notification, webhook: WebhookConfig) -> None:
        """Send notification to a specific webhook."""
        payload = {
            "event_type": notification.type.value,
            "notification_id": notification.id,
            "subject": notification.subject,
            "body": notification.body,
            "priority": notification.priority.value,
            "timestamp": notification.created_at.isoformat(),
            "metadata": notification.metadata,
        }

        headers = {"Content-Type": "application/json"}

        # Add signature if secret is configured
        if webhook.secret:
            payload_str = json.dumps(payload, sort_keys=True)
            signature = hmac.new(
                webhook.secret.encode(),
                payload_str.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook.url, json=payload, headers=headers)
            response.raise_for_status()


class InAppHandler(ChannelHandler):
    """Handler for in-app notifications."""

    def __init__(self):
        """Initialize in-app handler."""
        self._notifications: dict[str, list[Notification]] = {}  # user_id -> notifications
        self._lock = threading.Lock()

    async def send(
        self,
        notification: Notification,
        preferences: UserNotificationPreferences,
    ) -> DeliveryLog:
        """Store notification for in-app display."""
        log_id = str(uuid4())

        with self._lock:
            user_id = preferences.user_id
            if user_id not in self._notifications:
                self._notifications[user_id] = []

            self._notifications[user_id].append(notification)

            # Keep only last 100 notifications per user
            if len(self._notifications[user_id]) > 100:
                self._notifications[user_id] = self._notifications[user_id][-100:]

        return DeliveryLog(
            id=log_id,
            notification_id=notification.id,
            channel=NotificationChannel.IN_APP,
            status=DeliveryStatus.DELIVERED,
            attempt=1,
            timestamp=datetime.now(UTC),
        )

    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        """Get notifications for a user.

        Args:
            user_id: User ID
            unread_only: Only return unread notifications
            limit: Maximum number to return

        Returns:
            List of notifications
        """
        with self._lock:
            notifications = self._notifications.get(user_id, [])
            if unread_only:
                notifications = [n for n in notifications if not n.read]
            return list(reversed(notifications[-limit:]))

    def mark_as_read(self, user_id: str, notification_ids: list[str]) -> int:
        """Mark notifications as read.

        Args:
            user_id: User ID
            notification_ids: List of notification IDs to mark as read

        Returns:
            Number of notifications marked as read
        """
        count = 0
        with self._lock:
            notifications = self._notifications.get(user_id, [])
            for notification in notifications:
                if notification.id in notification_ids and not notification.read:
                    notification.read = True
                    notification.read_at = datetime.now(UTC)
                    count += 1
        return count

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications."""
        with self._lock:
            notifications = self._notifications.get(user_id, [])
            return sum(1 for n in notifications if not n.read)


# ============================================================================
# Delivery Queue
# ============================================================================


@dataclass
class QueuedDelivery:
    """A queued notification delivery."""

    notification: Notification
    channel: NotificationChannel
    preferences: UserNotificationPreferences
    attempt: int = 1
    next_retry_at: datetime | None = None


@dataclass
class DeadLetterEntry:
    """VP-Reliability-2: Entry in the dead letter queue for failed critical notifications."""

    id: str
    notification: Notification
    channel: NotificationChannel
    final_error: str
    attempts: int
    failed_at: datetime
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None


class DeliveryQueue:
    """Queue for notification deliveries with retry logic."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: float = 30.0,
        retry_backoff_multiplier: float = 2.0,
    ):
        """Initialize delivery queue.

        Args:
            max_retries: Maximum retry attempts
            retry_delay_seconds: Initial retry delay
            retry_backoff_multiplier: Backoff multiplier for retries
        """
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_backoff_multiplier = retry_backoff_multiplier

        self._queue: list[QueuedDelivery] = []
        self._lock = threading.Lock()
        self._processing = False

    def enqueue(
        self,
        notification: Notification,
        channel: NotificationChannel,
        preferences: UserNotificationPreferences,
    ) -> None:
        """Add a delivery to the queue."""
        with self._lock:
            self._queue.append(QueuedDelivery(
                notification=notification,
                channel=channel,
                preferences=preferences,
            ))

    def requeue_for_retry(self, delivery: QueuedDelivery) -> bool:
        """Requeue a failed delivery for retry.

        Args:
            delivery: The failed delivery

        Returns:
            True if requeued, False if max retries exceeded
        """
        if delivery.attempt >= self.max_retries:
            return False

        delay = self.retry_delay_seconds * (self.retry_backoff_multiplier ** delivery.attempt)
        delivery.attempt += 1
        delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)

        with self._lock:
            self._queue.append(delivery)

        return True

    def get_ready_deliveries(self, max_count: int = 10) -> list[QueuedDelivery]:
        """Get deliveries ready for processing.

        Args:
            max_count: Maximum number to return

        Returns:
            List of ready deliveries
        """
        now = datetime.now(UTC)
        ready = []

        with self._lock:
            remaining = []
            for delivery in self._queue:
                if len(ready) < max_count:
                    if delivery.next_retry_at is None or delivery.next_retry_at <= now:
                        ready.append(delivery)
                    else:
                        remaining.append(delivery)
                else:
                    remaining.append(delivery)
            self._queue = remaining

        return ready

    def get_queue_size(self) -> int:
        """Get current queue size."""
        with self._lock:
            return len(self._queue)


# ============================================================================
# Dead Letter Queue
# ============================================================================


class DeadLetterQueue:
    """VP-Reliability-2: Dead letter queue for permanently failed notifications.

    Stores notifications that failed all retry attempts for manual review
    and reprocessing. Critical for ensuring no important notifications are lost.
    """

    def __init__(self, max_entries: int = 1000):
        """Initialize dead letter queue.

        Args:
            max_entries: Maximum entries to retain
        """
        self._entries: list[DeadLetterEntry] = []
        self._lock = threading.Lock()
        self._max_entries = max_entries

    def add(
        self,
        notification: Notification,
        channel: NotificationChannel,
        error_message: str,
        attempts: int,
    ) -> DeadLetterEntry:
        """Add a failed notification to the dead letter queue.

        VP-Reliability-2: Log structured errors with priority context.
        """
        entry = DeadLetterEntry(
            id=str(uuid4()),
            notification=notification,
            channel=channel,
            final_error=error_message,
            attempts=attempts,
            failed_at=datetime.now(UTC),
        )

        # VP-Reliability-2: Structured logging with priority
        logger.error(
            "Notification permanently failed",
            extra={
                "notification_id": notification.id,
                "notification_type": notification.type.value,
                "priority": notification.priority.value,
                "channel": channel.value,
                "attempts": attempts,
                "error": error_message,
                "user_id": notification.user_id,
                "dlq_entry_id": entry.id,
            },
        )

        with self._lock:
            self._entries.append(entry)
            # Prune old entries if over limit (keep most recent)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

        return entry

    def get_entries(
        self,
        unacknowledged_only: bool = False,
        priority: NotificationPriority | None = None,
        limit: int = 100,
    ) -> list[DeadLetterEntry]:
        """Get dead letter queue entries.

        Args:
            unacknowledged_only: Only return unacknowledged entries
            priority: Filter by notification priority
            limit: Maximum entries to return

        Returns:
            List of dead letter entries
        """
        with self._lock:
            entries = self._entries.copy()

        if unacknowledged_only:
            entries = [e for e in entries if not e.acknowledged]
        if priority:
            entries = [e for e in entries if e.notification.priority == priority]

        return list(reversed(entries[-limit:]))

    def acknowledge(self, entry_id: str, acknowledged_by: str) -> bool:
        """Acknowledge a dead letter entry.

        Args:
            entry_id: Entry ID to acknowledge
            acknowledged_by: User/system acknowledging the entry

        Returns:
            True if acknowledged, False if not found
        """
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id and not entry.acknowledged:
                    entry.acknowledged = True
                    entry.acknowledged_at = datetime.now(UTC)
                    entry.acknowledged_by = acknowledged_by
                    logger.info(
                        f"DLQ entry {entry_id} acknowledged by {acknowledged_by}"
                    )
                    return True
        return False

    def get_critical_unacknowledged_count(self) -> int:
        """Get count of unacknowledged critical notifications."""
        with self._lock:
            return sum(
                1 for e in self._entries
                if not e.acknowledged
                and e.notification.priority == NotificationPriority.CRITICAL
            )

    def get_stats(self) -> dict[str, Any]:
        """Get dead letter queue statistics."""
        with self._lock:
            total = len(self._entries)
            unacknowledged = sum(1 for e in self._entries if not e.acknowledged)
            by_priority = {}
            for entry in self._entries:
                p = entry.notification.priority.value
                by_priority[p] = by_priority.get(p, 0) + 1

        return {
            "total_entries": total,
            "unacknowledged": unacknowledged,
            "by_priority": by_priority,
        }


# ============================================================================
# Main Notification Service
# ============================================================================


class NotificationService:
    """Centralized notification service.

    Provides multi-channel notification delivery with:
    - Template-based messages
    - User preferences
    - Delivery queue with retry
    - Delivery logging
    """

    def __init__(self):
        """Initialize notification service."""
        # Channel handlers
        self._slack_handler = SlackHandler()
        self._email_handler = EmailHandler(
            smtp_host=getattr(settings, "smtp_host", "localhost"),
            smtp_port=getattr(settings, "smtp_port", 587),
            smtp_user=getattr(settings, "smtp_user", None),
            smtp_password=getattr(settings, "smtp_password", None),
            from_address=getattr(settings, "notification_from_email", "notifications@clinicalont.local"),
        )
        self._webhook_handler = WebhookHandler()
        self._in_app_handler = InAppHandler()

        # Delivery queue
        self._queue = DeliveryQueue()

        # VP-Reliability-2: Dead letter queue for permanently failed notifications
        self._dead_letter_queue = DeadLetterQueue()

        # User preferences cache
        self._preferences: dict[str, UserNotificationPreferences] = {}

        # Delivery logs
        self._delivery_logs: list[DeliveryLog] = []
        self._log_lock = threading.Lock()

        # Templates
        self._templates = DEFAULT_TEMPLATES.copy()

        # Statistics
        self._total_sent = 0
        self._total_failed = 0

        logger.info("NotificationService initialized")

    def _get_handler(self, channel: NotificationChannel) -> ChannelHandler:
        """Get handler for a channel."""
        handlers = {
            NotificationChannel.SLACK: self._slack_handler,
            NotificationChannel.EMAIL: self._email_handler,
            NotificationChannel.WEBHOOK: self._webhook_handler,
            NotificationChannel.IN_APP: self._in_app_handler,
        }
        return handlers[channel]

    # ========================================================================
    # Preferences Management
    # ========================================================================

    def get_preferences(self, user_id: str) -> UserNotificationPreferences:
        """Get notification preferences for a user.

        Args:
            user_id: User ID

        Returns:
            User's notification preferences
        """
        if user_id not in self._preferences:
            # Return default preferences
            self._preferences[user_id] = UserNotificationPreferences(
                user_id=user_id,
                channels_enabled={
                    NotificationChannel.SLACK: False,
                    NotificationChannel.EMAIL: True,
                    NotificationChannel.WEBHOOK: False,
                    NotificationChannel.IN_APP: True,
                },
                types_enabled={t: True for t in NotificationType},
            )
        return self._preferences[user_id]

    def update_preferences(
        self,
        user_id: str,
        preferences: UserNotificationPreferences,
    ) -> None:
        """Update notification preferences for a user.

        Args:
            user_id: User ID
            preferences: New preferences
        """
        self._preferences[user_id] = preferences

    # ========================================================================
    # Webhook Management
    # ========================================================================

    def create_webhook(
        self,
        user_id: str,
        name: str,
        url: str,
        event_types: list[NotificationType],
        secret: str | None = None,
    ) -> WebhookConfig:
        """Create a new webhook configuration.

        Args:
            user_id: User ID
            name: Webhook name
            url: Webhook URL
            event_types: Event types to trigger webhook
            secret: Optional signing secret

        Returns:
            Created webhook configuration
        """
        config = WebhookConfig(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            url=url,
            secret=secret,
            event_types=event_types,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self._webhook_handler.add_webhook(config)
        return config

    def get_webhooks(self, user_id: str) -> list[WebhookConfig]:
        """Get all webhooks for a user."""
        return self._webhook_handler.get_webhooks_for_user(user_id)

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook."""
        self._webhook_handler.remove_webhook(webhook_id)

    async def test_webhook(self, webhook_id: str) -> DeliveryLog:
        """Test a webhook by sending a test notification.

        Args:
            webhook_id: Webhook ID to test

        Returns:
            DeliveryLog with test result
        """
        webhook = self._webhook_handler._webhooks.get(webhook_id)
        if not webhook:
            return DeliveryLog(
                id=str(uuid4()),
                notification_id="test",
                channel=NotificationChannel.WEBHOOK,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message="Webhook not found",
            )

        test_notification = Notification(
            id=str(uuid4()),
            type=NotificationType.MAINTENANCE,
            user_id=webhook.user_id,
            channels=[NotificationChannel.WEBHOOK],
            subject="Test Notification",
            body="This is a test notification to verify your webhook configuration.",
            priority=NotificationPriority.LOW,
            created_at=datetime.now(UTC),
            metadata={"test": True},
        )

        try:
            await self._webhook_handler._send_to_webhook(test_notification, webhook)
            return DeliveryLog(
                id=str(uuid4()),
                notification_id=test_notification.id,
                channel=NotificationChannel.WEBHOOK,
                status=DeliveryStatus.DELIVERED,
                attempt=1,
                timestamp=datetime.now(UTC),
            )
        except Exception as e:
            return DeliveryLog(
                id=str(uuid4()),
                notification_id=test_notification.id,
                channel=NotificationChannel.WEBHOOK,
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=datetime.now(UTC),
                error_message=str(e),
            )

    # ========================================================================
    # Notification Sending
    # ========================================================================

    async def send_notification(
        self,
        notification_type: NotificationType,
        user_id: str,
        channels: list[NotificationChannel] | None = None,
        **template_vars: Any,
    ) -> Notification:
        """Send a notification using a template.

        Args:
            notification_type: Type of notification
            user_id: Target user ID
            channels: Override channels (uses template defaults if None)
            **template_vars: Variables for template rendering

        Returns:
            The created notification
        """
        template = self._templates.get(notification_type)
        if not template:
            raise ValueError(f"No template found for notification type: {notification_type}")

        subject, body = template.render(**template_vars)
        use_channels = channels or template.channels

        notification = Notification(
            id=str(uuid4()),
            type=notification_type,
            user_id=user_id,
            channels=use_channels,
            subject=subject,
            body=body,
            priority=template.priority,
            created_at=datetime.now(UTC),
            metadata=template_vars,
        )

        await self._deliver_notification(notification)
        return notification

    async def send_custom_notification(
        self,
        user_id: str,
        subject: str,
        body: str,
        channels: list[NotificationChannel],
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        notification_type: NotificationType = NotificationType.MAINTENANCE,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        """Send a custom notification without a template.

        Args:
            user_id: Target user ID
            subject: Notification subject
            body: Notification body
            channels: Delivery channels
            priority: Priority level
            notification_type: Type of notification
            metadata: Additional metadata

        Returns:
            The created notification
        """
        notification = Notification(
            id=str(uuid4()),
            type=notification_type,
            user_id=user_id,
            channels=channels,
            subject=subject,
            body=body,
            priority=priority,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )

        await self._deliver_notification(notification)
        return notification

    async def _deliver_notification(self, notification: Notification) -> list[DeliveryLog]:
        """Deliver notification to all channels.

        Args:
            notification: Notification to deliver

        Returns:
            List of delivery logs
        """
        preferences = self.get_preferences(notification.user_id or "anonymous")
        logs = []

        for channel in notification.channels:
            # Check if channel is enabled for user
            if not preferences.channels_enabled.get(channel, True):
                continue

            # Check if notification type is enabled
            if not preferences.types_enabled.get(notification.type, True):
                continue

            # Check quiet hours
            if self._is_quiet_hours(preferences) and notification.priority != NotificationPriority.CRITICAL:
                continue

            handler = self._get_handler(channel)
            log = await handler.send(notification, preferences)
            logs.append(log)

            # Record log
            with self._log_lock:
                self._delivery_logs.append(log)
                if len(self._delivery_logs) > 10000:
                    self._delivery_logs = self._delivery_logs[-5000:]

            # Update statistics
            if log.status == DeliveryStatus.DELIVERED:
                self._total_sent += 1
            elif log.status == DeliveryStatus.FAILED:
                self._total_failed += 1
                # Queue for retry
                self._queue.enqueue(notification, channel, preferences)

        return logs

    def _is_quiet_hours(self, preferences: UserNotificationPreferences) -> bool:
        """Check if current time is within user's quiet hours."""
        if preferences.quiet_hours_start is None or preferences.quiet_hours_end is None:
            return False

        current_hour = datetime.now(UTC).hour

        start = preferences.quiet_hours_start
        end = preferences.quiet_hours_end

        if start <= end:
            return start <= current_hour < end
        else:
            # Wraps around midnight
            return current_hour >= start or current_hour < end

    # ========================================================================
    # In-App Notifications
    # ========================================================================

    def get_in_app_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        """Get in-app notifications for a user."""
        return self._in_app_handler.get_notifications(user_id, unread_only, limit)

    def mark_notifications_read(self, user_id: str, notification_ids: list[str]) -> int:
        """Mark notifications as read."""
        return self._in_app_handler.mark_as_read(user_id, notification_ids)

    def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count for a user."""
        return self._in_app_handler.get_unread_count(user_id)

    # ========================================================================
    # Delivery Logs
    # ========================================================================

    def get_delivery_logs(
        self,
        notification_id: str | None = None,
        channel: NotificationChannel | None = None,
        status: DeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[DeliveryLog]:
        """Get delivery logs with optional filters.

        Args:
            notification_id: Filter by notification ID
            channel: Filter by channel
            status: Filter by status
            limit: Maximum number to return

        Returns:
            List of delivery logs
        """
        with self._log_lock:
            logs = self._delivery_logs.copy()

        if notification_id:
            logs = [l for l in logs if l.notification_id == notification_id]
        if channel:
            logs = [l for l in logs if l.channel == channel]
        if status:
            logs = [l for l in logs if l.status == status]

        return list(reversed(logs[-limit:]))

    # ========================================================================
    # Queue Processing
    # ========================================================================

    async def process_queue(self, raise_on_critical_failure: bool = False) -> int:
        """Process pending deliveries in the queue.

        VP-Reliability-2: Enhanced error handling for critical notifications.

        Args:
            raise_on_critical_failure: If True, raise NotificationDeliveryError
                when a critical notification fails permanently.

        Returns:
            Number of deliveries processed

        Raises:
            NotificationDeliveryError: If raise_on_critical_failure is True and
                a critical notification fails permanently.
        """
        deliveries = self._queue.get_ready_deliveries()
        processed = 0
        critical_failures: list[NotificationDeliveryError] = []

        for delivery in deliveries:
            handler = self._get_handler(delivery.channel)
            log = await handler.send(delivery.notification, delivery.preferences)

            # Record log
            with self._log_lock:
                self._delivery_logs.append(log)

            if log.status == DeliveryStatus.DELIVERED:
                self._total_sent += 1
                processed += 1
            elif log.status == DeliveryStatus.FAILED:
                # Try to requeue
                if not self._queue.requeue_for_retry(delivery):
                    self._total_failed += 1

                    # VP-Reliability-2: Add to dead letter queue
                    dlq_entry = self._dead_letter_queue.add(
                        notification=delivery.notification,
                        channel=delivery.channel,
                        error_message=log.error_message or "Unknown error",
                        attempts=delivery.attempt,
                    )

                    # VP-Reliability-2: Escalate critical notification failures
                    if delivery.notification.priority in (
                        NotificationPriority.CRITICAL,
                        NotificationPriority.HIGH,
                    ):
                        error = NotificationDeliveryError(
                            notification_id=delivery.notification.id,
                            priority=delivery.notification.priority,
                            channel=delivery.channel,
                            error_message=log.error_message or "Unknown error",
                            attempts=delivery.attempt,
                        )

                        # Log at ERROR level for critical, WARN for high
                        if delivery.notification.priority == NotificationPriority.CRITICAL:
                            logger.error(
                                f"CRITICAL notification {delivery.notification.id} "
                                f"permanently failed on {delivery.channel.value}! "
                                f"DLQ entry: {dlq_entry.id}. Immediate attention required.",
                                extra={
                                    "alert": "critical_notification_failure",
                                    "dlq_entry_id": dlq_entry.id,
                                    "notification_type": delivery.notification.type.value,
                                    "user_id": delivery.notification.user_id,
                                },
                            )
                            critical_failures.append(error)
                        else:
                            logger.warning(
                                f"HIGH priority notification {delivery.notification.id} "
                                f"permanently failed on {delivery.channel.value}. "
                                f"DLQ entry: {dlq_entry.id}"
                            )

        # VP-Reliability-2: Optionally raise on critical failures
        if raise_on_critical_failure and critical_failures:
            raise critical_failures[0]

        return processed

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get notification service statistics."""
        return {
            "service": "NotificationService",
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "queue_size": self._queue.get_queue_size(),
            "delivery_log_count": len(self._delivery_logs),
            "user_preferences_count": len(self._preferences),
            "webhook_count": len(self._webhook_handler._webhooks),
            "template_count": len(self._templates),
            # VP-Reliability-2: Include DLQ stats
            "dead_letter_queue": self._dead_letter_queue.get_stats(),
        }

    # ========================================================================
    # Dead Letter Queue Access (VP-Reliability-2)
    # ========================================================================

    def get_dead_letter_entries(
        self,
        unacknowledged_only: bool = False,
        priority: NotificationPriority | None = None,
        limit: int = 100,
    ) -> list[DeadLetterEntry]:
        """Get dead letter queue entries.

        VP-Reliability-2: Access failed notifications for review.

        Args:
            unacknowledged_only: Only return unacknowledged entries
            priority: Filter by notification priority
            limit: Maximum entries to return

        Returns:
            List of dead letter entries
        """
        return self._dead_letter_queue.get_entries(
            unacknowledged_only=unacknowledged_only,
            priority=priority,
            limit=limit,
        )

    def acknowledge_dead_letter(self, entry_id: str, acknowledged_by: str) -> bool:
        """Acknowledge a dead letter entry.

        VP-Reliability-2: Mark a failed notification as reviewed.

        Args:
            entry_id: Entry ID to acknowledge
            acknowledged_by: User/system acknowledging

        Returns:
            True if acknowledged, False if not found
        """
        return self._dead_letter_queue.acknowledge(entry_id, acknowledged_by)

    def get_critical_failure_count(self) -> int:
        """Get count of unacknowledged critical notification failures.

        VP-Reliability-2: Quick check for critical issues needing attention.
        """
        return self._dead_letter_queue.get_critical_unacknowledged_count()

    async def retry_dead_letter(self, entry_id: str) -> bool:
        """Retry a dead letter notification.

        VP-Reliability-2: Attempt to resend a failed notification.

        Args:
            entry_id: Dead letter entry ID to retry

        Returns:
            True if retry queued, False if not found
        """
        entries = self._dead_letter_queue.get_entries(limit=1000)
        for entry in entries:
            if entry.id == entry_id:
                # Re-queue the notification
                preferences = self.get_preferences(
                    entry.notification.user_id or "anonymous"
                )
                self._queue.enqueue(
                    entry.notification,
                    entry.channel,
                    preferences,
                )
                logger.info(f"DLQ entry {entry_id} queued for retry")
                return True
        return False


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: NotificationService | None = None
_service_lock = threading.Lock()


def get_notification_service() -> NotificationService:
    """Get or create the singleton notification service instance.

    Returns:
        NotificationService singleton instance
    """
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = NotificationService()

    return _service_instance


def reset_notification_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
