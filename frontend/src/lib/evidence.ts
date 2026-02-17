/**
 * Shared evidence types and utilities for evidence-indexed pages.
 *
 * Single source of truth for docs, changelog, and any future
 * evidence-backed claim surfaces (P4-020).
 */

export type EvidenceStatus = "verified" | "stale" | "unverified" | "disputed";
export type FreshnessSLA = "quarterly" | "monthly" | "per-release" | "real-time";
export type EvidenceCategory = "security" | "clinical" | "operational" | "interop" | "product";

export interface EvidenceEntry {
  claim_id: string;
  claim_text: string;
  category: EvidenceCategory;
  evidence_paths: string[];
  last_verified: string;
  verified_by: string;
  freshness_sla: FreshnessSLA;
  status: EvidenceStatus;
  supporting_links?: SupportingLink[];
}

export interface SupportingLink {
  label: string;
  href: string;
}

export interface EvidenceStatusStyle {
  bg: string;
  text: string;
  border: string;
  label: string;
}

const SLA_MAX_DAYS: Record<FreshnessSLA, number> = {
  "real-time": 1,
  "per-release": 14,
  "monthly": 30,
  "quarterly": 90,
};

/**
 * Returns Tailwind classes and label for an evidence status badge.
 * Automatically downgrades "verified" to "stale" when the SLA window
 * has elapsed since last_verified.
 */
export function getEvidenceStatusColor(
  status: EvidenceStatus,
  freshness_sla: FreshnessSLA,
  last_verified: string,
  referenceDate: string = "2026-02-16"
): EvidenceStatusStyle {
  const now = new Date(referenceDate);
  const verified = new Date(last_verified);
  const daysSince = Math.floor(
    (now.getTime() - verified.getTime()) / (1000 * 60 * 60 * 24)
  );

  const isStale = daysSince > SLA_MAX_DAYS[freshness_sla];
  const effectiveStatus =
    isStale && status === "verified" ? "stale" : status;

  switch (effectiveStatus) {
    case "verified":
      return {
        bg: "bg-emerald-50",
        text: "text-emerald-700",
        border: "border-emerald-200",
        label: "Verified",
      };
    case "stale":
      return {
        bg: "bg-amber-50",
        text: "text-amber-700",
        border: "border-amber-200",
        label: "Stale",
      };
    case "unverified":
      return {
        bg: "bg-red-50",
        text: "text-red-700",
        border: "border-red-200",
        label: "Unverified",
      };
    case "disputed":
      return {
        bg: "bg-red-50",
        text: "text-red-700",
        border: "border-red-200",
        label: "Disputed",
      };
  }
}

/**
 * Required fields for every evidence entry. Used by the consistency
 * check test to ensure no claim is published without evidence metadata.
 */
export const REQUIRED_EVIDENCE_FIELDS: (keyof EvidenceEntry)[] = [
  "claim_id",
  "claim_text",
  "category",
  "evidence_paths",
  "last_verified",
  "verified_by",
  "freshness_sla",
  "status",
];

/**
 * Validates that every entry has all required fields populated.
 * Returns an array of error strings (empty = all valid).
 */
export function validateEvidenceEntries(
  entries: EvidenceEntry[]
): string[] {
  const errors: string[] = [];
  for (const entry of entries) {
    for (const field of REQUIRED_EVIDENCE_FIELDS) {
      const value = entry[field];
      if (value === undefined || value === null || value === "") {
        errors.push(`${entry.claim_id}: missing required field "${field}"`);
      }
    }
    if (
      !Array.isArray(entry.evidence_paths) ||
      entry.evidence_paths.length === 0
    ) {
      errors.push(`${entry.claim_id}: evidence_paths must be non-empty`);
    }
  }
  return errors;
}
