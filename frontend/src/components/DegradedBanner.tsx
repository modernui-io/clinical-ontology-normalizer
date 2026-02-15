"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  XCircle,
  ShieldAlert,
  Phone,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types for degraded response fields from the backend
// ---------------------------------------------------------------------------

export interface DegradedState {
  /** True when the backend declined to answer */
  declined?: boolean;
  /** Reason the backend declined */
  decline_reason?: string | null;
  /** Escalation path text, e.g. "Consult clinical team" */
  escalation_path?: string | null;
  /** Overall confidence score 0-1 */
  confidence?: number;
  /** Map of backend dependency name -> up/down */
  dependency_state?: Record<string, boolean>;
  /** Whether source provenance is complete */
  provenance_complete?: boolean;
  /** Action gate policy result */
  action_gate?: {
    allowed: boolean;
    risk_tier: string;
    required_confidence: number;
    actual_confidence: number;
  } | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns true when any degraded condition is present. */
export function isDegraded(state: DegradedState): boolean {
  if (state.declined) return true;
  if (state.confidence != null && state.confidence < 0.5) return true;
  if (state.provenance_complete === false) return true;
  if (state.action_gate && !state.action_gate.allowed) return true;
  if (state.dependency_state) {
    const anyDown = Object.values(state.dependency_state).some((v) => !v);
    if (anyDown) return true;
  }
  return false;
}

/** Returns true when actions should be blocked. */
export function isActionBlocked(state: DegradedState): boolean {
  if (state.declined) return true;
  if (state.action_gate && !state.action_gate.allowed) return true;
  return false;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DegradedBannerProps {
  state: DegradedState;
  className?: string;
}

export function DegradedBanner({ state, className }: DegradedBannerProps) {
  if (!isDegraded(state)) return null;

  const declined = !!state.declined;
  const downDeps = state.dependency_state
    ? Object.entries(state.dependency_state)
        .filter(([, up]) => !up)
        .map(([name]) => name)
    : [];
  const lowConfidence = state.confidence != null && state.confidence < 0.5;
  const provenanceMissing = state.provenance_complete === false;
  const actionGateBlocked = state.action_gate && !state.action_gate.allowed;

  // Red for declined, amber for degraded
  const isRed = declined;

  return (
    <Card
      className={cn(
        "border-l-4",
        isRed
          ? "border-red-500 bg-red-50 dark:border-red-700 dark:bg-red-950"
          : "border-amber-500 bg-amber-50 dark:border-amber-700 dark:bg-amber-950",
        className
      )}
    >
      <CardContent className="py-4 space-y-3">
        {/* Header */}
        <div className="flex items-start gap-3">
          {isRed ? (
            <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
          )}
          <div className="flex-1 space-y-1">
            <p
              className={cn(
                "text-sm font-semibold",
                isRed
                  ? "text-red-800 dark:text-red-200"
                  : "text-amber-800 dark:text-amber-200"
              )}
            >
              {declined
                ? "Response Declined -- Insufficient Evidence"
                : "Degraded Mode -- Results May Be Incomplete"}
            </p>

            {/* Decline reason */}
            {declined && state.decline_reason && (
              <p className="text-sm text-red-700 dark:text-red-300">
                {state.decline_reason}
              </p>
            )}

            {/* Low confidence */}
            {lowConfidence && !declined && (
              <p className="text-sm text-amber-700 dark:text-amber-300">
                Confidence is below threshold ({Math.round((state.confidence ?? 0) * 100)}%).
                Results should be verified manually.
              </p>
            )}

            {/* Missing provenance */}
            {provenanceMissing && (
              <p className="text-sm text-amber-700 dark:text-amber-300">
                Source provenance is incomplete. Not all claims are backed by source documents.
              </p>
            )}

            {/* Down dependencies */}
            {downDeps.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-amber-700 dark:text-amber-300">
                  Unavailable services:
                </span>
                {downDeps.map((dep) => (
                  <Badge
                    key={dep}
                    variant="outline"
                    className="text-xs border-amber-400 text-amber-800 dark:border-amber-600 dark:text-amber-200"
                  >
                    {dep}
                  </Badge>
                ))}
              </div>
            )}

            {/* Action gate blocked */}
            {actionGateBlocked && state.action_gate && (
              <div className="flex items-center gap-2 mt-1">
                <ShieldAlert className="h-4 w-4 text-red-500 dark:text-red-400" />
                <span className="text-xs text-red-700 dark:text-red-300">
                  Actions blocked: {state.action_gate.risk_tier} risk tier requires{" "}
                  {Math.round(state.action_gate.required_confidence * 100)}% confidence
                  (actual: {Math.round(state.action_gate.actual_confidence * 100)}%)
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Escalation path */}
        {(state.escalation_path || declined) && (
          <div
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2",
              isRed
                ? "bg-red-100 dark:bg-red-900/50"
                : "bg-amber-100 dark:bg-amber-900/50"
            )}
          >
            <Phone
              className={cn(
                "h-4 w-4 shrink-0",
                isRed
                  ? "text-red-600 dark:text-red-400"
                  : "text-amber-600 dark:text-amber-400"
              )}
            />
            <span
              className={cn(
                "text-sm font-medium",
                isRed
                  ? "text-red-800 dark:text-red-200"
                  : "text-amber-800 dark:text-amber-200"
              )}
            >
              {state.escalation_path || "Contact clinical team for manual review"}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Confidence badge for individual entities
// ---------------------------------------------------------------------------

interface EntityConfidenceBadgeProps {
  confidence: number;
  showWarning?: boolean;
}

export function EntityConfidenceBadge({
  confidence,
  showWarning = true,
}: EntityConfidenceBadgeProps) {
  const pct = Math.round(confidence * 100);

  let colorClass: string;
  let label: string;
  if (confidence >= 0.8) {
    colorClass =
      "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700";
    label = "High";
  } else if (confidence >= 0.5) {
    colorClass =
      "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700";
    label = "Medium";
  } else {
    colorClass =
      "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700";
    label = "Low";
  }

  return (
    <span className="inline-flex items-center gap-1">
      <Badge variant="outline" className={cn("text-xs font-medium", colorClass)}>
        {pct}% {label}
      </Badge>
      {showWarning && confidence < 0.3 && (
        <span className="text-xs text-red-600 dark:text-red-400 font-medium">
          Verify manually
        </span>
      )}
    </span>
  );
}
