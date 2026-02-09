"""Pydantic schemas for Threat Intelligence & DLP Policies.

CISO-13: Threat intelligence feed management, indicator of compromise (IOC)
tracking, data loss prevention policies, violation monitoring, and security
awareness training for the clinical trial patient recruitment platform.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ThreatCategory(str, Enum):
    """Classification of threat types."""

    APT = "APT"
    RANSOMWARE = "RANSOMWARE"
    PHISHING = "PHISHING"
    INSIDER = "INSIDER"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    ZERO_DAY = "ZERO_DAY"
    CREDENTIAL_STUFFING = "CREDENTIAL_STUFFING"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    DDOS = "DDOS"
    SOCIAL_ENGINEERING = "SOCIAL_ENGINEERING"


class ThreatSeverity(str, Enum):
    """Severity level for threat indicators and alerts."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class ThreatStatus(str, Enum):
    """Lifecycle status of a threat indicator or alert."""

    NEW = "NEW"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    CONFIRMED = "CONFIRMED"
    MITIGATED = "MITIGATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ARCHIVED = "ARCHIVED"


class IOCType(str, Enum):
    """Indicator of compromise type."""

    IP_ADDRESS = "IP_ADDRESS"
    DOMAIN = "DOMAIN"
    URL = "URL"
    FILE_HASH_MD5 = "FILE_HASH_MD5"
    FILE_HASH_SHA256 = "FILE_HASH_SHA256"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    CVE_ID = "CVE_ID"
    REGISTRY_KEY = "REGISTRY_KEY"
    USER_AGENT = "USER_AGENT"


class DLPPolicyType(str, Enum):
    """Classification of DLP policy types."""

    PHI_DETECTION = "PHI_DETECTION"
    PII_DETECTION = "PII_DETECTION"
    CREDENTIAL_DETECTION = "CREDENTIAL_DETECTION"
    SOURCE_CODE = "SOURCE_CODE"
    FINANCIAL_DATA = "FINANCIAL_DATA"
    INTELLECTUAL_PROPERTY = "INTELLECTUAL_PROPERTY"


class DLPAction(str, Enum):
    """Action to take when a DLP policy is triggered."""

    BLOCK = "BLOCK"
    ALERT = "ALERT"
    ENCRYPT = "ENCRYPT"
    QUARANTINE = "QUARANTINE"
    LOG_ONLY = "LOG_ONLY"
    REDACT = "REDACT"


class DLPChannel(str, Enum):
    """Communication channel monitored by DLP."""

    EMAIL = "EMAIL"
    WEB_UPLOAD = "WEB_UPLOAD"
    USB_TRANSFER = "USB_TRANSFER"
    CLOUD_STORAGE = "CLOUD_STORAGE"
    API_ENDPOINT = "API_ENDPOINT"
    PRINT = "PRINT"
    CLIPBOARD = "CLIPBOARD"


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class ThreatIndicator(BaseModel):
    """An indicator of compromise (IOC) tracked by the threat intelligence system."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique indicator identifier")
    ioc_type: IOCType = Field(..., description="Type of IOC")
    value: str = Field(..., description="IOC value (IP, domain, hash, etc.)")
    threat_category: ThreatCategory = Field(..., description="Threat classification")
    severity: ThreatSeverity = Field(..., description="Severity level")
    description: str = Field(default="", description="Human-readable description")
    source: str = Field(default="", description="Intelligence source or feed")
    first_seen: datetime = Field(..., description="When the IOC was first observed")
    last_seen: datetime = Field(..., description="When the IOC was most recently observed")
    confidence_score: float = Field(
        ..., ge=0.0, le=100.0, description="Confidence score (0-100)"
    )
    related_campaigns: list[str] = Field(
        default_factory=list, description="Associated threat campaigns"
    )
    mitre_techniques: list[str] = Field(
        default_factory=list, description="MITRE ATT&CK technique IDs"
    )
    status: ThreatStatus = Field(
        default=ThreatStatus.NEW, description="Current status"
    )


class ThreatFeed(BaseModel):
    """A threat intelligence feed configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique feed identifier")
    name: str = Field(..., description="Feed name")
    provider: str = Field(..., description="Feed provider organization")
    url: str = Field(default="", description="Feed endpoint URL")
    feed_type: str = Field(default="STIX", description="Feed format (STIX, CSV, JSON)")
    update_frequency_hours: int = Field(
        default=24, ge=1, description="Update frequency in hours"
    )
    last_updated: datetime | None = Field(
        default=None, description="Last successful update timestamp"
    )
    indicators_count: int = Field(
        default=0, ge=0, description="Total indicators from this feed"
    )
    enabled: bool = Field(default=True, description="Whether the feed is active")
    api_key_configured: bool = Field(
        default=False, description="Whether API key is configured"
    )


class ThreatAlert(BaseModel):
    """A threat alert generated from intelligence correlation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique alert identifier")
    title: str = Field(..., description="Alert title")
    description: str = Field(default="", description="Detailed alert description")
    severity: ThreatSeverity = Field(..., description="Alert severity")
    category: ThreatCategory = Field(..., description="Threat category")
    indicators: list[str] = Field(
        default_factory=list, description="Related indicator IDs"
    )
    affected_systems: list[str] = Field(
        default_factory=list, description="Affected system identifiers"
    )
    detection_method: str = Field(
        default="", description="How the threat was detected"
    )
    created_at: datetime = Field(..., description="Alert creation timestamp")
    acknowledged: bool = Field(default=False, description="Whether alert is acknowledged")
    acknowledged_by: str | None = Field(
        default=None, description="User who acknowledged"
    )
    mitigated: bool = Field(default=False, description="Whether threat is mitigated")


class DLPPattern(BaseModel):
    """A detection pattern used within DLP policies."""

    model_config = ConfigDict(from_attributes=True)

    pattern_name: str = Field(..., description="Pattern identifier name")
    regex_pattern: str = Field(..., description="Regular expression for detection")
    description: str = Field(default="", description="Pattern description")
    sample_match: str = Field(default="", description="Example of matching content")


class DLPPolicy(BaseModel):
    """A data loss prevention policy configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique policy identifier")
    name: str = Field(..., description="Policy name")
    policy_type: DLPPolicyType = Field(..., description="Policy classification")
    description: str = Field(default="", description="Policy description")
    channels: list[DLPChannel] = Field(
        default_factory=list, description="Monitored channels"
    )
    action: DLPAction = Field(
        default=DLPAction.ALERT, description="Action on violation"
    )
    enabled: bool = Field(default=True, description="Whether policy is active")
    patterns: list[DLPPattern] = Field(
        default_factory=list, description="Detection patterns"
    )
    sensitivity_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Detection sensitivity (0-1)"
    )
    exceptions: list[str] = Field(
        default_factory=list, description="Exception rules or whitelisted entities"
    )
    violation_count_30d: int = Field(
        default=0, ge=0, description="Violations in last 30 days"
    )
    last_triggered: datetime | None = Field(
        default=None, description="Last time a violation was detected"
    )
    created_at: datetime = Field(..., description="Policy creation timestamp")
    updated_at: datetime | None = Field(
        default=None, description="Last modification timestamp"
    )


class DLPViolation(BaseModel):
    """A recorded DLP policy violation event."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique violation identifier")
    policy_id: str = Field(..., description="Triggering policy ID")
    channel: DLPChannel = Field(..., description="Channel where violation occurred")
    user_id: str = Field(default="", description="User who triggered the violation")
    content_summary: str = Field(
        default="", description="Summary of detected content"
    )
    data_classification: str = Field(
        default="", description="Data classification level"
    )
    action_taken: DLPAction = Field(..., description="Action that was taken")
    timestamp: datetime = Field(..., description="When the violation occurred")
    resolved: bool = Field(default=False, description="Whether the violation is resolved")
    resolution_notes: str | None = Field(
        default=None, description="Notes on resolution"
    )


class SecurityAwarenessTraining(BaseModel):
    """Security awareness training program tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique training identifier")
    name: str = Field(..., description="Training program name")
    training_type: str = Field(..., description="Type of training (e.g., phishing, HIPAA)")
    description: str = Field(default="", description="Training description")
    required_for_roles: list[str] = Field(
        default_factory=list, description="Roles required to complete"
    )
    completion_deadline: datetime | None = Field(
        default=None, description="Deadline for completion"
    )
    total_assigned: int = Field(default=0, ge=0, description="Total users assigned")
    total_completed: int = Field(default=0, ge=0, description="Total users completed")
    pass_rate: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Pass rate percentage"
    )
    phishing_simulation_click_rate: float | None = Field(
        default=None, ge=0.0, le=100.0,
        description="Click rate on phishing simulations (%)",
    )


# ---------------------------------------------------------------------------
# Request / Response Wrappers
# ---------------------------------------------------------------------------


class ThreatIndicatorCreate(BaseModel):
    """Request schema for creating a threat indicator."""

    model_config = ConfigDict(from_attributes=True)

    ioc_type: IOCType = Field(..., description="Type of IOC")
    value: str = Field(..., min_length=1, description="IOC value")
    threat_category: ThreatCategory = Field(..., description="Threat classification")
    severity: ThreatSeverity = Field(..., description="Severity level")
    description: str = Field(default="", description="Description")
    source: str = Field(default="manual", description="Intelligence source")
    confidence_score: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Confidence score"
    )
    related_campaigns: list[str] = Field(
        default_factory=list, description="Associated campaigns"
    )
    mitre_techniques: list[str] = Field(
        default_factory=list, description="MITRE ATT&CK techniques"
    )


class ThreatIndicatorUpdate(BaseModel):
    """Request schema for updating a threat indicator."""

    model_config = ConfigDict(from_attributes=True)

    severity: ThreatSeverity | None = Field(default=None, description="Updated severity")
    description: str | None = Field(default=None, description="Updated description")
    confidence_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Updated confidence"
    )
    status: ThreatStatus | None = Field(default=None, description="Updated status")
    related_campaigns: list[str] | None = Field(
        default=None, description="Updated campaigns"
    )
    mitre_techniques: list[str] | None = Field(
        default=None, description="Updated techniques"
    )


class ThreatFeedCreate(BaseModel):
    """Request schema for adding a threat feed."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=200, description="Feed name")
    provider: str = Field(..., min_length=1, description="Provider")
    url: str = Field(default="", description="Feed URL")
    feed_type: str = Field(default="STIX", description="Feed format")
    update_frequency_hours: int = Field(default=24, ge=1, description="Update frequency")
    enabled: bool = Field(default=True, description="Active status")


class ThreatFeedUpdate(BaseModel):
    """Request schema for updating a threat feed."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(default=None, description="Updated name")
    url: str | None = Field(default=None, description="Updated URL")
    update_frequency_hours: int | None = Field(
        default=None, ge=1, description="Updated frequency"
    )
    enabled: bool | None = Field(default=None, description="Updated active status")


class ThreatAlertCreate(BaseModel):
    """Request schema for creating a threat alert."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., min_length=1, max_length=500, description="Alert title")
    description: str = Field(default="", description="Alert description")
    severity: ThreatSeverity = Field(..., description="Severity")
    category: ThreatCategory = Field(..., description="Threat category")
    indicators: list[str] = Field(
        default_factory=list, description="Related indicator IDs"
    )
    affected_systems: list[str] = Field(
        default_factory=list, description="Affected systems"
    )
    detection_method: str = Field(default="", description="Detection method")


class DLPPolicyCreate(BaseModel):
    """Request schema for creating a DLP policy."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=300, description="Policy name")
    policy_type: DLPPolicyType = Field(..., description="Policy type")
    description: str = Field(default="", description="Description")
    channels: list[DLPChannel] = Field(
        default_factory=list, description="Monitored channels"
    )
    action: DLPAction = Field(default=DLPAction.ALERT, description="Action on violation")
    enabled: bool = Field(default=True, description="Active status")
    patterns: list[DLPPattern] = Field(
        default_factory=list, description="Detection patterns"
    )
    sensitivity_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Sensitivity"
    )
    exceptions: list[str] = Field(
        default_factory=list, description="Exception rules"
    )


class DLPPolicyUpdate(BaseModel):
    """Request schema for updating a DLP policy."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(default=None, description="Updated name")
    description: str | None = Field(default=None, description="Updated description")
    channels: list[DLPChannel] | None = Field(
        default=None, description="Updated channels"
    )
    action: DLPAction | None = Field(default=None, description="Updated action")
    enabled: bool | None = Field(default=None, description="Updated active status")
    patterns: list[DLPPattern] | None = Field(
        default=None, description="Updated patterns"
    )
    sensitivity_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Updated sensitivity"
    )
    exceptions: list[str] | None = Field(
        default=None, description="Updated exceptions"
    )


class DLPViolationResolve(BaseModel):
    """Request schema for resolving a DLP violation."""

    model_config = ConfigDict(from_attributes=True)

    resolution_notes: str = Field(
        ..., min_length=1, description="Resolution notes"
    )


class ThreatMetrics(BaseModel):
    """Aggregated threat intelligence metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_indicators: int = Field(default=0, description="Total tracked IOCs")
    indicators_by_category: dict[str, int] = Field(
        default_factory=dict, description="IOC count by threat category"
    )
    indicators_by_severity: dict[str, int] = Field(
        default_factory=dict, description="IOC count by severity"
    )
    active_threats: int = Field(
        default=0, description="Indicators with NEW or UNDER_INVESTIGATION status"
    )
    mitre_technique_coverage: list[str] = Field(
        default_factory=list, description="Unique MITRE techniques observed"
    )
    active_feeds: int = Field(default=0, description="Enabled threat feeds")
    total_feeds: int = Field(default=0, description="Total configured feeds")
    unacknowledged_alerts: int = Field(
        default=0, description="Alerts pending acknowledgment"
    )
    total_alerts: int = Field(default=0, description="Total alerts")
    mean_confidence_score: float = Field(
        default=0.0, description="Average IOC confidence score"
    )


class DLPMetrics(BaseModel):
    """Aggregated DLP metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_policies: int = Field(default=0, description="Total DLP policies")
    active_policies: int = Field(default=0, description="Enabled DLP policies")
    total_violations_30d: int = Field(
        default=0, description="Total violations in last 30 days"
    )
    violations_by_channel: dict[str, int] = Field(
        default_factory=dict, description="Violations by channel"
    )
    violations_by_policy_type: dict[str, int] = Field(
        default_factory=dict, description="Violations by policy type"
    )
    blocked_count: int = Field(
        default=0, description="Total blocked violations"
    )
    logged_count: int = Field(
        default=0, description="Total log-only violations"
    )
    resolved_count: int = Field(
        default=0, description="Total resolved violations"
    )
    unresolved_count: int = Field(
        default=0, description="Total unresolved violations"
    )


class TrainingComplianceRate(BaseModel):
    """Training compliance statistics."""

    model_config = ConfigDict(from_attributes=True)

    total_trainings: int = Field(default=0, description="Total training programs")
    overall_completion_rate: float = Field(
        default=0.0, description="Overall completion percentage"
    )
    overall_pass_rate: float = Field(
        default=0.0, description="Overall pass rate percentage"
    )
    avg_phishing_click_rate: float = Field(
        default=0.0, description="Average phishing simulation click rate"
    )
    overdue_trainings: int = Field(
        default=0, description="Trainings past deadline"
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class ThreatIndicatorListResponse(BaseModel):
    """Paginated list of threat indicators."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ThreatIndicator] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class ThreatAlertListResponse(BaseModel):
    """List of threat alerts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ThreatAlert] = Field(default_factory=list)
    total: int = Field(default=0)


class DLPPolicyListResponse(BaseModel):
    """List of DLP policies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DLPPolicy] = Field(default_factory=list)
    total: int = Field(default=0)


class DLPViolationListResponse(BaseModel):
    """Paginated list of DLP violations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DLPViolation] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class TrainingListResponse(BaseModel):
    """List of security awareness trainings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SecurityAwarenessTraining] = Field(default_factory=list)
    total: int = Field(default=0)
