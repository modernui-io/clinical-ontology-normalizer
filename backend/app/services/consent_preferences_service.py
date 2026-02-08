"""Patient Consent Preference Center Service (VP-Product-7).

Comprehensive consent preference management for pharma-regulated
clinical trial recruitment. Provides granular per-category consent,
channel preferences, consent templates, full audit trails, expiry
detection, and program-wide metrics.

This service is SEPARATE from the basic ``consent_service.py`` which
handles HIPAA consent records. This preference center sits on top and
provides a richer patient-facing consent experience.

Usage:
    from app.services.consent_preferences_service import (
        get_consent_preferences_service,
    )

    svc = get_consent_preferences_service()
    profile = svc.get_profile("patient-1")
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.schemas.consent_preferences import (
    CategoryMetrics,
    ConsentAction,
    ConsentCategory,
    ConsentCheckResponse,
    ConsentExportRecord,
    ConsentMetrics,
    ConsentPreference,
    ConsentPreferenceAuditEntry,
    ConsentSource,
    ConsentTemplate,
    ExpiringConsentItem,
    MonthlyRate,
    OverallConsentStatus,
    PreferenceProfile,
    PreferenceStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton plumbing
# ---------------------------------------------------------------------------

_instance: ConsentPreferencesService | None = None
_lock = Lock()


def get_consent_preferences_service() -> ConsentPreferencesService:
    """Return the singleton ConsentPreferencesService."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ConsentPreferencesService()
    return _instance


def reset_consent_preferences_service() -> None:
    """Reset the singleton (used by tests)."""
    global _instance
    with _lock:
        _instance = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ConsentPreferencesService:
    """Manages patient consent preferences, templates, and audit trails."""

    def __init__(self) -> None:
        # profiles keyed by patient_id
        self._profiles: dict[str, PreferenceProfile] = {}
        # audit entries keyed by patient_id
        self._audit: dict[str, list[ConsentPreferenceAuditEntry]] = {}
        # templates keyed by template id
        self._templates: dict[str, ConsentTemplate] = {}

        self._seed()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed(self) -> None:
        """Populate demo data: templates, patient profiles, audit entries."""
        now = datetime.now(timezone.utc)

        # --- Templates ---
        self._templates["tmpl-standard"] = ConsentTemplate(
            id="tmpl-standard",
            name="Standard Clinical Trial",
            description="Standard consent template for Phase III clinical trials",
            version=1,
            categories=[
                ConsentCategory.TRIAL_SCREENING,
                ConsentCategory.DATA_SHARING,
                ConsentCategory.COMMUNICATION,
                ConsentCategory.ANALYTICS,
            ],
            required_categories=[
                ConsentCategory.TRIAL_SCREENING,
                ConsentCategory.DATA_SHARING,
            ],
            language="en",
            effective_date=now - timedelta(days=180),
        )

        self._templates["tmpl-enhanced"] = ConsentTemplate(
            id="tmpl-enhanced",
            name="Enhanced Research",
            description="Extended consent template with biobank and genetic analysis",
            version=1,
            categories=[
                ConsentCategory.TRIAL_SCREENING,
                ConsentCategory.DATA_SHARING,
                ConsentCategory.COMMUNICATION,
                ConsentCategory.ANALYTICS,
                ConsentCategory.RESEARCH_REUSE,
                ConsentCategory.BIOBANK,
                ConsentCategory.GENETIC_ANALYSIS,
                ConsentCategory.THIRD_PARTY_TRANSFER,
            ],
            required_categories=[
                ConsentCategory.TRIAL_SCREENING,
                ConsentCategory.DATA_SHARING,
                ConsentCategory.BIOBANK,
            ],
            language="en",
            effective_date=now - timedelta(days=90),
        )

        # --- Patient profiles ---
        seed_patients: list[dict] = [
            # Fully consented patients
            {
                "patient_id": "PAT-001",
                "statuses": {cat: PreferenceStatus.OPTED_IN for cat in ConsentCategory},
                "overall": OverallConsentStatus.FULL,
            },
            {
                "patient_id": "PAT-002",
                "statuses": {cat: PreferenceStatus.OPTED_IN for cat in ConsentCategory},
                "overall": OverallConsentStatus.FULL,
            },
            # Partially consented
            {
                "patient_id": "PAT-003",
                "statuses": {
                    ConsentCategory.TRIAL_SCREENING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.DATA_SHARING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.COMMUNICATION: PreferenceStatus.OPTED_IN,
                    ConsentCategory.ANALYTICS: PreferenceStatus.OPTED_OUT,
                    ConsentCategory.RESEARCH_REUSE: PreferenceStatus.NOT_SET,
                    ConsentCategory.BIOBANK: PreferenceStatus.NOT_SET,
                    ConsentCategory.GENETIC_ANALYSIS: PreferenceStatus.NOT_SET,
                    ConsentCategory.THIRD_PARTY_TRANSFER: PreferenceStatus.OPTED_OUT,
                },
                "overall": OverallConsentStatus.PARTIAL,
            },
            {
                "patient_id": "PAT-004",
                "statuses": {
                    ConsentCategory.TRIAL_SCREENING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.DATA_SHARING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.COMMUNICATION: PreferenceStatus.NOT_SET,
                    ConsentCategory.ANALYTICS: PreferenceStatus.NOT_SET,
                    ConsentCategory.RESEARCH_REUSE: PreferenceStatus.OPTED_IN,
                    ConsentCategory.BIOBANK: PreferenceStatus.OPTED_OUT,
                    ConsentCategory.GENETIC_ANALYSIS: PreferenceStatus.NOT_SET,
                    ConsentCategory.THIRD_PARTY_TRANSFER: PreferenceStatus.NOT_SET,
                },
                "overall": OverallConsentStatus.PARTIAL,
            },
            {
                "patient_id": "PAT-005",
                "statuses": {
                    ConsentCategory.TRIAL_SCREENING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.DATA_SHARING: PreferenceStatus.OPTED_OUT,
                    ConsentCategory.COMMUNICATION: PreferenceStatus.OPTED_IN,
                    ConsentCategory.ANALYTICS: PreferenceStatus.NOT_SET,
                    ConsentCategory.RESEARCH_REUSE: PreferenceStatus.NOT_SET,
                    ConsentCategory.BIOBANK: PreferenceStatus.NOT_SET,
                    ConsentCategory.GENETIC_ANALYSIS: PreferenceStatus.NOT_SET,
                    ConsentCategory.THIRD_PARTY_TRANSFER: PreferenceStatus.NOT_SET,
                },
                "overall": OverallConsentStatus.PARTIAL,
            },
            # Withdrawn patients
            {
                "patient_id": "PAT-006",
                "statuses": {cat: PreferenceStatus.OPTED_OUT for cat in ConsentCategory},
                "overall": OverallConsentStatus.WITHDRAWN,
            },
            {
                "patient_id": "PAT-007",
                "statuses": {cat: PreferenceStatus.OPTED_OUT for cat in ConsentCategory},
                "overall": OverallConsentStatus.WITHDRAWN,
            },
            # Pending patients
            {
                "patient_id": "PAT-008",
                "statuses": {cat: PreferenceStatus.NOT_SET for cat in ConsentCategory},
                "overall": OverallConsentStatus.PENDING,
            },
            {
                "patient_id": "PAT-009",
                "statuses": {cat: PreferenceStatus.NOT_SET for cat in ConsentCategory},
                "overall": OverallConsentStatus.PENDING,
            },
            # Mixed / edge cases
            {
                "patient_id": "PAT-010",
                "statuses": {
                    ConsentCategory.TRIAL_SCREENING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.DATA_SHARING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.COMMUNICATION: PreferenceStatus.OPTED_IN,
                    ConsentCategory.ANALYTICS: PreferenceStatus.OPTED_IN,
                    ConsentCategory.RESEARCH_REUSE: PreferenceStatus.OPTED_IN,
                    ConsentCategory.BIOBANK: PreferenceStatus.OPTED_IN,
                    ConsentCategory.GENETIC_ANALYSIS: PreferenceStatus.OPTED_OUT,
                    ConsentCategory.THIRD_PARTY_TRANSFER: PreferenceStatus.OPTED_OUT,
                },
                "overall": OverallConsentStatus.PARTIAL,
            },
            # Patient with expiring consent
            {
                "patient_id": "PAT-011",
                "statuses": {
                    ConsentCategory.TRIAL_SCREENING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.DATA_SHARING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.COMMUNICATION: PreferenceStatus.OPTED_IN,
                    ConsentCategory.ANALYTICS: PreferenceStatus.NOT_SET,
                    ConsentCategory.RESEARCH_REUSE: PreferenceStatus.NOT_SET,
                    ConsentCategory.BIOBANK: PreferenceStatus.NOT_SET,
                    ConsentCategory.GENETIC_ANALYSIS: PreferenceStatus.NOT_SET,
                    ConsentCategory.THIRD_PARTY_TRANSFER: PreferenceStatus.NOT_SET,
                },
                "overall": OverallConsentStatus.PARTIAL,
                "expires_days": 15,  # expires in 15 days
            },
            # Another patient with expiring consent
            {
                "patient_id": "PAT-012",
                "statuses": {
                    ConsentCategory.TRIAL_SCREENING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.DATA_SHARING: PreferenceStatus.OPTED_IN,
                    ConsentCategory.COMMUNICATION: PreferenceStatus.NOT_SET,
                    ConsentCategory.ANALYTICS: PreferenceStatus.NOT_SET,
                    ConsentCategory.RESEARCH_REUSE: PreferenceStatus.NOT_SET,
                    ConsentCategory.BIOBANK: PreferenceStatus.NOT_SET,
                    ConsentCategory.GENETIC_ANALYSIS: PreferenceStatus.NOT_SET,
                    ConsentCategory.THIRD_PARTY_TRANSFER: PreferenceStatus.NOT_SET,
                },
                "overall": OverallConsentStatus.PARTIAL,
                "expires_days": 5,  # expires in 5 days
            },
        ]

        default_channels = {"EMAIL": True, "SMS": False, "PHONE": False, "PORTAL": True, "MAIL": False}

        for pdata in seed_patients:
            patient_id = pdata["patient_id"]
            statuses: dict[ConsentCategory, PreferenceStatus] = pdata["statuses"]
            overall: OverallConsentStatus = pdata["overall"]
            expires_days: int | None = pdata.get("expires_days")

            prefs: list[ConsentPreference] = []
            for cat, st in statuses.items():
                expires_at = None
                if expires_days is not None and st == PreferenceStatus.OPTED_IN:
                    expires_at = now + timedelta(days=expires_days)

                pref = ConsentPreference(
                    id=f"cpref-{patient_id}-{cat.value}",
                    patient_id=patient_id,
                    category=cat,
                    status=st,
                    channel_preferences=dict(default_channels) if st == PreferenceStatus.OPTED_IN else {},
                    grantor="system-seed",
                    granted_at=now - timedelta(days=30),
                    expires_at=expires_at,
                    version=1,
                    source=ConsentSource.WEB_PORTAL,
                )
                prefs.append(pref)

            opted_in_count = sum(1 for s in statuses.values() if s == PreferenceStatus.OPTED_IN)
            completeness = (
                sum(1 for s in statuses.values() if s != PreferenceStatus.NOT_SET)
                / len(ConsentCategory)
                * 100
            )

            profile = PreferenceProfile(
                patient_id=patient_id,
                preferences=prefs,
                overall_consent_status=overall,
                last_updated=now - timedelta(days=1),
                consent_version=1,
                profile_completeness_pct=round(completeness, 1),
            )
            self._profiles[patient_id] = profile

            # Seed audit entries
            self._audit[patient_id] = []
            for pref in prefs:
                if pref.status != PreferenceStatus.NOT_SET:
                    action = (
                        ConsentAction.GRANTED
                        if pref.status == PreferenceStatus.OPTED_IN
                        else ConsentAction.WITHDRAWN
                    )
                    entry = ConsentPreferenceAuditEntry(
                        id=f"audit-{uuid.uuid4().hex[:8]}",
                        patient_id=patient_id,
                        category=pref.category,
                        action=action,
                        old_status=PreferenceStatus.NOT_SET,
                        new_status=pref.status,
                        performed_by="system-seed",
                        timestamp=pref.granted_at,
                        notes="Initial seed data",
                    )
                    self._audit[patient_id].append(entry)

    # ------------------------------------------------------------------
    # Clear (for tests)
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data and re-seed."""
        self._profiles.clear()
        self._audit.clear()
        self._templates.clear()
        self._seed()

    # ------------------------------------------------------------------
    # Profile queries
    # ------------------------------------------------------------------

    def get_profile(self, patient_id: str) -> PreferenceProfile:
        """Get the full preference profile for a patient.

        Raises:
            KeyError: If the patient is not found.
        """
        if patient_id not in self._profiles:
            raise KeyError(f"Patient profile not found: {patient_id}")
        return self._profiles[patient_id]

    def list_profiles(
        self,
        status: OverallConsentStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[PreferenceProfile], int]:
        """List preference profiles with optional filtering.

        Returns:
            Tuple of (profiles, total_count).
        """
        profiles = list(self._profiles.values())

        if status is not None:
            profiles = [p for p in profiles if p.overall_consent_status == status]

        total = len(profiles)
        return profiles[offset : offset + limit], total

    # ------------------------------------------------------------------
    # Preference updates
    # ------------------------------------------------------------------

    def update_preference(
        self,
        patient_id: str,
        category: ConsentCategory,
        status: PreferenceStatus,
        channel_prefs: dict[str, bool] | None = None,
        source: ConsentSource = ConsentSource.WEB_PORTAL,
        grantor: str = "system",
        ip_address: str | None = None,
    ) -> ConsentPreference:
        """Update a single consent preference for a patient.

        Creates the patient profile if it does not exist.

        Returns:
            The updated ConsentPreference.
        """
        now = datetime.now(timezone.utc)

        # Ensure profile exists
        if patient_id not in self._profiles:
            self._profiles[patient_id] = PreferenceProfile(
                patient_id=patient_id,
                preferences=[],
                overall_consent_status=OverallConsentStatus.PENDING,
                last_updated=now,
                consent_version=1,
                profile_completeness_pct=0.0,
            )
            self._audit[patient_id] = []

        profile = self._profiles[patient_id]

        # Find or create the preference for this category
        existing = None
        for pref in profile.preferences:
            if pref.category == category:
                existing = pref
                break

        old_status = existing.status if existing else PreferenceStatus.NOT_SET

        if existing is not None:
            # Update in-place by replacing in the list
            new_pref = ConsentPreference(
                id=existing.id,
                patient_id=patient_id,
                category=category,
                status=status,
                channel_preferences=channel_prefs if channel_prefs is not None else existing.channel_preferences,
                grantor=grantor,
                granted_at=now,
                expires_at=existing.expires_at,
                version=existing.version + 1,
                withdrawal_reason=existing.withdrawal_reason if status == PreferenceStatus.OPTED_OUT else None,
                ip_address=ip_address,
                source=source,
            )
            idx = profile.preferences.index(existing)
            profile.preferences[idx] = new_pref
        else:
            new_pref = ConsentPreference(
                id=f"cpref-{patient_id}-{category.value}",
                patient_id=patient_id,
                category=category,
                status=status,
                channel_preferences=channel_prefs or {},
                grantor=grantor,
                granted_at=now,
                version=1,
                ip_address=ip_address,
                source=source,
            )
            profile.preferences.append(new_pref)

        # Record audit
        action = ConsentAction.GRANTED if status == PreferenceStatus.OPTED_IN else (
            ConsentAction.WITHDRAWN if status == PreferenceStatus.OPTED_OUT else ConsentAction.UPDATED
        )
        self._record_audit(
            patient_id=patient_id,
            category=category,
            action=action,
            old_status=old_status,
            new_status=status,
            performed_by=grantor,
            ip_address=ip_address,
            notes=None,
        )

        # Recalculate profile stats
        self._recalculate_profile(patient_id)

        return new_pref

    def bulk_update_preferences(
        self,
        patient_id: str,
        preferences: list[dict],
    ) -> PreferenceProfile:
        """Update multiple consent preferences at once.

        Args:
            patient_id: Patient identifier.
            preferences: List of dicts with keys: category, status,
                channel_preferences, source, grantor, ip_address.

        Returns:
            Updated PreferenceProfile.
        """
        for pref_data in preferences:
            self.update_preference(
                patient_id=patient_id,
                category=pref_data["category"],
                status=pref_data["status"],
                channel_prefs=pref_data.get("channel_preferences"),
                source=pref_data.get("source", ConsentSource.WEB_PORTAL),
                grantor=pref_data.get("grantor", "system"),
                ip_address=pref_data.get("ip_address"),
            )

        return self._profiles[patient_id]

    # ------------------------------------------------------------------
    # Withdrawals
    # ------------------------------------------------------------------

    def withdraw_consent(
        self,
        patient_id: str,
        category: ConsentCategory,
        reason: str,
        performed_by: str = "system",
        ip_address: str | None = None,
    ) -> ConsentPreference:
        """Withdraw consent for a specific category.

        Args:
            patient_id: Patient identifier.
            category: Category to withdraw.
            reason: Required reason for withdrawal.
            performed_by: Who performed the withdrawal.
            ip_address: IP address for audit.

        Raises:
            KeyError: If patient not found.
            ValueError: If reason is empty.

        Returns:
            The updated ConsentPreference.
        """
        if not reason or not reason.strip():
            raise ValueError("Withdrawal reason is required")

        if patient_id not in self._profiles:
            raise KeyError(f"Patient profile not found: {patient_id}")

        profile = self._profiles[patient_id]
        existing = None
        for pref in profile.preferences:
            if pref.category == category:
                existing = pref
                break

        old_status = existing.status if existing else PreferenceStatus.NOT_SET

        now = datetime.now(timezone.utc)

        if existing is not None:
            new_pref = ConsentPreference(
                id=existing.id,
                patient_id=patient_id,
                category=category,
                status=PreferenceStatus.OPTED_OUT,
                channel_preferences={},
                grantor=performed_by,
                granted_at=now,
                expires_at=None,
                version=existing.version + 1,
                withdrawal_reason=reason,
                ip_address=ip_address,
                source=ConsentSource.WEB_PORTAL,
            )
            idx = profile.preferences.index(existing)
            profile.preferences[idx] = new_pref
        else:
            new_pref = ConsentPreference(
                id=f"cpref-{patient_id}-{category.value}",
                patient_id=patient_id,
                category=category,
                status=PreferenceStatus.OPTED_OUT,
                channel_preferences={},
                grantor=performed_by,
                granted_at=now,
                version=1,
                withdrawal_reason=reason,
                ip_address=ip_address,
                source=ConsentSource.WEB_PORTAL,
            )
            profile.preferences.append(new_pref)

        self._record_audit(
            patient_id=patient_id,
            category=category,
            action=ConsentAction.WITHDRAWN,
            old_status=old_status,
            new_status=PreferenceStatus.OPTED_OUT,
            performed_by=performed_by,
            ip_address=ip_address,
            notes=f"Withdrawal reason: {reason}",
        )

        self._recalculate_profile(patient_id)
        return new_pref

    def withdraw_all_consent(
        self,
        patient_id: str,
        reason: str,
        performed_by: str = "system",
        ip_address: str | None = None,
    ) -> PreferenceProfile:
        """Withdraw all consent for a patient.

        Raises:
            KeyError: If patient not found.
            ValueError: If reason is empty.
        """
        if not reason or not reason.strip():
            raise ValueError("Withdrawal reason is required")

        if patient_id not in self._profiles:
            raise KeyError(f"Patient profile not found: {patient_id}")

        profile = self._profiles[patient_id]

        # Withdraw each category that has preferences
        categories_to_withdraw = set()
        for pref in profile.preferences:
            categories_to_withdraw.add(pref.category)
        # Also include any categories not yet in the profile
        for cat in ConsentCategory:
            categories_to_withdraw.add(cat)

        for cat in categories_to_withdraw:
            self.withdraw_consent(
                patient_id=patient_id,
                category=cat,
                reason=reason,
                performed_by=performed_by,
                ip_address=ip_address,
            )

        return self._profiles[patient_id]

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def get_audit_trail(
        self,
        patient_id: str,
        category: ConsentCategory | None = None,
        limit: int = 50,
    ) -> list[ConsentPreferenceAuditEntry]:
        """Get consent audit trail for a patient.

        Args:
            patient_id: Patient identifier.
            category: Optional filter by category.
            limit: Max entries to return.

        Returns:
            List of audit entries, most recent first.
        """
        entries = self._audit.get(patient_id, [])
        if category is not None:
            entries = [e for e in entries if e.category == category]
        # Sort by timestamp descending
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    # ------------------------------------------------------------------
    # Consent check
    # ------------------------------------------------------------------

    def check_consent(
        self,
        patient_id: str,
        category: ConsentCategory,
        channel: str | None = None,
    ) -> ConsentCheckResponse:
        """Quick check if a patient has consented to a category+channel.

        Returns a ConsentCheckResponse regardless of whether the patient
        is known. Unknown patients are treated as NOT_SET / not consented.
        """
        if patient_id not in self._profiles:
            return ConsentCheckResponse(
                patient_id=patient_id,
                category=category,
                channel=channel,
                is_consented=False,
                status=PreferenceStatus.NOT_SET,
            )

        profile = self._profiles[patient_id]
        pref = None
        for p in profile.preferences:
            if p.category == category:
                pref = p
                break

        if pref is None:
            return ConsentCheckResponse(
                patient_id=patient_id,
                category=category,
                channel=channel,
                is_consented=False,
                status=PreferenceStatus.NOT_SET,
            )

        # Check expiry
        now = datetime.now(timezone.utc)
        if pref.expires_at is not None and pref.expires_at <= now:
            return ConsentCheckResponse(
                patient_id=patient_id,
                category=category,
                channel=channel,
                is_consented=False,
                status=PreferenceStatus.EXPIRED,
            )

        is_consented = pref.status == PreferenceStatus.OPTED_IN

        # If a channel is specified, also verify channel preference
        if channel is not None and is_consented:
            channel_enabled = pref.channel_preferences.get(channel, False)
            is_consented = channel_enabled

        return ConsentCheckResponse(
            patient_id=patient_id,
            category=category,
            channel=channel,
            is_consented=is_consented,
            status=pref.status,
        )

    # ------------------------------------------------------------------
    # Expiring consents
    # ------------------------------------------------------------------

    def get_expiring_consents(self, days_ahead: int = 30) -> list[ExpiringConsentItem]:
        """Get consents expiring within N days.

        Returns:
            List of ExpiringConsentItem sorted by days_until_expiry ascending.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        items: list[ExpiringConsentItem] = []

        for profile in self._profiles.values():
            for pref in profile.preferences:
                if (
                    pref.status == PreferenceStatus.OPTED_IN
                    and pref.expires_at is not None
                    and now < pref.expires_at <= cutoff
                ):
                    days_until = (pref.expires_at - now).days
                    items.append(
                        ExpiringConsentItem(
                            patient_id=pref.patient_id,
                            category=pref.category,
                            expires_at=pref.expires_at,
                            days_until_expiry=days_until,
                        )
                    )

        items.sort(key=lambda x: x.days_until_expiry)
        return items

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ConsentMetrics:
        """Calculate program-wide consent metrics."""
        profiles = list(self._profiles.values())
        total = len(profiles)

        if total == 0:
            return ConsentMetrics(total_patients=0)

        full = sum(1 for p in profiles if p.overall_consent_status == OverallConsentStatus.FULL)
        partial = sum(1 for p in profiles if p.overall_consent_status == OverallConsentStatus.PARTIAL)
        withdrawn = sum(1 for p in profiles if p.overall_consent_status == OverallConsentStatus.WITHDRAWN)
        pending = sum(1 for p in profiles if p.overall_consent_status == OverallConsentStatus.PENDING)

        # Per-category metrics
        by_category: dict[str, CategoryMetrics] = {}
        for cat in ConsentCategory:
            opted_in = 0
            opted_out = 0
            not_set = 0
            for profile in profiles:
                found = False
                for pref in profile.preferences:
                    if pref.category == cat:
                        found = True
                        if pref.status == PreferenceStatus.OPTED_IN:
                            opted_in += 1
                        elif pref.status == PreferenceStatus.OPTED_OUT:
                            opted_out += 1
                        else:
                            not_set += 1
                        break
                if not found:
                    not_set += 1
            by_category[cat.value] = CategoryMetrics(
                opted_in=opted_in,
                opted_out=opted_out,
                not_set=not_set,
            )

        # Average categories consented per patient
        total_consented_cats = 0
        for profile in profiles:
            consented = sum(
                1 for pref in profile.preferences if pref.status == PreferenceStatus.OPTED_IN
            )
            total_consented_cats += consented
        avg_cats = total_consented_cats / total

        # Consent rate trend (generate synthetic monthly data)
        now = datetime.now(timezone.utc)
        trend: list[MonthlyRate] = []
        base_rate = (full + partial) / total * 100
        for i in range(6, 0, -1):
            month_dt = now - timedelta(days=30 * i)
            month_str = month_dt.strftime("%Y-%m")
            # Simulate increasing trend
            rate = max(0.0, min(100.0, base_rate - (i * 5) + (i * 2)))
            trend.append(MonthlyRate(month=month_str, rate=round(rate, 1)))

        # Withdrawal rate (last 30 days)
        thirty_days_ago = now - timedelta(days=30)
        withdrawal_count = 0
        for entries in self._audit.values():
            for entry in entries:
                if entry.action == ConsentAction.WITHDRAWN and entry.timestamp >= thirty_days_ago:
                    withdrawal_count += 1
        withdrawal_rate = withdrawal_count / total * 100 if total > 0 else 0.0

        return ConsentMetrics(
            total_patients=total,
            fully_consented_pct=round(full / total * 100, 1),
            partially_consented_pct=round(partial / total * 100, 1),
            withdrawn_pct=round(withdrawn / total * 100, 1),
            pending_pct=round(pending / total * 100, 1),
            by_category=by_category,
            avg_categories_consented=round(avg_cats, 2),
            consent_rate_trend=trend,
            withdrawal_rate_30d=round(withdrawal_rate, 1),
        )

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def get_templates(self) -> list[ConsentTemplate]:
        """Get all consent templates."""
        return list(self._templates.values())

    def get_template(self, template_id: str) -> ConsentTemplate:
        """Get a specific consent template.

        Raises:
            KeyError: If template not found.
        """
        if template_id not in self._templates:
            raise KeyError(f"Template not found: {template_id}")
        return self._templates[template_id]

    def apply_template(
        self,
        patient_id: str,
        template_id: str,
        source: ConsentSource = ConsentSource.WEB_PORTAL,
        grantor: str = "system",
        ip_address: str | None = None,
    ) -> PreferenceProfile:
        """Apply a consent template to a patient, opting them into all template categories.

        Raises:
            KeyError: If template not found.
        """
        template = self.get_template(template_id)

        for cat in template.categories:
            self.update_preference(
                patient_id=patient_id,
                category=cat,
                status=PreferenceStatus.OPTED_IN,
                channel_prefs={"EMAIL": True, "PORTAL": True, "SMS": False, "PHONE": False, "MAIL": False},
                source=source,
                grantor=grantor,
                ip_address=ip_address,
            )

        return self._profiles[patient_id]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_consent_record(self, patient_id: str) -> ConsentExportRecord:
        """Export the full consent record for data portability.

        Raises:
            KeyError: If patient not found.
        """
        profile = self.get_profile(patient_id)
        audit = self.get_audit_trail(patient_id, limit=10000)

        return ConsentExportRecord(
            patient_id=patient_id,
            profile=profile,
            audit_trail=audit,
            exported_at=datetime.now(timezone.utc),
            export_format="JSON",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_audit(
        self,
        patient_id: str,
        category: ConsentCategory,
        action: ConsentAction,
        old_status: PreferenceStatus | None,
        new_status: PreferenceStatus,
        performed_by: str,
        ip_address: str | None = None,
        notes: str | None = None,
    ) -> ConsentPreferenceAuditEntry:
        """Record an audit entry."""
        entry = ConsentPreferenceAuditEntry(
            id=f"audit-{uuid.uuid4().hex[:12]}",
            patient_id=patient_id,
            category=category,
            action=action,
            old_status=old_status,
            new_status=new_status,
            performed_by=performed_by,
            timestamp=datetime.now(timezone.utc),
            ip_address=ip_address,
            notes=notes,
        )
        if patient_id not in self._audit:
            self._audit[patient_id] = []
        self._audit[patient_id].append(entry)
        return entry

    def _recalculate_profile(self, patient_id: str) -> None:
        """Recalculate overall status and completeness for a profile."""
        profile = self._profiles[patient_id]
        now = datetime.now(timezone.utc)

        statuses = []
        for pref in profile.preferences:
            s = pref.status
            # Check expiry
            if s == PreferenceStatus.OPTED_IN and pref.expires_at is not None and pref.expires_at <= now:
                s = PreferenceStatus.EXPIRED
            statuses.append(s)

        opted_in_count = sum(1 for s in statuses if s == PreferenceStatus.OPTED_IN)
        opted_out_count = sum(1 for s in statuses if s == PreferenceStatus.OPTED_OUT)
        not_set_count = sum(1 for s in statuses if s in (PreferenceStatus.NOT_SET, PreferenceStatus.EXPIRED))

        total_cats = len(ConsentCategory)
        addressed = sum(1 for s in statuses if s not in (PreferenceStatus.NOT_SET,))

        # Determine overall status
        if opted_in_count == total_cats:
            overall = OverallConsentStatus.FULL
        elif opted_out_count == total_cats or (opted_out_count > 0 and opted_in_count == 0 and not_set_count == 0):
            overall = OverallConsentStatus.WITHDRAWN
        elif opted_in_count > 0 or opted_out_count > 0:
            overall = OverallConsentStatus.PARTIAL
        else:
            overall = OverallConsentStatus.PENDING

        profile.overall_consent_status = overall
        profile.last_updated = now
        profile.consent_version += 1
        profile.profile_completeness_pct = round(addressed / total_cats * 100, 1)
